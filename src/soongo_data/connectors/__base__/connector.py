""" Defines the Connectors classes"""
import inspect
import os
import typing

from soongo_data import connectors
from soongo_data.connectors.__base__.dataset import Dataset
from soongo_data.connectors.__base__.fetch_utils import \
    fetch_organization_connector_params
from soongo_data.utils.aws import s3_list_files
from soongo_data.utils.imports import lazy_import
from soongo_data.utils.logging_utils import gen_logger


class Connector:
    """
    Connector class to be subclassed by all connectors. It contains
    a collection of datasets and a logger.
    """
    NAME: str = None

    def __init__(
        self,
        folder: str,
        organization_name: str,
        log_file: typing.Optional[str] = None,
        s3_bucket: typing.Optional[str] = None,
        **connector_params,
    ):
        self.logger = gen_logger(
            name=self.__class__.__name__,
            file_path=log_file,
        )
        self.organization_name = organization_name
        self.s3_bucket = s3_bucket

        if self.NAME is None:
            raise AttributeError(
                f'Connector must have a NAME attribute but '
                f'{self.__class__.__name__} NAME is still None'
            )

        self.data_folder = os.path.join(
            os.path.expanduser(folder),
            organization_name,
            self.NAME,
        )
        self.module_folder = os.path.join(
            connectors.__path__[0],
            self.NAME.lower(),
        )
        self.connector_params = fetch_organization_connector_params(
            organization_name=organization_name,
        )[self.NAME]
        self.connector_params.update(connector_params)
        self.dataset_dict = self.fetch_datasets()

    def get(
        self: typing.Self,
        dataset_name: str,
    ) -> Dataset:
        """ Get the requested Dataset

        :param dataset_name: name of the Dataset to be fetched
        :return: Dataset object
        """
        # Log if connector folder not found but do not return
        # as this can be acceptable behavior for API connectors
        if self.s3_bucket:
            try:
                s3_list_files(
                    bucket_name=self.s3_bucket,
                    prefix=self.data_folder,
                    pattern='.*',
                )
            except FileNotFoundError:
                self.logger.warning(
                    f'The provided connector S3 folder {self.data_folder} does not exist'
                )

        if (
            not self.s3_bucket and
            not os.path.isdir(self.data_folder)
        ):
            self.logger.warning(
                f'The provided connector local folder {self.data_folder} does not exist'
            )

        try:
            # Memoization
            if hasattr(self, dataset_name):
                return getattr(self, dataset_name)

            dataset = self.__get__(dataset_name)

            setattr(
                self,
                dataset_name,
                dataset
            )
            return dataset

        except ImportError:
            raise ImportError(
                f'Connector {self.NAME} does not have a {dataset_name} '
                'module to import'
            )

    def __get__(
        self: typing.Self,
        dataset_name: str,
    ) -> Dataset:
        """ Get a Dataset instance from specified dataset name.

        :param dataset_name: name of the Dataset to be fetched
        :param connector_name: name of the Connector to be used

        :return: Dataset class
        """
        dataset_module = self.dataset_dict.get(dataset_name)
        if dataset_module is None:
            raise ImportError(
                f'Connector {self.NAME} does not have a {dataset_name} '
                f'Dataset object to import'
            )

        return dataset_module(
            connector_folder=self.data_folder,
            logger=self.logger,
            organization_name=self.organization_name,
            s3_bucket=self.s3_bucket,
            **self.connector_params,
        )

    def fetch_datasets(self: typing.Self) -> typing.Dict[str, Dataset]:
        """ Import all datasets from the connector

        :return: None
        """
        excluded_files = {'__init__.py', 'utils.py', 'full_data.py'}
        dataset_dict = {}

        # Traverse the folder to collect all Datasets
        for root, _, files in os.walk(self.module_folder):
            for file in files:
                if file.endswith(".py") and file not in excluded_files:
                    module_name = file[:-3]  # Remove the .py extension

                    # Dynamically import the module
                    module = lazy_import(
                        f'soongo_data.connectors.{self.NAME.lower()}.'
                        f'{module_name}'
                    )

                    # Inspect the module for classes
                    for _, obj in inspect.getmembers(module, inspect.isclass):
                        # Check if the object is a subclass of the parent class
                        if issubclass(obj, Dataset) and obj != Dataset:
                            dataset_dict[obj.NAME] = obj

        return dataset_dict

    def __iter__(self) -> typing.Generator[Dataset, None, None]:
        """ Turn the class iterable. Only iterate on Datasets."""
        for dataset_name in self.dataset_dict:
            yield self.get(dataset_name)

    @classmethod
    def local_test(
        cls: typing.Type[typing.Self],
        organization_name: str,
    ) -> None:
        """ Local test method to be used for testing the connector locally.

        :param organization_name: name of the organization
        :param connector_name: name of the connector
        """
        connector = cls(
            folder=os.environ['_soongo_data_folder'],
            organization_name=organization_name,
            s3_bucket=None,
        )
        i = 0
        test_folder = os.environ.get('_soongo_test_folder')
        for dataset in connector:
            for df in dataset:
                if test_folder:
                    df.to_csv(
                        os.path.join(
                            test_folder,
                            f'{connector.NAME}_{i}.csv',
                        ),
                        index=False,
                    )
                i += 1
                print(df)
