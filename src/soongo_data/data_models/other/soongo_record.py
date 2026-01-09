""" SoonGoRecordModel

Defines columns used across all Gac datasets
"""
from soongo_data.data_models.base import BaseModel, DataColumn
from soongo_data.utils.enums import SynchronizationTypes, mapper_factory
from soongo_data.utils.type import convert_json, convert_string


class SoonGoRecordsModel(BaseModel):
    organization_id: DataColumn = DataColumn(
        raw_name='organization_id',
        dtype='string',
        name='organization_id',
        description='SoonGo database uuid associated with the organization',
    )
    record_date: DataColumn = DataColumn(
        raw_name='record_date',
        dtype='datetime64[ns]',
        name='record_date',
        description='Minimum date at which the row was recorded'
    )
    source_dataset: DataColumn = DataColumn(
        raw_name='source_dataset',
        dtype='string',
        name='source_dataset',
        description='Dataset name the data was sourced from'
    )
    connector_name: DataColumn = DataColumn(
        raw_name='connector_name',
        dtype='string',
        name='connector_name',
        description='Name of the connector the data was sourced from'
    )
    connector_id: DataColumn = DataColumn(
        raw_name='connector_id',
        dtype='string',
        name='connector_id',
        description='Db uuid of the connector the data was sourced from'
    )
    source_table: DataColumn = DataColumn(
        raw_name='source_table',
        dtype='string',
        name='source_table',
        description='Name of the table the data was sourced from'
    )
    synchronisation_id: DataColumn = DataColumn(
        raw_name='synchronisation_id',
        dtype='string',
        name='synchronisation_id',
        description='Synchronisation uuid, unique per connector',
    )
    synchronisation_type: DataColumn = DataColumn(
        raw_name='synchronisation_type',
        dtype='string',
        name='synchronisation_type',
        post_processing=mapper_factory(SynchronizationTypes),
        description='Synchronisation type see SynchronizationTypes enum',
    )
    ext_api_params: DataColumn = DataColumn(
        raw_name='ext_api_params',
        name='ext_api_params',
        dtype='object',
        description='Additional parameters used to query the external api, such as id',
        post_processing=convert_json,
        is_json=True,
    )
    edi_line_reference: DataColumn = DataColumn(
        raw_name='edi_line_reference',
        name='edi_line_reference',
        dtype='object',
        description='EDI line reference identifying type of line',
        post_processing=convert_string,
    )
    file_creation_date: DataColumn = DataColumn(
        raw_name='file_creation_date',
        name='file_creation_date',
        dtype='datetime64[ns]',
        description='Creation date of the underlying file'
    )
    sheet_name: DataColumn = DataColumn(
        raw_name='sheet_name',
        name='sheet_name',
        dtype='string',
        description='Sheet name of the underlying excel file'
    )
