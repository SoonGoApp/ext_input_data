import json
import os

import pandas as pd
import pytz
import sqlalchemy as sa
import traceback

from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.aws import df_to_bytes_excel, send_ses_email
from soongo_data.utils.db import gen_engine
from soongo_data.utils.secrets_utils import get_local_secret
from soongo_data.sql_mappings import (
    BusinessUnitsTable,
    OrganizationsTable,
    OrganizationParametersTable,
    SuppliersTable,
    VehiclesTable,
    CollaboratorsTable,
    ExpensesTable,
    ExpenseWithAssociations,
    VehicleModelsTable,
    VehicleBusinessUnitView,
    ExpenseSoongoCategoryTable,
    VehicleAttributionsTable
)


def main(
    engine: sa.engine.base.Engine,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    org_slug: str,
    exclude_unattributed: bool = False,
) -> pd.DataFrame:
    """
    Export expenses from the database to a CSV file.

    Args:
        logger (logging.Logger): Logger object for logging.
        engine (sa.engine.base.Engine): SQLAlchemy engine for database connection.
        start_date (pd.Timestamp): Start date for filtering expenses.
        end_date (pd.Timestamp): End date for filtering expenses.

    Returns:
        pd.Dataframe: Dataframe of expenses
    """
    with engine.connect() as con:

        where_conds = [
            OrganizationsTable.slug == org_slug,
            sa.func.coalesce(
                ExpenseWithAssociations.transaction_start_date,
                ExpenseWithAssociations.billing_date,
            ).between(start_date, end_date),
        ]

        if exclude_unattributed:
            where_conds.append(
                sa.func.coalesce(
                    VehicleBusinessUnitView.cost_center_id,
                    CollaboratorsTable.business_unit_id
                ).is_not(None)
            )

        expenses_bu = sa.select(
            ExpenseWithAssociations.id,
            ExpenseWithAssociations.billing_date,
            ExpenseWithAssociations.transaction_start_date,
            ExpenseWithAssociations.transaction_end_date,
            ExpenseWithAssociations.expense_location,
            ExpenseWithAssociations.soongo_category,
            ExpenseWithAssociations.product,
            ExpenseWithAssociations.supplier_id,
            ExpenseWithAssociations.amount_tax_exc,
            ExpenseWithAssociations.vat_value,
            ExpenseWithAssociations.net_amount,
            ExpenseWithAssociations.organization_id,
            ExpenseWithAssociations.merchant_name,
            ExpenseWithAssociations.billing_reference,
            ExpenseWithAssociations.quantity,
            sa.func.coalesce(
                VehicleBusinessUnitView.cost_center_id,
                CollaboratorsTable.business_unit_id,
                sa.cast(
                    sa.func.replace(
                        sa.cast(
                            OrganizationParametersTable.value['value'],
                            sa.String,
                        ),
                        '"',
                        '',
                    ),
                    sa.UUID,
                ),
            ).label('business_unit_id'),
            ExpenseWithAssociations.collaborator_id,
            VehicleBusinessUnitView.previous_attribution_id,
            ExpenseWithAssociations.vehicle_id.label('vehicle_id'),
            BusinessUnitsTable.name.label('Mini'),
            ExpensesTable.billed_entity,
            sa.and_(
                VehicleBusinessUnitView.collaborator_id.is_(None),
                VehicleBusinessUnitView.attribution_business_unit_id.is_(None)
            ).label('not_attributed'),
            sa.func.rank().over(
                partition_by=ExpenseWithAssociations.id,
                order_by=[
                    VehicleBusinessUnitView.date_from.desc(),
                    sa.func.coalesce(
                        VehicleBusinessUnitView.date_to,
                        end_date,
                    ).desc(),
                    VehicleBusinessUnitView.attribution_business_unit_id.asc()  # Tie breaker
                ]
            ).label('association_rank'),
        ).select_from(
            ExpenseWithAssociations
        ).join(
            ExpensesTable,
            ExpensesTable.id == ExpenseWithAssociations.id,
        ).outerjoin(
            VehicleBusinessUnitView,
            sa.and_(
                sa.func.coalesce(
                    ExpenseWithAssociations.transaction_start_date,
                    ExpenseWithAssociations.billing_date,
                ).between(
                    VehicleBusinessUnitView.date_from,
                    sa.func.coalesce(
                        VehicleBusinessUnitView.date_to,
                        sa.func.now(),
                    ),
                ),
                VehicleBusinessUnitView.vehicle_id == ExpenseWithAssociations.vehicle_id,
            ),
        ).join(
            OrganizationsTable,
            OrganizationsTable.id == ExpenseWithAssociations.organization_id
        ).outerjoin(
            CollaboratorsTable,
            CollaboratorsTable.id == ExpenseWithAssociations.collaborator_id
        ).outerjoin(
            BusinessUnitsTable,
            BusinessUnitsTable.id == VehicleBusinessUnitView.cost_center_id
        ).outerjoin(
            OrganizationParametersTable,
            sa.and_(
                OrganizationParametersTable.organization_id == ExpenseWithAssociations.organization_id,
                OrganizationParametersTable.name == 'default_cost_center',
            )
        ).where(
            *where_conds
        ).alias('expense_bu')

        last_driver = sa.orm.aliased(CollaboratorsTable)
        last_bu = sa.orm.aliased(BusinessUnitsTable)

        query = sa.select(
            expenses_bu.c.id,
            expenses_bu.c.billing_date.label('Date de facturation'),
            expenses_bu.c.transaction_start_date.label('Date de début'),
            expenses_bu.c.transaction_end_date.label('Date de fin'),
            expenses_bu.c.expense_location.label('Lieu de la dépense'),
            VehiclesTable.plate_number.label('Immatriculation'),
            VehicleModelsTable.name.label('Modèle'),
            sa.func.coalesce(
                CollaboratorsTable.firstname + ' ' + CollaboratorsTable.lastname,
                CollaboratorsTable.soongo_collab_reference,
            ).label('Conducteur'),
            expenses_bu.c.Mini.label('Mini'),
            sa.func.coalesce(
                last_bu.name,
                sa.func.coalesce(
                    last_driver.firstname + ' ' + last_driver.lastname,
                    last_driver.soongo_collab_reference,
                ),
            ).label('Précédente attribution'),
            sa.case(
                (
                    sa.or_(
                        VehicleAttributionsTable.business_unit_id.is_not(None),
                        VehicleAttributionsTable.collaborator_id.is_not(None),
                    ),
                    VehicleAttributionsTable.date_to,
                ),
            ).label('Date de fin précédente attribution'),
            BusinessUnitsTable.name.label('Centre de coûts'),
            expenses_bu.c.soongo_category.label('Catégorie Soongo'),
            expenses_bu.c.product.label('Libellé dépense fournisseur'),
            SuppliersTable.name.label('Fournisseur'),
            expenses_bu.c.amount_tax_exc.label('Dépense HT'),
            expenses_bu.c.vat_value.label('TVA'),
            expenses_bu.c.net_amount.label('Dépense Net'),
            expenses_bu.c.merchant_name.label('Nom du marchand'),
            expenses_bu.c.billing_reference.label('Référence de la facture'),
            expenses_bu.c.quantity.label('Quantité'),
            VehiclesTable.energy.label('Énergie du véhicule'),
            expenses_bu.c.billed_entity.label('Entité facturée')
        ).select_from(
            expenses_bu
        ).outerjoin(
            VehiclesTable,
            VehiclesTable.id == expenses_bu.c.vehicle_id
        ).outerjoin(
            VehicleModelsTable,
            VehicleModelsTable.id == VehiclesTable.model_id,
        ).outerjoin(
            CollaboratorsTable,
            CollaboratorsTable.id == expenses_bu.c.collaborator_id
        ).outerjoin(
            VehicleAttributionsTable,
            VehicleAttributionsTable.id == expenses_bu.c.previous_attribution_id,
        ).outerjoin(
            last_driver,
            last_driver.id == VehicleAttributionsTable.collaborator_id,
        ).outerjoin(
            last_bu,
            last_bu.id == VehicleAttributionsTable.business_unit_id,
        ).outerjoin(
            BusinessUnitsTable,
            BusinessUnitsTable.id == expenses_bu.c.business_unit_id
        ).outerjoin(
            SuppliersTable,
            SuppliersTable.id == expenses_bu.c.supplier_id,
        ).filter(
            expenses_bu.c.association_rank == 1,
        )

        df = pd.read_sql(
            sql=query,
            con=con,
        )

    assert df['id'].is_unique, 'Duplicate expenses in export!'
    df.drop(columns=['id'], inplace=True)

    translated_cat = df['Catégorie Soongo'].map(
        get_expense_translation(
            sql_connection=engine,
        )
    )
    missing_categories = df.loc[
        pd.isna(translated_cat),
        'Catégorie Soongo'
    ]
    if len(missing_categories):
        raise ValueError(
            f'Missing categories for {missing_categories.unique()}'
        )
    df['Catégorie Soongo'] = translated_cat

    return df


