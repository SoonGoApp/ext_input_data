import asyncio
import json
from abc import ABC, abstractmethod
from contextlib import closing
from logging import Logger
from typing import Any, Dict, List, Optional, Self, Sequence

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

from soongo_data.connectors.__base__.check_utils import (
    check_col_matching,
    check_columns,
    check_no_dup_values,
    get_record_date,
    set_record_cols,
)
from soongo_data.data_models.base import DataColumn
from soongo_data.utils.api import (
    APIBadResponse,
    APICacher,
    APIPaginatorTemplate,
)
from soongo_data.utils.imports import safe_import
from soongo_data.utils.logging_utils import gen_logger

confluent_kafka = safe_import(
    module_name='confluent_kafka',
    min_major_version=2,
    min_minor_version=11,
)


class Strategy(ABC):
    @abstractmethod
    def get_content(
        self,
        url: str,
        logger: Logger,
        params: Optional[dict] = None,
        paginator: Optional[APIPaginatorTemplate] = None,
        response_keys: Sequence[str] = tuple(),
        headers: Optional[dict] = None,
        auth: Optional[requests.auth.HTTPBasicAuth] = None,
        api_cacher: Optional[APICacher] = None,
    ) -> pd.DataFrame:
        """Load data from the API and return a DataFrame."""
        pass


class EventStreamStrategy(Strategy):
    def __init__(self: Self):
        self.stop_event = asyncio.Event()
        if confluent_kafka is None:
            raise ImportError(
                'confluent_kafka is required for EventStreamStrategy. '
                'Please install it with "pip install confluent_kafka>=2.11.0"',
            )

    def get_content(
        self: Self,
        url: str,
        logger: Logger,
        paginator: Optional[APIPaginatorTemplate] = None,
        response_keys: Sequence[str] = tuple(),
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        auth: Optional[requests.auth.HTTPBasicAuth] = None,
        api_cacher: Optional[APICacher] = None,
    ) -> pd.DataFrame:
        return asyncio.run(
            self._process(
                conf=headers,
                timer=params.get('timer', 10),
                topic=url,
                logger=logger,
            )
        )

    def _consume_kafka(
        self: Self,
        conf: Optional[Dict[str, str]],
        topic: str,
        logger: Logger,
        **parsing_params: Dict[str, Any],
    ) -> pd.DataFrame:
        """Consume messages from a Kafka topic and return them as a DataFrame.
        :param conf: Kafka consumer configuration.
        :param topic: Kafka topic to consume messages from.
        :param logger: Logger instance for logging.
        :param parsing_params: Additional parameters for parsing messages.
        :return: DataFrame containing the consumed messages.
        """
        result = list()

        with closing(confluent_kafka.Consumer(conf, logger=logger)) as consumer:
            consumer.subscribe([topic])

            while not self.stop_event.is_set():
                msg = consumer.poll(timeout=1.0)

                if msg is None:
                    continue

                if msg.error():
                    raise confluent_kafka.cimpl.KafkaException(msg.error())
                else:
                    payload = json.loads(msg.value().decode('utf-8'))
                    result.append(payload)
                    consumer.commit(asynchronous=True)

        return pd.DataFrame(result)

    async def _async_timer(
        self: Self,
        seconds: int,
    ) -> None:
        await asyncio.sleep(seconds)
        self.stop_event.set()

    async def _process(
        self: Self,
        conf: Optional[Dict[str, str]],
        timer: int,
        topic: str,
        logger: Logger,
    ) -> pd.DataFrame:
        """Process the Kafka consumer and timer asynchronously.
        This method runs the consumer in a separate thread and uses an
        asyncio task to handle the timer. It returns a DataFrame containing
        the consumed messages. 
        :param conf: Kafka consumer configuration.
        :param timer: Time in seconds to run the consumer before stopping.
        :param topic: Kafka topic to consume messages from.
        :param logger: Logger instance for logging.
        :return: DataFrame containing the consumed messages.
        """
        consumer_task = asyncio.to_thread(
            self._consume_kafka, conf, topic, logger
        )
        timer_task = asyncio.create_task(self._async_timer(timer))
        df, _ = await asyncio.gather(consumer_task, timer_task)

        return df


class HttpStrategy(Strategy):
    def get_content(
        self,
        url: str,
        logger: Logger,
        paginator: Optional[APIPaginatorTemplate] = None,
        response_keys: Sequence[str] = tuple(),
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        auth: Optional[requests.auth.HTTPBasicAuth] = None,
        api_cacher: Optional[APICacher] = None,
    ) -> pd.DataFrame:
        response_items = None

        prep_request = requests.Request(
            method='GET',
            url=url,
            params=params,
            headers=headers,
            auth=auth,
        ).prepare()

        if paginator is None:
            if (api_cacher is not None) and (prep_request.url is not None):
                response_items = api_cacher.fetch_from_cache(
                    prepared_url=prep_request.url,
                )

            if response_items is None:
                with requests.Session() as session:
                    response = session.send(prep_request)

                if response.status_code != 200:
                    logger.error(response)
                logger.info(
                    'Query successful, parsing response and loading into DataFrame',
                )

                response_items = response.json()

                if (api_cacher is not None) and (prep_request.url is not None):
                    api_cacher.push_to_cache(
                        result=response_items,
                        prepared_url=prep_request.url,
                    )

            for response_key in response_keys:
                response_items = response_items[response_key]

            if isinstance(response_items, dict):
                # Prevents Pandas from exploding the dict into multiple rows
                response_items = [response_items]

            df = pd.DataFrame(response_items)
        else:
            df_lst = [
                pd.DataFrame(response)
                for response in paginator.paginate(
                    url=url,
                    params=params,
                    headers=headers,
                    auth=auth,
                )
            ]
            if df_lst:
                df = pd.concat(df_lst, axis=0, ignore_index=True)
            else:
                df = pd.DataFrame()

        return df


