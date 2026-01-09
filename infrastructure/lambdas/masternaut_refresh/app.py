import json
import logging
import os
import requests
from functools import lru_cache

import pandas as pd
import pytz
import sqlalchemy as sa

from soongo_data.sql_mappings import (
    VehiclesTable, OrganizationsTable, VehicleAttributionsTable,
    CollaboratorsTable, CollaboratorConnectorIdsTable,
    VehicleConnectorIdsTable, ConnectorsTable, BusinessUnitConnectorIdsTable
)
from soongo_data.utils.aws import get_aws_secret
from soongo_data.utils.db import gen_engine
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.type import scalar_is_nan, series_is_nan


PROD_SECRETS = get_aws_secret(secret_name='prod-workers-secrets')
MASTERNAUT_BASE_URL = 'https://api.masternautconnect.com/connect-webservices/services/public/v1/customer/'


def main(
    org_slug: str,
    engine: sa.engine.Engine,
    logger: logging.Logger,
) -> None:
    """ Fetches latest associations in db and commits them to Masternaut via API

    :param org_slug: slug of the organization to do the changes for
    :param engine: sqlalchemy engine
    :param commit_changes: whether to commit changes to Masternaut.
    """

    association_df = get_association_df(
        engine=engine,
        org_slug=org_slug,
    )

    current_time = pd.Timestamp.now(tz=pytz.timezone('Europe/Paris'))
    associations_to_commit = association_df[
        (association_df['collaborator_rank'] == 1) &
        (association_df['vehicle_rank'] == 1) &
        (association_df['defaultVehicleId'] != association_df['vehicle_connector_id']) &
        (association_df['date_to'].fillna(current_time) >= current_time)
    ]
    logger.info(
        'Found %s associations to correct on Masternaut',
        len(associations_to_commit),
    )

    for _, association in associations_to_commit.iterrows():
        update_association_masternaut(
            vehicle_connector_id=association['vehicle_connector_id'],
            plate_number=association['plate_number'],
            collaborator_id=association['collaborator_id'],
            collaborator_connector_id=association['collaborator_connector_id'],
            soongo_collab_reference=association['soongo_collab_reference'],
            customer_id=association['customer_id'],
            business_unit_connector_id=association['business_unit_connector_id'],
            default_vehicle_id=association['defaultVehicleId'],
            default_driver_id=association['defaultDriverId'],
            org_slug=org_slug,
            logger=logger,
        )

    vehicle_to_unlink = association_df.loc[
        (association_df['vehicle_rank'] == 1) &
        series_is_nan(association_df['collaborator_id']) &
        ~series_is_nan(association_df['defaultDriverId'])
    ]
    logger.info('Found %s vehicles to unlink', len(vehicle_to_unlink))
    for _, association in vehicle_to_unlink.iterrows():
        if scalar_is_nan(association['customer_id']):
            logger.error('Vehicle %s has no customer id', association['plate_number'])
            continue

        if scalar_is_nan(association['vehicle_connector_id']):
            logger.error('Vehicle %s has no connector id', association['plate_number'])
            continue

        unlink_collaborator_vehicle_masternaut(
            customer_id=association['customer_id'],
            soongo_collab_reference='unspecified',
            default_vehicle_id=association['vehicle_connector_id'],
            collaborator_connector_id=association['defaultDriverId'],
            org_slug=org_slug,
            logger=logger,
        )

    # Correct vehicle groups
    vehicles_wrong_groups = association_df[
        (association_df['collaborator_rank'] == 1) &
        (association_df['vehicle_rank'] == 1) &
        (association_df['vehicle_group_id'] != association_df['business_unit_connector_id']) &
        (association_df['date_to'].fillna(current_time) >= current_time) &
        ~series_is_nan(association_df['business_unit_connector_id'])
    ]
    logger.info(
        'Found %s vehicles with an incorrect group on Masternaut',
        len(vehicles_wrong_groups),
    )
    for _, vehicle in vehicles_wrong_groups.iterrows():
        if scalar_is_nan(vehicle['vehicle_connector_id']):
            logger.error(
                f'Vehicle {vehicle["plate_number"]} has no connector id'
            )
            continue

        attribute_vehicle_to_group_masternaut(
            customer_id=vehicle['customer_id'],
            vehicle_connector_id=vehicle['vehicle_connector_id'],
            business_unit_connector_id=vehicle['business_unit_connector_id'],
            plate_number=vehicle['plate_number'],
            org_slug=org_slug,
            logger=logger,
        )

    # For collaborators fetch a new df as collaborators can be in multiple
    # accounts simultaneously
    collaborator_df = get_collaborator_group_df(
        engine=engine,
        org_slug=org_slug,
    )
    collaborators_wrong_groups = collaborator_df[
        (collaborator_df['collaborator_group_id'] != collaborator_df['business_unit_connector_id']) &
        ~series_is_nan(collaborator_df['business_unit_id']) &
        ~series_is_nan(collaborator_df['collaborator_connector_id']) &
        ~series_is_nan(collaborator_df['business_unit_connector_id'])
    ]
    logger.info(
        'Found %s collaborators with an incorrect group on Masternaut',
        len(collaborators_wrong_groups),
    )
    for _, collaborator in collaborators_wrong_groups.iterrows():

        try:
            attribute_collaborator_to_group_masternaut(
                customer_id=collaborator['customer_id'],
                soongo_collab_reference=collaborator['soongo_collab_reference'],
                business_unit_connector_id=collaborator['business_unit_connector_id'],
                collaborator_connector_id=collaborator['collaborator_connector_id'],
                org_slug=org_slug,
                logger=logger,
            )
        except ValueError as e:
            logger.error(
                'Error on linking collaborator %s, masternaut id %s to masternaut group %s: %s',
                collaborator['soongo_collab_reference'],
                collaborator['collaborator_connector_id'],
                collaborator['business_unit_connector_id'],
                e,
                stack_info=True,
                exc_info=True,
            )
            continue


