"""scritp to fetch vehicle eco score data from Masternaut API and load it"""

import asyncio
import logging
import os
import typing

import aiohttp
import pandas as pd
import sqlalchemy as sa
from sqlalchemy.orm.session import Session

from soongo_data.connectors import ConnectorData
from soongo_data.data_models import DocumentsModel, VehiclesModel
from soongo_data.data_models.other.soongo_record import SoonGoRecordsModel
from soongo_data.input_tables import io
from soongo_data.input_tables.input_tables import add_synchronization_id
from soongo_data.sql_mappings import DocumentsTable
from soongo_data.sql_mappings.organizations import OrganizationsTable
from soongo_data.sql_mappings.vehicles import VehiclesTable
from soongo_data.utils.aws import gen_s3_path, push_to_s3_async
from soongo_data.utils.db import get_organization_id
from soongo_data.utils.input_tables import (
    InputColumn,
    InputTable,
    add_input_table,
)
from soongo_data.utils.logging_utils import gen_logger


@add_input_table
class DocumentsUploadInputTable(InputTable):
    def __init__(self: typing.Self) -> None:
        super().__init__(
            sql_mapping=DocumentsTable,
            columns=[
                InputColumn.from_data_column(
                    column=DocumentsModel.doc_type,
                    sql_name='type',
                ),
                InputColumn.from_data_column(
                    column=VehiclesModel.plate_number,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=DocumentsModel.path,
                    sql_name='path',
                ),
                InputColumn.from_data_column(
                    column=DocumentsModel.filename,
                    nullable=False,
                    sql_name='filename',
                ),
                InputColumn.from_data_column(
                    column=DocumentsModel.size,
                    nullable=False,
                ),
                InputColumn.from_data_column(
                    column=DocumentsModel.hash_content,
                    is_id=True,
                ),
                InputColumn.from_data_column(
                    column=SoonGoRecordsModel.connector_name,
                    nullable=False,
                ),
                InputColumn.from_data_column(
                    column=SoonGoRecordsModel.synchronisation_type,
                    nullable=False,
                ),
                InputColumn.from_data_column(
                    column=SoonGoRecordsModel.synchronisation_id,
                ),
            ],
        )

    @classmethod
    async def get_size_and_hash_file(
        cls, session: aiohttp.ClientSession, plate_number: str, url: str
    ) -> typing.Tuple[int, str]:
        try:
            async with session.get(url) as response:
                response.raise_for_status()

                content = await response.read()
                hash = io.hash_content(content)

                await io.write_content(f'/tmp/{hash}', content)

                return len(content), hash
        except Exception as e:
            return 0, str(e)

    @classmethod
    async def fetch_all(
        cls,
        df: pd.DataFrame,
    ) -> typing.List[typing.Tuple[int, str]]:
        """Fetch size and hash for all files in the DataFrame asynchronously.
        :param df: DataFrame containing document data
        """
        async with aiohttp.ClientSession() as session:
            tasks = [
                cls.get_size_and_hash_file(
                    session,
                    row[VehiclesModel.plate_number.name],
                    row[DocumentsModel.external_url.name],
                )
                for _, row in df.iterrows()
            ]
            return await asyncio.gather(*tasks)

    @classmethod
    async def put_document_async(
        cls, row: pd.Series, logger: logging.Logger, env: str
    ) -> None:
        """Asynchronously upload a document to S3.
        :param row: DataFrame row containing document data
        :param logger: Logger for logging information
        """

        content = await io.read_content(
            f'/tmp/{row[DocumentsModel.hash_content.name]}'
        )

        await push_to_s3_async(
            bucket_name=f'soongo-{env}-media',
            s3_path=row[DocumentsModel.path.name],
            content_type='application/pdf',
            content=content,
            logger=logger,
            endpoint_url=os.environ.get('AWS_ENDPOINT_URL', None),
            session_profile=f'{env}-backend-user',
            ACL='bucket-owner-full-control',
        )

    @classmethod
    async def process_all_documents(
        cls,
        data_df: pd.DataFrame,
        logger: logging.Logger,
        env: str,
    ) -> None:
        """Process all documents asynchronously and upload them to S3.
        :param data_df: DataFrame containing document data
        :param organization_id: ID of the organization to which the documents
        belong
        :param logger: Logger for logging information
        """
        tasks = [
            cls.put_document_async(row, logger, env)
            for _, row in data_df.iterrows()
        ]
        await asyncio.gather(*tasks)

    @classmethod
    def _remove_records_if_document_exists(
        cls,
        df: pd.DataFrame,
        organization_name: str,
        session: Session,
        logger: logging.Logger,
    ) -> pd.DataFrame:
        """Remove records from the DataFrame if the document already exists
        in the database.
        Or if the vehicle id is not found in the database.
            :param df: DataFrame containing documents to check
            :param organization_name: Name of the organization to filter
            documents
            :param session: SQLAlchemy session to query the database
            :return: DataFrame with records removed if the document already
            exists
        """
        organization_id = get_organization_id(organization_name)

        existing_plates = df[VehiclesModel.plate_number.name].unique()

        existing_pairs = pd.read_sql(
            sql=sa.select(
                VehiclesTable.plate_number, DocumentsTable.hash_content
            ).join(
                VehiclesTable,
                sa.and_(
                    VehiclesTable.organization_id == organization_id,
                    DocumentsTable.vehicle_id == VehiclesTable.id,
                )
            ).where(
                VehiclesTable.plate_number.in_(existing_plates)
            ),
            con=session.get_bind(),
        )

        df = df.merge(
            existing_pairs,
            how='left',
            on=[
                VehiclesModel.plate_number.name,
                DocumentsModel.hash_content.name,
            ],
            indicator='is_existing',
        )

        size_df_before_cleaning = len(df)

        df = df[
            ~(df['is_existing'] == 'both')
        ]

        logger.info(
            'Number of already existing records removed from dataframe: %d',
            size_df_before_cleaning - len(df),
        )

        return df

    @staticmethod
    def _get_vehicle_ids_for_df(
        df: pd.DataFrame, organization_id: str, session: Session
    ):
        """Get vehicle ids for the DataFrame based on the plate numbers.
        :param df: DataFrame containing vehicle plate numbers
        :param organization_id: ID of the organization to filter vehicles
        :param session: SQLAlchemy session to query the database
        :return: DataFrame with vehicle IDs added
        """
        plates = df[VehiclesModel.plate_number.name].dropna().unique().tolist()

        plate_to_id = dict(
            session.query(VehiclesTable.plate_number, VehiclesTable.id)
            .filter(VehiclesTable.organization_id == organization_id)
            .filter(VehiclesTable.plate_number.in_(plates))
            .all()
        )

        df[VehiclesModel.vehicle_id.name] = df[
            VehiclesModel.plate_number.name
        ].map(plate_to_id)

        return df

    def _get_df(
        self: typing.Self,
        connector_data: ConnectorData,
        logger: logging.Logger,
        fetch_params_dict: dict | None = None,
    ) -> pd.DataFrame:
        """Get Documents table

        :param connector_data: Connector Data Class with all folders
        """
        combined_df = self.fetch_table_data(
            connector_data=connector_data,
            logger=logger,
            fetch_params_dict=fetch_params_dict,
        )

        combined_df = add_synchronization_id(combined_df, connector_data)
        if combined_df.empty:
            return combined_df

        logger.info(
            'Fetching file metadata for %d documents', len(combined_df)
        )
        files_metadata = asyncio.run(self.fetch_all(combined_df))
        logger.info('%d documents downloaded', len(combined_df))

        combined_df[DocumentsModel.size.name] = [
            file_metadata[0] for file_metadata in files_metadata
        ]
        combined_df[DocumentsModel.hash_content.name] = [
            file_metadata[1] for file_metadata in files_metadata
        ]

        combined_df = self.fill_missing_cols(combined_df)

        return combined_df[self.return_column_names()]

    def to_sql(
        self: typing.Self,
        data_df: pd.DataFrame,
        organization_id: str,
        session: sa.orm.Session,
        logger: logging.Logger,
        update_values: str = 'keep',
        columns: typing.Optional[typing.List[str]] = None,
    ) -> None:
        organization = session.get(OrganizationsTable, organization_id)

        data_df = self._get_vehicle_ids_for_df(
            data_df, organization_id, session
        )

        logger.info(
            'Could fetch vehicle ids for %d/%d documents. Dropping the others.',
            data_df[VehiclesModel.vehicle_id.name].notna().sum(),
            len(data_df),
        )
        data_df = data_df[data_df[VehiclesModel.vehicle_id.name].notna()]

        data_df = self._remove_records_if_document_exists(
            df=data_df,
            organization_name=organization.name,
            session=session,
            logger=logger,
        )
        logger.info('Real number of documents to upload: %d', len(data_df))

        data_df[DocumentsModel.path.name] = data_df.apply(
            lambda row: gen_s3_path(
                organization_slug=organization.slug,
                entity_id=row[VehiclesModel.vehicle_id.name],
                entity_type='vehicle',
                document_type=row[DocumentsModel.doc_type.name],
                file_name=row[DocumentsModel.filename.name],
            ),
            axis=1,
        )

        if 'prod' in os.environ['DATABASE_URL']:
            env = 'prod'
        elif 'staging' in os.environ['DATABASE_URL']:
            env = 'staging'
        else:
            env = os.environ['env']

        asyncio.run(
            self.process_all_documents(
                data_df,
                logger,
                env=env,
            )
        )

        super().to_sql(
            data_df,
            organization_id,
            session,
            logger,
            update_values,
            columns,
        )


if __name__ == '__main__':
    logger = gen_logger('documents_upload')

    organization_name = 'acorus'
    root_folder = os.environ['_soongo_data_folder']
    organization_folder = os.path.join(
        root_folder,
        organization_name,
    )
    connector_data = ConnectorData(
        root_folder=root_folder,
        organization_name=organization_name,
    )
    documents_update_input_table = DocumentsUploadInputTable()

    du_df = documents_update_input_table.get(
        connector_data=connector_data,
        logger=logger,
    )
    du_df.to_csv(
        os.path.join(
            organization_folder,
            'webapp_tables',
            f'{documents_update_input_table.name}_table.csv',
        ),
        index=False,
        sep=';',
    )
