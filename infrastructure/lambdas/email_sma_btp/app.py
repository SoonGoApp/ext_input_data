import json
import logging
import os
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import sqlalchemy as sa

from soongo_data.sql_mappings import (
    OrganizationsTable,
    VehicleContractsRankedView,
    VehicleContractsTable,
    VehiclesTable,
)
from soongo_data.utils.aws import (
    df_to_bytes_excel,
    send_ses_email,
)
from soongo_data.utils.secrets_utils import get_local_secret
from soongo_data.utils.db import gen_engine
from soongo_data.utils.logging_utils import gen_logger


def extract_to_df(sql: str, logger: logging.Logger) -> pd.DataFrame:
    db_info = get_local_secret(logger=logger)
    engine = gen_engine(
        database_url=db_info['DATABASE_URL'],
    )
    df = pd.DataFrame()

    logger.info('Loading dataframe')
    with engine.connect() as con:
        df = pd.read_sql(
            sql=sql,
            con=con,
        )
    logger.info('Loaded dataframe')
    return df


def prepare_sql_query_to_get_vehicles(
    organization_slug: str, logger: logging.Logger
) -> sa.sql.selectable.Select:
    max_rank_subq = (
        sa.select(
            VehicleContractsRankedView.vehicle_id,
            sa.func.max(VehicleContractsRankedView.contracts_rank).label(
                'max_rank'
            ),
        )
        .group_by(VehicleContractsRankedView.vehicle_id)
        .cte('max_rank_per_vehicle')
    )
    sql = (
        sa.select(
            VehiclesTable.plate_number.label("Immatriculation"),
            VehiclesTable.entry_into_fleet_date.label("Date d'ajout"),
            VehiclesTable.exit_from_fleet_date.label("Date de retrait"),
            sa.literal("Tous risques").label("Offre"),
            VehicleContractsTable.contract_type.label("Mode d'acquisition"),
            VehiclesTable.rebate_price.label("Prix d'achat TTC"),
        )
        .select_from(max_rank_subq)
        .join(
            VehicleContractsRankedView,
            sa.and_(
                VehicleContractsRankedView.vehicle_id
                == max_rank_subq.c.vehicle_id,
                VehicleContractsRankedView.contracts_rank
                == max_rank_subq.c.max_rank,
            ),
        )
        .join(
            VehicleContractsTable,
            VehicleContractsTable.id == VehicleContractsRankedView.id,
        )
        .join(
            VehiclesTable, VehiclesTable.id == VehicleContractsTable.vehicle_id
        )
        .join(
            OrganizationsTable,
            sa.and_(
                OrganizationsTable.id == VehiclesTable.organization_id,
                OrganizationsTable.slug == organization_slug,
            ),
        )
    )

    logger.info('Query: %s', sql)
    return sql


def send_email(organization_slug, recipient_emails, now, logger) -> None:
    try:
        df = extract_to_df(
            prepare_sql_query_to_get_vehicles(
                organization_slug, logger
            ),
            logger,
        )

        for col in df.select_dtypes(['datetimetz']).columns:
            df[col] = df[col].dt.tz_localize(None)  

        for recipient_email in recipient_emails:
            logger.info('Sending email to %s', recipient_email)
            send_ses_email(
                sender_email='infra@soongo.co',
                recipient_email=recipient_email,
                subject=f'État de parc {now.strftime("%m/%Y")}',
                body_text=(
                    f"""Bonjour,

Veuillez trouver ci-joint un état de parc à la date du {now.strftime('%d/%m/%Y')}.

Bonne journée,

L'équipe SoonGo"""
                ),
                logger=logger,
                attachment_tup=(
                    f'etat_de_parc__{now.strftime("%Y-%m-%d")}.xlsx',
                    df_to_bytes_excel(df),
                ),
            )
    except Exception as error:
        logger.exception(
            'Email send failed for organization %s on error %s',
            organization_slug,
            error,
        )
        send_ses_email(
            sender_email='infra@soongo.co',
            recipient_email='data@soongo.co',
            subject=f'Alert: Error on {os.environ["AWS_LAMBDA_FUNCTION_NAME"]} aws lambda function',
            body_text=(
                f"""Function: {os.environ['AWS_LAMBDA_FUNCTION_NAME']}
Version: {os.environ['AWS_LAMBDA_FUNCTION_VERSION']}
Region: {os.environ['AWS_REGION']}
Memory: {os.environ['AWS_LAMBDA_FUNCTION_MEMORY_SIZE']} MB

With organization '{organization_slug}'

Error: {error}
Traceback: {traceback.format_exception(error)}
                """
            ),
            logger=logger,
        )
    else:
        logger.info(
            'Email send succeeded for organization %s to %s',
            organization_slug,
            recipient_email,
        )


def lambda_handler(event, context):
    logger = gen_logger(__name__)
    now = datetime.now(ZoneInfo('Europe/Paris'))

    if os.environ['env'] == 'staging':
        logger.warning(
            '! Using staging!',
        )
    for upload_params in event:
        organization_slug = upload_params.get('organization_slug')
        recipient_emails = upload_params.get('recipient_emails')
        send_email(organization_slug, recipient_emails, now, logger)
    return {
        'statusCode': 200,
        'body': json.dumps('SMA-BTP email'),
    }