def get_association_df(
    engine: sa.Engine,
    org_slug: str,
) -> pd.DataFrame:
    with engine.connect() as connection:
        masternaut_connector_id = connection.execute(
            sa.select(ConnectorsTable.id).where(ConnectorsTable.name == 'MASTERNAUT')
        ).scalar()

        latest_association = sa.select(
            OrganizationsTable.id.label('organization_id'),
            CollaboratorsTable.soongo_collab_reference,
            CollaboratorsTable.id.label('collaborator_id'),
            sa.func.coalesce(
                VehicleAttributionsTable.business_unit_id,
                CollaboratorsTable.business_unit_id,
            ).label('business_unit_id'),
            CollaboratorConnectorIdsTable.collaborator_connector_id,
            VehiclesTable.plate_number,
            VehiclesTable.id.label('vehicle_id'),
            VehicleConnectorIdsTable.vehicle_connector_id,
            VehicleConnectorIdsTable.add_params['customerId'].label('customer_id'),
            BusinessUnitConnectorIdsTable.business_unit_connector_id,
            VehicleAttributionsTable.date_from,
            VehicleAttributionsTable.date_to,
            sa.func.rank().over(
                partition_by=CollaboratorsTable.soongo_collab_reference,
                order_by=[
                    VehicleAttributionsTable.date_from.desc(),
                    VehicleAttributionsTable.id.asc()
                ],
            ).label('collaborator_rank'),
            sa.func.rank().over(
                partition_by=VehiclesTable.plate_number,
                order_by=[
                    VehicleAttributionsTable.date_from.desc(),
                    VehicleAttributionsTable.id.asc(),
                ],
            ).label('vehicle_rank')
        ).select_from(
            VehicleAttributionsTable
        ).join(
            VehiclesTable,
            VehiclesTable.id == VehicleAttributionsTable.vehicle_id,
        ).outerjoin(
            CollaboratorsTable,
            CollaboratorsTable.id == VehicleAttributionsTable.collaborator_id,
        ).outerjoin(
            VehicleConnectorIdsTable,
            sa.and_(
                VehicleConnectorIdsTable.vehicle_id == VehiclesTable.id,
                VehicleConnectorIdsTable.connector_id == masternaut_connector_id,
            )
        ).outerjoin(
            CollaboratorConnectorIdsTable,
            sa.and_(
                CollaboratorConnectorIdsTable.collaborator_id == CollaboratorsTable.id,
                CollaboratorConnectorIdsTable.add_params['customerId'] == VehicleConnectorIdsTable.add_params['customerId'],
                CollaboratorConnectorIdsTable.connector_id == masternaut_connector_id,
            )
        ).outerjoin(
            BusinessUnitConnectorIdsTable,
            sa.and_(
                sa.func.coalesce(
                    VehicleAttributionsTable.business_unit_id,
                    CollaboratorsTable.business_unit_id,
                ) == BusinessUnitConnectorIdsTable.business_unit_id,
                BusinessUnitConnectorIdsTable.connector_id == masternaut_connector_id,
                BusinessUnitConnectorIdsTable.add_params['customerId'] == VehicleConnectorIdsTable.add_params['customerId'],
            )
        ).join(
            OrganizationsTable,
            OrganizationsTable.id == VehiclesTable.organization_id,
        ).where(
            sa.func.coalesce(
                VehicleAttributionsTable.date_to,
                sa.func.current_date()
            ) >= sa.func.current_date(),
            OrganizationsTable.slug == org_slug,
        )

        association_df = pd.read_sql(latest_association, engine)
        driver_df = masternaut_get(endpoint='driver', org_slug=org_slug)
        driver_df = driver_df.rename(
            columns={
                'id': 'collaborator_connector_id',
                'groupId': 'collaborator_group_id',
            }
        )
        driver_df = driver_df[
            [
                'customer_id',
                'collaborator_connector_id',
                'defaultVehicleId',
                'collaborator_group_id',
            ]
        ]
        vehicle_df = masternaut_get(endpoint='vehicle', org_slug=org_slug)
        vehicle_df = vehicle_df.rename(
            columns={
                'id': 'vehicle_connector_id',
                'groupId': 'vehicle_group_id',
            }
        )
        vehicle_df = vehicle_df[
            [
                'customer_id',
                'vehicle_connector_id',
                'defaultDriverId',
                'vehicle_group_id',
            ]
        ]
        association_df = association_df.merge(
            driver_df,
            on=['customer_id', 'collaborator_connector_id'],
            how='left',
            validate='m:1',  # Some collaborator_connector_ids are missing
        )
        association_df = association_df.merge(
            vehicle_df,
            on=['customer_id', 'vehicle_connector_id'],
            how='left',
            validate='m:1',  # Some vehicle_connector_ids are missing
        )

        return association_df


