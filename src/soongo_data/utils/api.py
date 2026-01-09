import logging
import os
import typing
from abc import ABC, abstractmethod

import requests
import sqlalchemy as sa

from soongo_data.sql_mappings import ExternalApiCache
from soongo_data.utils.db import gen_session, get_organization_id
from soongo_data.utils.typing_utils import JSONType


class APICacher:

    def __init__(
        self: typing.Self,
        logger: logging.Logger,
        org_slug: typing.Optional[str] = None,
    ):
        """ Initialize the API Cacher

        :param logger: logger instance to log messages
        """
        self.logger = logger
        self.organization_id = get_organization_id(
            organization_name=org_slug,
            database_url=os.environ['DATABASE_URL']
        ) if org_slug else None

    def fetch_from_cache(
        self: typing.Self,
        prepared_url: str,
    ) -> JSONType:
        self.logger.info(
            'Attempting to fetch cached response'
        )
        with gen_session(database_url=os.environ['DATABASE_URL']) as session:
            where_conds = [
                ExternalApiCache.url == self.sanitize_url(prepared_url)
            ]
            if self.organization_id:
                where_conds.append(
                    ExternalApiCache.organization_id == self.organization_id
                )
            else:
                where_conds.append(
                    ExternalApiCache.organization_id.is_(None)
                )
            cache_query = sa.select(
                ExternalApiCache.result
            ).select_from(ExternalApiCache).where(
                *where_conds
            )
            result = session.execute(cache_query).scalar()
            if result is not None:
                self.logger.info(
                    'Found cached response',
                )

            return result

    @staticmethod
    def sanitize_url(
        url: str,
    ) -> str:
        """ Sanitize the URL by removing query parameters.
        This method can be overridden to implement custom sanitization logic.

        :param url: URL to sanitize
        :returns: sanitized URL
        """
        return url

    def push_to_cache(
        self: typing.Self,
        result: JSONType,
        prepared_url: str,
    ) -> None:
        """ Push the result to the cache.
        :param result: result to cache
        :param prepared_url: URL to cache the result for
        :raises ValueError: if the result is None
        """
        self.logger.info(
            'Attempting to fetch cached response'
        )
        with gen_session(database_url=os.environ['DATABASE_URL']) as session:
            new_cache_entry = ExternalApiCache(
                url=self.sanitize_url(prepared_url),
                organization_id=self.organization_id,
                result=result,
            )
            session.add(new_cache_entry)
            try:
                session.commit()
            except sa.exc.IntegrityError:
                self.logger.warning(
                    'Cache entry already exists for url %s; updating result',
                    prepared_url,
                )

                session.rollback()


class APIPaginatorTemplate(ABC):

    @abstractmethod
    def paginate(
        self: typing.Self,
        url: str,
        params: dict,
        headers: dict,
        auth: requests.auth.HTTPBasicAuth,
    ) -> typing.Generator[dict, None, None]:
        pass


class APIOffsetPaginator(APIPaginatorTemplate):
    """
    Offset based API Paginator
    """

    def __init__(
        self,
        item_keys: typing.Collection[str],
        index_key: str,
        nb_items_limit: int,
        logger: logging.Logger,
        limit_key: typing.Optional[str] = None,
        start_index: int = 0,
    ):
        """ Class handling API Pagination if any.

        :param type: APIPaginationType e.g. offset, page, cursor, key
        :param item_keys: tuple of keys to access the items in the response
        :param page_limit: integer number of items returned per page
        :param page_key: str param to pass to the json response to obtain the 
            page index. Applicable to APIPaginationType.page
        :param page_limit_param_name: limit parameter name.
        :param page_limit: number of items to return per query.
        :param start_index: start page index. Applicable to APIPaginationType.page
        """
        self.logger = logger
        self.item_keys = item_keys
        self.index_key = index_key
        self.limit_key = limit_key
        self.nb_items_limit = nb_items_limit
        self.start_index = start_index

    def paginate(
        self: typing.Self,
        url: str,
        params: dict,
        headers: dict,
        auth: requests.auth.HTTPBasicAuth,
    ) -> typing.Generator[dict, None, None]:
        """ Paginate through the API and yield the response as a dictionary

        :param url: url path string, include base url and route
        :param params: query params provided as a dictionary
        :param headers: query headers as a dictionary
        :param auth: requests auth object if auth not provided in headers

        :returns: generator of response dictionaries
        """
        if params is None:
            params = {}
        if self.limit_key is not None:
            params[self.limit_key] = self.nb_items_limit
        params[self.index_key] = self.start_index
        nb_items = self.nb_items_limit
        while nb_items == self.nb_items_limit:
            response = requests.get(
                url=url,
                params=params,
                headers=headers,
                auth=auth,
            ).json()
            for item_key in self.item_keys:
                response = response[item_key]
            nb_items = len(response)
            if nb_items > 0:
                self.logger.debug(
                    (
                        'Loaded %d items from page %d'
                    ),
                    nb_items,
                    params[self.index_key],
                )
                params[self.index_key] += self.nb_items_limit
                yield response


class APIPagePaginator(APIPaginatorTemplate):
    """
    Page-based API Paginator
    """

    def __init__(
        self,
        item_keys: typing.Collection[str],
        page_key: str,
        page_size: int,
        logger: logging.Logger,
        page_size_key: typing.Optional[str] = None,
        start_page: int = 1,
    ):
        """ Class handling API Pagination for page-based APIs.

        :param item_keys: tuple of keys to access the items in the response
        :param page_key: str param to pass to the JSON response to obtain the page index
        :param nb_items_limit: number of items to return per query
        :param logger: logger instance for logging
        :param limit_key: limit parameter name (optional)
        :param start_page: starting page index (default is 1)
        """
        self.logger = logger
        self.item_keys = item_keys
        self.page_key = page_key
        self.page_size_key = page_size_key
        self.page_size = page_size
        self.start_page = start_page

    def paginate(
        self: typing.Self,
        url: str,
        params: dict,
        headers: dict,
        auth: requests.auth.HTTPBasicAuth,
    ) -> typing.Generator[dict, None, None]:
        """ Paginate through the API and yield the response as a dictionary.

        :param url: URL path string, including base URL and route
        :param params: Query params provided as a dictionary
        :param headers: Query headers as a dictionary
        :param auth: Requests auth object if auth is not provided in headers

        :returns: Generator of response dictionaries
        """
        if params is None:
            params = {}
        if self.page_size_key is not None:
            params[self.page_size_key] = self.page_size
        params[self.page_key] = self.start_page
        current_page = self.start_page

        while True:
            response = requests.get(
                url=url,
                params=params,
                headers=headers,
                auth=auth,
            )
            response = response.json()

            # Navigate through the response to extract items
            for item_key in self.item_keys:
                response = response[item_key]

            nb_items = len(response)
            if nb_items == 0:
                self.logger.debug("No more items to fetch. Stopping pagination.")
                break

            self.logger.debug(
                "Loaded %d items from page %d",
                nb_items,
                current_page,
            )

            yield response

            if nb_items < self.page_size:
                self.logger.debug("Last page reached. Stopping pagination.")
                break

            # Move to the next page
            current_page += 1
            params[self.page_key] = current_page


class APIBadResponse(Exception):

    def __init__(self: typing.Self, response: requests.Response):
        message = (
            f'Status code: {response.status_code}, reason: {response.reason} '
            f'text: {response.text}'
        )
        super().__init__(self, message)
