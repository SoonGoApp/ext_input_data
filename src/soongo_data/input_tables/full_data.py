""" Connectors full data"""
import os
from functools import cached_property
from typing import Optional, Union
from uuid import uuid4

import pandas as pd
import yaml

# Gotta import every connector for the connector_dict to populate
# TODO: think about a system where this wouldn't be necessary
from soongo_data.connectors.acorus.full_data import AcorusData  # NOQA
from soongo_data.connectors.ayvens.full_data import AyvensData  # NOQA
from soongo_data.connectors.alphabet.full_data import AlphabetData  # NOQA
from soongo_data.connectors.api_plaque.full_data import ApiPlaqueData  # NOQA
from soongo_data.connectors.arval.full_data import ArvalData  # NOQA
from soongo_data.connectors.athlon.full_data import AthlonData  # NOQA
from soongo_data.connectors.as24.full_data import AS24Data  # NOQA
from soongo_data.connectors.bpce.full_data import BPCEData  # NOQA
from soongo_data.connectors.chargemap.full_data import ChargeMapData  # NOQA
from soongo_data.connectors.concur.full_data import ConcurData  # NOQA
from soongo_data.connectors.dentmaster.full_data import DentMasterData  # NOQA
from soongo_data.connectors.domino.full_data import DominoData  # NOQA
from soongo_data.connectors.easypark.full_data import EasyparkData  # NOQA
from soongo_data.connectors.edenred.full_data import EdenredData  # NOQA
from soongo_data.connectors.euromaster.full_data import EuromasterData  # NOQA
from soongo_data.connectors.flease.full_data import FleaseData  # NOQA
from soongo_data.connectors.fleetnote.full_data import FleetNoteData  # NOQA
from soongo_data.connectors.flowbird.full_data import FlowbirdData  # NOQA
from soongo_data.connectors.fraikin.full_data import FraikinData  # NOQA
from soongo_data.connectors.gac.full_data import GacData  # NOQA
from soongo_data.connectors.gan.full_data import GANData  # NOQA
from soongo_data.connectors.gba.full_data import GBAData  # NOQA
from soongo_data.connectors.greenncap.full_data import GreenNCapData  # NOQA
from soongo_data.connectors.greenway.full_data import GreenwayData  # NOQA
from soongo_data.connectors.havas.full_data import HavasData  # NOQA
from soongo_data.connectors.holson.full_data import HolsonData  # NOQA
from soongo_data.connectors.loc_action.full_data import LocActionData  # NOQA
from soongo_data.connectors.lucca.full_data import LuccaData  # NOQA
from soongo_data.connectors.masternaut.full_data import MasternautData  # NOQA
from soongo_data.connectors.mon_petit_carrossier.full_data import \
    MonPetitCarrossierData  # NOQA
from soongo_data.connectors.norauto.full_data import NorautoData  # NOQA
from soongo_data.connectors.notilus.full_data import NotilusData  # NOQA
from soongo_data.connectors.pay_by_phone.full_data import \
    PayByPhoneData  # NOQA
from soongo_data.connectors.quartus.full_data import QuartusData  # NOQA
from soongo_data.connectors.yanet.full_data import YanetData  # NOQA
from soongo_data.connectors.sambms.full_data import SamBmsData  # NOQA
from soongo_data.connectors.smabtp.full_data import SmaBtpCsvData  # NOQA
from soongo_data.connectors.speedy.full_data import SpeedyData  # NOQA
from soongo_data.connectors.total.full_data import TotalData  # NOQA
from soongo_data.connectors.zeplug.full_data import ZeplugData  # NOQA
from soongo_data.utils.aws import s3_list_files


class ConnectorData:
    """ Class collecting data from all different connectors"""

    def __init__(
        self,
        root_folder: str,
        organization_name: str = 'quartus',
        log_file: Optional[str] = None,
        config_file: Optional[str] = None,
        s3_bucket: Optional[str] = None,
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
        if config_file is None:
            config_file = os.path.join(
                os.path.dirname(os.path.realpath(__file__)),
                'connector_config.yaml',
            )
        with open(config_file) as config_path:
            self.connector_param_dict = yaml.safe_load(
                config_path
            )[organization_name]

        if self.s3_bucket:
            try:
                s3_list_files(
                    bucket_name=self.s3_bucket,
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
        for connector in self.connector_param_dict:
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
        if connector_name not in self.connector_param_dict:
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
            connector = connector_dict[connector_name](
                folder=self.root_folder,
                log_file=self.log_file,
                organization_name=self.organization_name,
                s3_bucket=self.s3_bucket,
                **self.connector_param_dict[connector_name],
            )
            setattr(
                self,
                connector_name,
                connector,
            )

        if dataset_name is None and table_name is None:
            return connector

        if isinstance(connector, Dataset):
            if table_name is None:
                return connector

            try:
                return getattr(
                    connector,
                    table_name,
                )
            except AttributeError:
                raise ValueError(
                    f'Passed table_name {table_name} does not exist in '
                    f'connector {connector_name}'
                )

        if dataset_name is None:
            raise ValueError(
                'Cannot pass no dataset_name - queried connector '
                f'{connector_name} contains multiple datasets'
            )

        try:
            dataset = getattr(connector, dataset_name)
        except AttributeError:
            raise ValueError(
                f'Passed dataset name {dataset_name} does not exist in '
                f'connector {connector_name}'
            )
        assert isinstance(dataset, Dataset)
        if table_name is None:
            return dataset

        try:
            return getattr(dataset, table_name)
        except AttributeError:
            raise ValueError(
                f'Passed table name {table_name} does not exist in '
                f'dataset {dataset_name} of connector {connector_name}'
            )

    def __iter__(self):
        for source in self.connector_param_dict:
            yield self.get(source)

    @cached_property
    def synchronisation_id_dict(self):
        return {
            connector_name: str(uuid4())
            for connector_name in self.connector_param_dict.keys()
        }


if __name__ == '__main__':
    connector_data = ConnectorData(
        root_folder='/home/matthieuglotz/Documents/Data/soongo-local',
        organization_name='acorus',
    )
    for source in connector_data:
        for element in source:
            if isinstance(element, Dataset):
                for df in element:
                    print(df)

            else:
                print(element)