def get_collaborator_group_df(
    engine: sa.Engine,
    org_slug: str,  
) -> pd.DataFrame:
    with engine.connect() as connection:
        masternaut_connector_id = connection.execute(
            sa.select(ConnectorsTable.id).where(ConnectorsTable.name == 'MASTERNAUT')
        ).scalar()

        collaborator_query = sa.select(
            CollaboratorsTable.soongo_collab_reference,
            CollaboratorsTable.id.label('collaborator_id'),
            CollaboratorsTable.business_unit_id,
            CollaboratorConnectorIdsTable.collaborator_connector_id,
            CollaboratorConnectorIdsTable.add_params['customerId'].label('customer_id'),
            BusinessUnitConnectorIdsTable.business_unit_connector_id,
        ).select_from(
            CollaboratorsTable,
        ).outerjoin(
            CollaboratorConnectorIdsTable,
            sa.and_(
                CollaboratorConnectorIdsTable.collaborator_id == CollaboratorsTable.id,
                # Here we accept to fetch multiple ids for the same collaborator
                # across the different customerIds
                CollaboratorConnectorIdsTable.connector_id == masternaut_connector_id,
            )
        ).outerjoin(
            BusinessUnitConnectorIdsTable,
            sa.and_(
                CollaboratorsTable.business_unit_id == BusinessUnitConnectorIdsTable.business_unit_id,
                BusinessUnitConnectorIdsTable.connector_id == masternaut_connector_id,
                # We however need the businessUnitConnectorId of that specific customerId
                BusinessUnitConnectorIdsTable.add_params['customerId'] == CollaboratorConnectorIdsTable.add_params['customerId'],
            )
        ).join(
            OrganizationsTable,
            OrganizationsTable.id == CollaboratorsTable.organization_id,
        ).where(
            OrganizationsTable.slug == org_slug,
        )

        collaborator_df = pd.read_sql(collaborator_query, engine)
        driver_df = masternaut_get(endpoint='driver', org_slug=org_slug)
        driver_df = driver_df.rename(
            columns={
                'id': 'collaborator_connector_id',
                'groupId': 'collaborator_group_id',
            }
        )
        driver_df = driver_df[
            [
                'customer_id',
                'collaborator_connector_id',
                'defaultVehicleId',
                'collaborator_group_id',
            ]
        ]
        collaborator_df = collaborator_df.merge(
            driver_df,
            on=['customer_id', 'collaborator_connector_id'],
            how='left',
            validate='m:1',  # Some collaborator_connector_ids are missing
        )

        return collaborator_df


