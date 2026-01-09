import os
import re
import typing
import logging

import numpy as np
import pandas as pd
import sqlalchemy as sa
import yaml

from soongo_data.data_models import VehiclesModel
from soongo_data.sql_mappings import VehicleBrandsTable, VehicleModelsTable
from soongo_data.utils.db import gen_engine
from soongo_data.utils.type import str_is_nan
from soongo_data.utils.aws import s3_get_most_recent_file, s3_list_files


def list_matching_files(
    target_folder: str,
    pattern: typing.Pattern,
    s3_bucket: typing.Optional[str] = None,
) -> typing.List[str]:
    """ List files matching a specific pattern in a target folder

    :param target_folder: folder to get the file from
    :param pattern: regular expression the file name needs to match

    :returns: list of files matching the pattern
    """
    if s3_bucket:
        return s3_list_files(
            bucket_name=s3_bucket,
            prefix=target_folder,
            pattern=pattern,
        )

    elif not os.path.isdir(os.path.expanduser(target_folder)):
        raise ValueError(
            f'The provided target_folder argument is not a valid directory '
            f'{target_folder}'
        )

    matching_files = [
        os.path.join(target_folder, file_name)
        for file_name in os.listdir(target_folder)
        if re.match(pattern, file_name)
    ]

    if not matching_files:
        raise FileNotFoundError(
            f'No file matching the provided pattern file name in the target '
            f'folder: {target_folder}'
        )
    return matching_files


def get_latest_file(
    target_folder: str,
    pattern: typing.Pattern,
    s3_bucket: typing.Optional[str] = None,
) -> str:
    """ Get latest file matching a specific patter in a target folder

    :param target_folder: folder to get the file from
    :param pattern: regular expression the file name needs to match

    :raises ValueError: if the provided target folder argument is not a valid
    directory or if several files matching the pattern have the same most
    recent update time

    :returns: path to the latest file
    """
    if s3_bucket:
        return s3_get_most_recent_file(
            bucket_name=s3_bucket,
            prefix=target_folder,
            pattern=pattern,
        )

    elif not os.path.isdir(os.path.expanduser(target_folder)):
        raise ValueError(
            f'The provided target_folder argument is not a valid directory '
            f'{target_folder}'
        )
    matching_files = [
        os.path.join(target_folder, file_name)
        for file_name in os.listdir(target_folder)
        if re.match(pattern, file_name) and os.path.isfile(
            os.path.join(target_folder, file_name)
        )
    ]

    if not matching_files:
        raise FileNotFoundError(
            f'No file matching the provided pattern file name in the target '
            f'folder: {target_folder}'
        )

    update_times = [
        os.path.getmtime(file_path) for file_path in matching_files
    ]
    most_recent_time = np.max(update_times)
    most_recent_files = [
        matching_files[index] for index in range(len(update_times))
        if update_times[index] == most_recent_time
    ]
    if len(most_recent_files) == 1:
        return most_recent_files[0]

    else:
        raise ValueError(
            f'File matching the provided pattern file name are tied in terms'
            f'of update time: {most_recent_files}'
        )


def fetch_organization_connector_params(
    organization_name: str,
) -> typing.Dict[str, typing.Any]:
    """ Fetch the connector parameters from the config file

    :param organization_name: name of the organization to fetch the
    connector parameters for
    :return: dictionary containing the connector parameters
    """
    config_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
        'connector_config.yaml',
    )
    with open(config_file) as config_path:
        connector_params = yaml.safe_load(
            config_path
        )

    if organization_name not in connector_params:
        raise ValueError(
            f'Organization {organization_name} does not exist in the '
            f'configuration file'
        )

    return connector_params[organization_name]


def fetch_make_from_model(
    df: pd.DataFrame,
    logger: logging.Logger,
) -> pd.DataFrame:
    """ Fetch columns of interest from the vehicle table

    :param df: Pandas DataFrame to enrich. Must have either plate_number or
    employee_id
    :param cols_to_fetch: list of columns to fetch. Must be among vehicle_table
    columns.
    :param connector_data: Connector Data with all data for the organisation

    :return: enriched df with additional columns
    """
    if VehiclesModel.model.name not in df.columns:
        raise ValueError(
            'Vehicle model must be provided'
        )
    if VehiclesModel.make.name not in df.columns:
        df[VehiclesModel.make.name] = pd.NA

    db_engine = gen_engine(database_url=os.environ['DATABASE_URL'])
    with db_engine.connect() as connection:
        model_df = pd.read_sql(
            sql=sa.select(
                VehicleModelsTable.name.label(VehiclesModel.model.name),
                VehicleBrandsTable.name.label('temp_make'),
            ).select_from(
                VehicleModelsTable,
            ).outerjoin(
                VehicleBrandsTable,
                VehicleModelsTable.brand_id == VehicleBrandsTable.id,
            ),
            con=connection,
        )

    model_df = model_df[
        ~model_df[VehiclesModel.model.name].duplicated(keep=False)
    ]

    df = df.merge(
        model_df,
        on=VehiclesModel.model.name,
        how='left',
        validate='m:1',
        indicator='_models_merge',
    )
    missing_models = df.loc[
        ~str_is_nan(df[VehiclesModel.model.name])
        & (df['_models_merge'] == 'left_only'),
        VehiclesModel.model.name,
    ].unique()
    if missing_models.any():
        logger.warning(
            '%d out of %d models are missing in database:  %s',
            len(missing_models),
            len(df[VehiclesModel.model.name].unique()),
            missing_models,
        )

    df[VehiclesModel.make.name] = df[VehiclesModel.make.name].mask(
        str_is_nan(df[VehiclesModel.make.name]),
        df['temp_make'],
    )

    df.drop(
        columns=['_models_merge', 'temp_make'],
        inplace=True,
    )
    return df