class Http11Strategy(Strategy):

    class HTTP11Adapter(HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            ctx = create_urllib3_context()
            ctx.set_alpn_protocols(["http/1.1"])
            kwargs["ssl_context"] = ctx
            return super().init_poolmanager(*args, **kwargs)

        def proxy_manager_for(self, *args, **kwargs):
            ctx = create_urllib3_context()
            ctx.set_alpn_protocols(["http/1.1"])
            kwargs["ssl_context"] = ctx
            return super().proxy_manager_for(*args, **kwargs)

    def get_content(
        self,
        url: str,
        logger: Logger,
        paginator: Optional[APIPaginatorTemplate] = None,
        response_keys: Sequence[str] = tuple(),
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        auth: Optional[requests.auth.HTTPBasicAuth] = None,
        api_cacher: Optional[APICacher] = None,
    ) -> pd.DataFrame:
        response_items = None

        prep_request = requests.Request(
            method='GET',
            url=url,
            params=params,
            headers=headers,
            auth=auth,
        )

        if paginator is None:
            if response_items is None:
                with requests.Session() as session:
                    session.mount('https://', Http11Strategy.HTTP11Adapter())
                    session.mount('http://', Http11Strategy.HTTP11Adapter())

                    prepared = session.prepare_request(prep_request)

                    response = session.send(prepared)

                    if (api_cacher is not None) and (prep_request.url is not None):
                        response_items = api_cacher.fetch_from_cache(prepared_url=prepared.url)

                    if response_items is None:
                        response = session.send(prepared)
                        response_items = response.json()

                if response.status_code != 200:
                    raise APIBadResponse(response)
                logger.info(
                    'Query successful, parsing response and loading into DataFrame',
                )

                response_items = response.json()

                if (api_cacher is not None) and (prep_request.url is not None):
                    api_cacher.push_to_cache(
                        result=response_items,
                        prepared_url=prep_request.url,
                    )

            for response_key in response_keys:
                response_items = response_items[response_key]

            if isinstance(response_items, dict):
                # Prevents Pandas from exploding the dict into multiple rows
                response_items = [response_items]

            df = pd.DataFrame(response_items)
        else:
            df_lst = [
                pd.DataFrame(response)
                for response in paginator.paginate(
                    url=url,
                    params=params,
                    headers=headers,
                    auth=auth,
                )
            ]
            if df_lst:
                df = pd.concat(df_lst, axis=0, ignore_index=True)
            else:
                df = pd.DataFrame()

        return df


def load_from_api(
    organization_name: str,
    url: str,
    col_lst: List[DataColumn],
    record_dates: List[str],
    connector_name: str,
    source_dataset: str,
    source_table: str,
    synchronization_type: str,
    paginator: Optional[APIPaginatorTemplate] = None,
    check_cols: bool = True,
    skip_cols: Optional[List[str]] = None,
    response_keys: Sequence[str] = tuple(),
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
    auth: Optional[requests.auth.HTTPBasicAuth] = None,
    api_cacher: Optional[APICacher] = None,
    strategy: Strategy = HttpStrategy(),
    put_values: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """Fetch data from an api, and return the results as a pandas
    Dataframe.

    :param organization_name: str name of the organization
    :param url: url path string, include base url and route
    :param params: query params provided as a dictionary
    :param headers: query headers as a dictionary
    :param auth: requests auth object if auth not provided in headers
    :param col_lst: list of DataColumns this file contains
    :param record_dates: list of str column names to compute the record
        date from.
    :param synchronization_type: str SynchronizationTypes enum
    :param skip_cols: raw str col name to skip, if any
    :param check_cols: check whether col_lst matches df cols.
    :param connector_name: str name of the connector the data was
        extracted from.
    :param source_dataset: str name of the dataset the data was
        extracted from.
    :param source_table: str name of the table the data was
        extracted from.
    :param api_cacher: APICacher object to cache API responses
    :param paginator: APIPaginatorTemplate object to paginate through
        API responses, if applicable

    :returns: queried data as a pandas DataFrame
    """
    logger = gen_logger('api_loader')
    logger.info(
        'Attempting the query API at url %s',
        url,
    )

    df = strategy.get_content(
        url=url,
        logger=logger,
        paginator=paginator,
        response_keys=response_keys,
        params=params,
        headers=headers,
        auth=auth,
        api_cacher=api_cacher,
    )

    if df.empty:
        return pd.DataFrame(
            columns=[col.name for col in col_lst],
        )

    # API may not return all fields, hence cols are deleted if available
    if skip_cols:
        skip_cols = set(skip_cols).intersection(df.columns)
        df.drop(skip_cols, axis=1, inplace=True)

    check_col_matching(gac_col_lst=col_lst, raw_df=df, logger=logger)

    for table_col in col_lst:
        df.rename(
            columns={table_col.raw_name: table_col.name},
            inplace=True,
        )

    if check_cols:
        df = check_columns(
            df=df,
            col_lst=col_lst,
            organization_name=organization_name,
        )
        df = get_record_date(data_df=df, record_dates=record_dates)
    df = set_record_cols(
        df=df,
        connector_name=connector_name,
        source_dataset=source_dataset,
        source_table=source_table,
        synchronization_type=synchronization_type,
    )

    check_no_dup_values(df.columns)

    if put_values:
        df = df.assign(**put_values)

    return df