def masternaut_get(endpoint: str, org_slug: str) -> pd.DataFrame:
    ids = json.loads(PROD_SECRETS.get(f'{org_slug.upper()}_MASTERNAUT_IDS', "[]"))

    if not ids:
        raise ValueError('Missing Masternaut ids')

    df_lst = []
    for id in ids:
        response = requests.get(
            url=os.path.join(
                MASTERNAUT_BASE_URL,
                f'{id}/{endpoint}'
            ),
            auth=get_masternaut_auth(org_slug),
            params={}
        ).json()['items']

        df = pd.DataFrame(response)
        df['customer_id'] = id
        df_lst.append(df)

    return pd.concat(df_lst, axis=0, ignore_index=True)


def update_association_masternaut(
    vehicle_connector_id: str,
    plate_number: str,
    collaborator_id: str,
    collaborator_connector_id: str,
    soongo_collab_reference: str,
    customer_id: str,
    business_unit_connector_id: str,
    default_vehicle_id: str,
    default_driver_id: str,
    org_slug: str,
    logger: logging.Logger,
) -> None:
    if scalar_is_nan(vehicle_connector_id):
        logger.warning(
            'Vehicle %s has no connector id',
            plate_number
        )
        return

    if scalar_is_nan(customer_id):
        logger.warning(
            'Vehicle %s has no customer id',
            plate_number
        )
        return

    if scalar_is_nan(collaborator_connector_id) and (not scalar_is_nan(collaborator_id)):
        if scalar_is_nan(business_unit_connector_id):
            logger.warning(
                'Collaborator %s has no connector id nor any group id',
                soongo_collab_reference,
            )
            return

        collaborator_connector_id = create_collaborator_masternaut(
            logger=logger,
            customer_id=customer_id,
            soongo_collab_reference=soongo_collab_reference,
            business_unit_connector_id=business_unit_connector_id,
            org_slug=org_slug,
        )

        if scalar_is_nan(collaborator_connector_id):
            return

    if not scalar_is_nan(default_vehicle_id):
        unlink_collaborator_vehicle_masternaut(
            customer_id=customer_id,
            soongo_collab_reference=soongo_collab_reference,
            default_vehicle_id=default_vehicle_id,
            collaborator_connector_id=collaborator_connector_id,
            org_slug=org_slug,
            logger=logger,
        )

    if not scalar_is_nan(default_driver_id):
        unlink_collaborator_vehicle_masternaut(
            customer_id=customer_id,
            soongo_collab_reference=soongo_collab_reference,
            default_vehicle_id=vehicle_connector_id,
            collaborator_connector_id=default_driver_id,
            org_slug=org_slug,
            logger=logger,
        )

    if scalar_is_nan(collaborator_id):
        logger.info(
            'Vehicle %s is not associated with a driver on SoonGo; not linking',
            plate_number,
        )

    else:
        link_collaborator_vehicle_masternaut(
            customer_id=customer_id,
            soongo_collab_reference=soongo_collab_reference,
            vehicle_connector_id=vehicle_connector_id,
            collaborator_connector_id=collaborator_connector_id,
            plate_number=plate_number,
            org_slug=org_slug,
            logger=logger,
        )

        attribute_collaborator_to_group_masternaut(
            customer_id=customer_id,
            soongo_collab_reference=soongo_collab_reference,
            collaborator_connector_id=collaborator_connector_id,
            business_unit_connector_id=business_unit_connector_id,
            org_slug=org_slug,
            logger=logger,
        )

    # Update vehicle group
    if not scalar_is_nan(business_unit_connector_id):
        attribute_vehicle_to_group_masternaut(
            customer_id=customer_id,
            vehicle_connector_id=vehicle_connector_id,
            business_unit_connector_id=business_unit_connector_id,
            plate_number=plate_number,
            org_slug=org_slug,
            logger=logger,
        )