def get_expense_translation(sql_connection: sa.Connection, lang: str = 'fr'):
    """
    Get the translation for the expense categories.

    Args:
        sql_connection (sa.Connection): SQLAlchemy connection object.
        lang (str): Language code for the translation.

    Returns:
        dict: Mapping of expense categories to their translations.
    """
    query = sa.select(
        ExpenseSoongoCategoryTable.type,
        ExpenseSoongoCategoryTable.description_fr,
    ).select_from(
        ExpenseSoongoCategoryTable
    )
    translation_dict = sql_connection.connect().execute(query).fetchall()
    translation_dict = {
        row[0]: row[1]
        for row in translation_dict
    }

    return translation_dict


def convert_date_cols(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert date columns to datetime objects.

    Args:
        df (pd.DataFrame): Input DataFrame.

    Returns:
        pd.DataFrame: DataFrame with date columns converted to datetime objects.
    """
    for col in df.columns:
        # Excel does not support timezone
        if pd.api.types.is_datetime64_any_dtype(df[col].dtype):
            # Even if the datetimes are naive, we know them to be in UTC
            if df[col].dt.tz is not None:
                df[col] = df[col].dt.tz_convert('Europe/Paris')
                df[col] = df[col].dt.tz_localize(None)

    return df


def lambda_handler(event, context):
    logger = gen_logger(__name__)
    db_info = get_local_secret(logger=logger)

    if os.environ['env'] == 'staging':
        logger.warning(
            '! Using staging!'
        )
    engine = gen_engine(
        database_url=db_info['DATABASE_URL'],
    )

    for upload_params in event:
        organization_slug = upload_params.get('organization_slug')
        recipient_email = upload_params.get('recipient_email')
        with engine.connect() as connection:
            organization_name = connection.execute(
                sa.select(OrganizationsTable.name).where(
                    OrganizationsTable.slug == organization_slug
                )
            ).scalar()

        paris_tz = pytz.timezone('Europe/Paris')
        today = pd.Timestamp.today(tz=paris_tz)
        start_date = (today.replace(day=1) - pd.offsets.MonthBegin(1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = (today.replace(day=1) - pd.offsets.MonthEnd(1)).replace(hour=23, minute=59, second=59)


        try:
            logger.info(
                'Exporting expenses from %s to %s',
                start_date,
                end_date
            )
            expense_df = main(
                engine=engine,
                start_date=start_date,
                end_date=end_date,
                org_slug=organization_slug,
                exclude_unattributed=upload_params.get(
                    'exclude_unattributed',
                    False
                ),
            )
            expense_df = convert_date_cols(expense_df)

            logger.info(
                'Sending email for %d expenses from %s to %s for organization slug %s',
                len(expense_df),
                start_date,
                end_date,
                organization_slug,
            )

            # boto3.set_stream_logger('botocore', level=DEBUG)
            send_ses_email(
                sender_email="infra@soongo.co",
                recipient_email=recipient_email,
                subject=f"Rapport de dépenses {organization_name}",
                body_text=(
                    f"Bonjour,\n\nVeuillez trouver ci-joint un rapport des dépenses de {organization_name}"
                    f" du {start_date.strftime('%d/%m/%Y')} au {end_date.strftime('%d/%m/%Y')}.\n\nBonne journée,\n\nL'équipe SoonGo"
                ),
                logger=logger,
                attachment_tup=(
                    f"{organization_slug}_dépenses_{start_date.strftime(r'%d/%m/%Y')}_{end_date.strftime(r'%d/%m/%Y')}.xlsx",
                    df_to_bytes_excel(expense_df)
                )
            )

        except Exception as error:
            logger.error(
                'Email send failed for organization %s on error %s',
                organization_slug,
                error
            )
            send_ses_email(
                sender_email="infra@soongo.co",
                recipient_email="data@soongo.co",
                subject="Alert: Error on send expenses email",
                body_text=(
                    f"Sending expense email for organization {organization_slug} failed on error {error}"
                    f" with traceback {traceback.format_exception(error)}"
                ),
                logger=logger,
            )

        else:
            logger.info(
                f'Email send succeeded for organization %s to {recipient_email}',
                organization_slug,
            )

    return {
        'statusCode': 200,
        'body': json.dumps('Expenses email export')
    }
