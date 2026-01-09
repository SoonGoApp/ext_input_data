""" Defines the Datasets class"""
import logging
import os
import typing

import pandas as pd

from soongo_data.connectors.__base__.data_source import DataSource
from soongo_data.connectors.__base__.fetch_utils import \
    fetch_organization_connector_params
from soongo_data.utils.aws import s3_list_files
from soongo_data.utils.enums import SynchronizationTypes
from soongo_data.utils.logging_utils import gen_logger


class Dataset:
    """ The Dataset type imports tables in csv format as pandas dataframe as
    cached_properties

    :ivar folder: folder where the csv tables are stored
    :ivar logger: logging logger
    :ivar connector_name: name of the connector the dataset stems from
    :ivar name: string name of the Dataset
    :ivar table_lst: list of table names
    """
    CONNECTOR_NAME: str = None
    NAME: str = None
    TYPE: str = None

    def __init__(
        self,
        connector_folder: str,
        logger: logging.Logger,
        organization_name: str,
        s3_bucket: typing.Optional[str],
        **connector_params,
    ) -> None:
        """ Instantiate datasets and loads folder and logger

        :param folder: string path to the folder containing the csv tables
        :param logger: logging logger
        :param connector_name: name of the connector the dataset stems from
        :param name: string name of the Dataset
        :param s3_bucket: optional string indicating the s3 bucket where the
            data is stored. If None, then the folder path is interpreted as
            a local path
        """
        self.folder = os.path.join(
            connector_folder,
            self.TYPE,  # Additional level not necessary; consider changing
            self.NAME,
        )
        self.logger = logger
        self.table_lst = []
        self.organization_name = organization_name
        self.s3_bucket = s3_bucket
        self.connector_params = connector_params if connector_params else {}

        if s3_bucket:
            try:
                s3_list_files(
                    bucket_name=s3_bucket,
                    prefix=connector_folder,
                    pattern='.*',
                )
            except FileNotFoundError:
                self.logger.error(
                    'Provided connector S3 folder %s is not a valid directory',
                    connector_folder,
                )

        else:
            if not os.path.isdir(os.path.expanduser(connector_folder)):
                self.logger.error(
                    'Provided connector folder %s is not a valid directory',
                    connector_folder,
                )

        for attr_name in ['NAME', 'TYPE', 'CONNECTOR_NAME']:
            if not hasattr(self, attr_name):
                raise AttributeError(
                    f'Dataset must have a {attr_name} attribute but '
                    f'{self.__class__.__name__} {attr_name} is still None'
                )

    def __iter__(self) -> typing.Generator[pd.DataFrame, None, None]:
        """ Turn the class iterable. Only iterate on DataSources."""
        for attr in dir(self):

            attr_value = getattr(self, attr)
            if isinstance(attr_value, type):
                if issubclass(attr_value, DataSource) & (attr_value != DataSource):
                    datasource_class = attr_value(
                        folder=self.folder,
                        logger=self.logger,
                        organization_name=self.organization_name,
                        s3_bucket=self.s3_bucket,
                    )
                    yield datasource_class.parse(**self.connector_params)

    def get(
        self: typing.Self,
        data_source_name: str,
        data_path: typing.Optional[str] = None,
        **parsing_params,
    ) -> pd.DataFrame:
        """ Get the requested DataSource

        :param data_source_name: name of the DataSource to be fetched
        :return: DataSource object
        """
        get_params = self.connector_params | parsing_params
        if hasattr(self, data_source_name):
            return getattr(self, data_source_name)(
                folder=self.folder,
                logger=self.logger,
                organization_name=self.organization_name,
                s3_bucket=self.s3_bucket,
            ).parse(
                data_path,
                **get_params,
            )
        else:
            raise AttributeError(
                f'Dataset {self.NAME} does not have a {data_source_name} '
                'attribute'
            )

    @classmethod
    def local_test(
        cls: typing.Type[typing.Self],
        organization_name: str,
    ) -> None:
        connector_folder = os.path.join(
            os.environ['_soongo_data_folder'],
            organization_name,
            cls.CONNECTOR_NAME,
        )
        connector_params = fetch_organization_connector_params(
            organization_name=organization_name,
        )[cls.CONNECTOR_NAME]
        logger = gen_logger(cls.CONNECTOR_NAME)
        dataset = cls(
            connector_folder=connector_folder,
            organization_name=organization_name,
            logger=logger,
            s3_bucket=None,
            **connector_params
        )
        i = 0
        test_folder = os.environ.get('_soongo_test_folder')
        for df in dataset:
            if test_folder:
                if df is not None:
                    df.to_csv(
                        os.path.join(
                            test_folder,
                            f'{cls.CONNECTOR_NAME}_{dataset.NAME}_{i}.csv',
                        )
                    )
            logger.info(df)
            i += 1


class EmptyDataset(Dataset):
    """
    Stub class of Dataset returned when not available
    """

    NAME = 'EMPTY'
    TYPE = SynchronizationTypes.csv_upload.value

    def __init__(
        self: typing.Self,
        connector_folder: str,
        organization_name: str,
        logger: logging.Logger,
        **connector_params: typing.Dict[str, typing.Any],
    ) -> None:
        """ Empty Dataset class to be used when the connector is not available
        or the folder does not exist
        """
        super().__init__(
            connector_folder=connector_folder,
            logger=logger,
            connector_name='EMPTY',
            organization_name=organization_name,
        )