def unlink_collaborator_vehicle_masternaut(
    customer_id: str,
    soongo_collab_reference: str,
    default_vehicle_id: str,
    collaborator_connector_id: str,
    org_slug: str,
    logger: logging.Logger,
) -> None:
    response = requests.delete(
        url=os.path.join(
            MASTERNAUT_BASE_URL,
            f'{customer_id}/driver/{collaborator_connector_id}/vehicle/{default_vehicle_id}',
        ),
        auth=get_masternaut_auth(org_slug),
        headers={'content-type': 'application/json; charset=utf-8'}, 
    )
    if response.status_code // 100 == 2:
        try:
            # If the response is JSON, parse it
            error_message = response.json()
        except ValueError:
            # If the response is not JSON, fallback to plain text
            error_message = response.text
        logger.info(
            'Unlinked collaborator %s from masternaut vehicle %s, status code: %s: %s',
            soongo_collab_reference,
            default_vehicle_id,
            response.status_code,
            error_message,
        )
    elif json.loads(
        response.content.decode('utf-8')
    )[0].get('errorCode') in (0, 12004):
        logger.info(
            'Collaborator %s was already unlinked from masternaut vehicle %s, error message: %s',
            soongo_collab_reference,
            default_vehicle_id,
            response.content.decode('utf-8'),
        )
    else:
        response_content = json.loads(
            response.content.decode('utf-8')
        )
        logger.error(
            f'Failed to unlink collaborator '
            f'{soongo_collab_reference} and masternaut '
            f'vehicle {default_vehicle_id} on '
            f'{response_content}'
        )


def link_collaborator_vehicle_masternaut(
    customer_id: str,
    soongo_collab_reference: str,
    vehicle_connector_id: str,
    collaborator_connector_id: str,
    plate_number: str,
    org_slug: str,
    logger: logging.Logger,
) -> None:
    response = requests.post(
        url=os.path.join(
            MASTERNAUT_BASE_URL,
            f'{customer_id}/driver/{collaborator_connector_id}/vehicle/{vehicle_connector_id}',
        ),
        auth=get_masternaut_auth(org_slug),
        headers={'content-type': 'application/json; charset=utf-8'}, 
    )
    if response.status_code // 100 == 2:
        logger.info(
            'Linked vehicle %s to driver %s, status code: %s',
            plate_number,
            soongo_collab_reference,
            response.status_code,
        )
    else:
        logger.error(
            f'Failed to link vehicle {plate_number} '
            f'and collaborator {soongo_collab_reference}'
            f' on {response.status_code}'
        )


