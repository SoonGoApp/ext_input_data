""" Connectors full data"""
import os
from functools import cached_property
from typing import Optional, Union, Dict, Any
from uuid import uuid4

import pandas as pd

from soongo_data.connectors.__base__.connector import Dataset, Connector
from soongo_data.connectors.__base__.fetch_utils import \
    fetch_organization_connector_params
from soongo_data.utils.aws import s3_list_files
from soongo_data.utils.imports import import_child_class_from_path


class ConnectorData:
    """ Class collecting data from all different connectors"""

    def __init__(
        self,
        root_folder: str,
        organization_name: str,
        log_file: Optional[str] = None,
        s3_bucket: Optional[str] = None,
        organization_connector_params: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        """ Instantiate Connectors class with all Connectors data

        :param root_folder: path to the folder containing all connectors data;
        either a local path of an S3 bucket patch
        :param log_file: path to a log file
        """
        self.log_file = log_file
        self.organization_name = organization_name
        self.s3_bucket = s3_bucket
        self.root_folder = root_folder

        default_organization_connector_params = fetch_organization_connector_params(
            organization_name=organization_name,
        )
        if organization_connector_params:
            for connector_name, value in organization_connector_params.items():
                default_organization_connector_params[connector_name] |= value
        self.connector_params = default_organization_connector_params

        if s3_bucket:
            try:
                s3_list_files(
                    bucket_name=s3_bucket,
                    prefix=root_folder,
                    pattern='.*',
                )
            except FileNotFoundError:
                raise FileNotFoundError(
                    f'The provided root folder {root_folder} does not exist'
                )

        elif not s3_bucket and not os.path.isdir(root_folder):
            raise FileNotFoundError(
                f'The provided root folder {root_folder} does not exist'
            )

        # Lazy memoization: first set attributes names as None, fetch actual
        # object only if required by a get call.
        for connector in self.connector_params:
            setattr(
                self,
                connector,
                None
            )

    def get(
        self,
        connector_name: str,
        dataset_name: Optional[str] = None,
        table_name: Optional[str] = None,
    ) -> Union[Dataset, pd.DataFrame]:
        """ Get requested Dataset or table

        :param connector_name: name of the connector the data needs to be
        fetched from.
        :param dataset_name: name of the dataset the data needs to be fetched
        from.
        :param table_name: name of the table the data needs to be fetched from.

        :raises ValueError: if any of the passed connector, dataset, or table
        name does not exist.

        :returns: Connector, Dataset, or table, depending on whether only
        a connector name, connector and dataset name, or connector, dataset,
        and table_name were passed.
        """
        if connector_name not in self.connector_params:
            raise ValueError(
                f'Passed {connector_name} value is not a valid connector name'
            )

        connector = getattr(
            self,
            connector_name,
        )
        # Lazy memoization: do not load connector data at init, only if
        # fetching data for that connector
        if connector is None:
            connector_classes = import_child_class_from_path(
                path=f'soongo_data.connectors.{connector_name.lower()}.full_data',
                parent_class=Connector,
            )
            assert len(connector_classes) == 1, (
                f'Connector {connector_name} has more than one connector '
                'class in the full_data module. Please check the module.'
            )
            connector_class = connector_classes[0]
            connector = connector_class(
                folder=self.root_folder,
                log_file=self.log_file,
                organization_name=self.organization_name,
                s3_bucket=self.s3_bucket,
                **self.connector_params[connector_name],
            )
            setattr(
                self,
                connector_name,
                connector,
            )

        if dataset_name is None and table_name is None:
            return connector

        if dataset_name is None:
            raise ValueError(
                'Cannot pass no dataset_name and a table_name. '
                'Please pass a dataset_name or set table_name to None.'
            )

        try:
            dataset = connector.get(dataset_name)
        except AttributeError:
            raise ValueError(
                f'Passed dataset name {dataset_name} does not exist in '
                f'connector {connector_name}'
            )
        assert isinstance(dataset, Dataset)
        if table_name is None:
            return dataset

        try:
            return dataset.get(table_name)
        except AttributeError:
            raise ValueError(
                f'Passed table name {table_name} does not exist in '
                f'dataset {dataset_name} of connector {connector_name}'
            )

    def __iter__(self):
        for source in self.connector_params:
            yield self.get(source)

    @cached_property
    def synchronisation_id_dict(self):
        return {
            connector_name: str(uuid4())
            for connector_name in self.connector_params
        }


if __name__ == '__main__':
    connector_data = ConnectorData(
        root_folder=os.environ['_soongo_data_folder'],
        organization_name='acorus',
    )
    for source in connector_data:
        for element in source:
            if isinstance(element, Dataset):
                for df in element:
                    print(df)

            else:
                print(element)