def attribute_collaborator_to_group_masternaut(
    customer_id: str,
    soongo_collab_reference: str,
    collaborator_connector_id: str,
    business_unit_connector_id: str,
    org_slug: str,
    logger: logging.Logger,
) -> None:
    url = os.path.join(
        MASTERNAUT_BASE_URL,
        f'{customer_id}/driver/{collaborator_connector_id}',
    )
    response = requests.put(
        url=url,
        auth=get_masternaut_auth(org_slug),
        headers={'content-type': 'application/json; charset=utf-8'},
        json={
            'id': collaborator_connector_id,
            'groupId': business_unit_connector_id,
        }
    )
    if response.status_code // 100 == 2:
        logger.info(
            'Linked driver %s to masternaut group %s, status code: %s',
            soongo_collab_reference,
            business_unit_connector_id,
            response.status_code,
        )
    else:
        logger.error(
            f'Failed to link collaborator {soongo_collab_reference} '
            f'and group {business_unit_connector_id}'
            f' on {response.status_code}'
        )


def attribute_vehicle_to_group_masternaut(
    customer_id: str,
    vehicle_connector_id: str,
    business_unit_connector_id: str,
    plate_number: str,
    org_slug: str,
    logger: logging.Logger,
):
    response = requests.put(
        url=os.path.join(
            MASTERNAUT_BASE_URL,
            f'{customer_id}/vehicle/{vehicle_connector_id}',
        ),
        auth=get_masternaut_auth(org_slug),
        headers={'content-type': 'application/json; charset=utf-8'},
        json={
            'id': vehicle_connector_id,
            'groupId': business_unit_connector_id,
        }
    )
    if response.status_code // 100 == 2:
        logger.info(
            'Linked vehicle %s to masternaut group %s, status code: %s',
            plate_number,
            business_unit_connector_id,
            response.status_code,
        )
    else:
        logger.error(
            f'Failed to link vehicle {plate_number} '
            f'and group {business_unit_connector_id}'
            f' on {response.status_code}'
        )


def create_collaborator_masternaut(
    logger: logging.Logger,
    customer_id: str,
    soongo_collab_reference: str,
    business_unit_connector_id: str,
    org_slug: str
) -> str:
    response = requests.post(
        url=os.path.join(
            MASTERNAUT_BASE_URL,
            f'{customer_id}/driver',
        ),
        auth=get_masternaut_auth(org_slug),
        headers={'content-type': 'application/json; charset=utf-8'},
        json={
            'name': soongo_collab_reference,
            'active': True,
            'groupId': business_unit_connector_id,
        }
    )
    if response.status_code // 100 == 2:
        logger.info(
            'Created collaborator %s in masternaut, status code: %s',
            soongo_collab_reference,
            response.status_code,
        )
        return response.json()['id']
    else:
        logger.error(
            'Failed to create collaborator '
            '%s on masternaut %s for url %s',
            soongo_collab_reference,
            response.status_code,
            response.url,
        )
        return


@lru_cache
def get_masternaut_auth(org_slug: str):
    username = PROD_SECRETS[f'{org_slug.upper()}_MASTERNAUT_USERNAME']
    pwd = PROD_SECRETS[f'{org_slug.upper()}_MASTERNAUT_PWD']
    if not username or not pwd:
        raise ValueError('Missing Masternaut credentials')
    return requests.auth.HTTPBasicAuth(username, pwd)


def lambda_handler(event, context):
    engine = gen_engine(
        database_url=PROD_SECRETS['DATABASE_URL']
    )
    logger = gen_logger(__name__)
    for synchro_params in event:
        main(
            org_slug=synchro_params['organization_slug'],
            engine=engine,
            logger=logger,
        )
