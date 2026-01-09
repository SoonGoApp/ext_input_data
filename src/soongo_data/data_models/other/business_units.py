""" BusinessUnitsModel

Defines columns used across all fleet connectors datasets
"""
from soongo_data.data_models.base import BaseModel, DataColumn
from soongo_data.utils.type import convert_date, convert_string


class BusinessUnitsModel(BaseModel):
    business_unit_id = DataColumn(
        raw_name='business_unit_id',
        dtype='string',
        post_processing=convert_string,
        name='business_unit_id',
        description='Soongo internal db uuid for this business unit',
    )
    region_id = DataColumn(
        raw_name='region_id',
        dtype='string',
        post_processing=convert_string,
        name='region_id',
        description='Soongo internal db uuid for this geography',
    )
    entity_ref = DataColumn(
        raw_name='Unité organisationnelle du collaborateur 3 : nom',
        dtype='string',
        name='entity_ref',
        post_processing=convert_string,
    )
    entity_1: DataColumn = DataColumn(
        raw_name='Entité 1',
        dtype='string',
        post_processing=convert_string,
        name='entity_1',
    )
    entity_2: DataColumn = DataColumn(
        raw_name='Entité 2',
        dtype='string',
        post_processing=convert_string,
        name='entity_2',
    )
    entity_3: DataColumn = DataColumn(
        raw_name='Entité 3',
        dtype='string',
        post_processing=convert_string,
        name='entity_3',
    )
    entity_4: DataColumn = DataColumn(
        raw_name='Entité 4',
        dtype='string',
        post_processing=convert_string,
        name='entity_4',
    )
    parent_entity: DataColumn = DataColumn(
        raw_name='Entité parente',
        dtype='string',
        post_processing=convert_string,
        name='parent_entity',
    )
    business_unit_connector_id = DataColumn(
        raw_name='business_unit_connector_id',
        dtype='string',
        post_processing=convert_string,
        name='business_unit_connector_id',
        description='business unit id on an external connector system',
    )
    cost_center: DataColumn = DataColumn(
        raw_name='Centre de coûts',
        dtype='string',
        post_processing=convert_string,
        name='cost_center',
    )
    billed_entity: DataColumn = DataColumn(
        raw_name='Entité Facturée',
        dtype='string',
        post_processing=convert_string,
        name='billed_entity',
    )
    export_entity: DataColumn = DataColumn(
        raw_name="Entité exportée",
        dtype='string',
        post_processing=convert_string,
        name='export_entity'
    )
    employee_entity: DataColumn = DataColumn(
        raw_name='Entité Collaborateur',
        dtype='string',
        post_processing=convert_string,
        name='employee_entity',
    )
    company_name = DataColumn(
        raw_name="Société",
        dtype='string',
        post_processing=convert_string,
        name='company_name',
    )
    company_number = DataColumn(
        raw_name="SIREN",
        dtype='string',
        post_processing=convert_string,
        name='company_number',
    )
    company_number_detail = DataColumn(
        raw_name="N° Siret",
        dtype='string',
        post_processing=convert_string,
        name='company_number_detail',
    )
    legal_entity = DataColumn(
        raw_name="Entité légale",
        dtype='string',
        post_processing=convert_string,
        name='legal_entity',
    )
    business_unit_attribution_date = DataColumn(
        raw_name="Date d'affection de l'entité",
        dtype='datetime64[ns]',
        name='business_unit_attribution_date',
        post_processing=lambda x: convert_date(x, date_format=r'%d/%m/%Y'),
    )
    organization_name = DataColumn(
        raw_name='Client / Groupe',
        dtype='string',
        post_processing=convert_string,
        name='organization_name',
    )
    organization_id = DataColumn(
        raw_name='Code Client',
        dtype='Int64',
        name='organization_id',
    )
    business_unit = DataColumn(
        raw_name='business_unit',
        dtype='string',
        name='business_unit',
        description=(
            'SoonGo generated hierarchical business unit. '
            'All units separated by ">"'
        )
    )
    geography = DataColumn(
        raw_name='geography',
        dtype='string',
        name='geography',
        description=(
            'SoonGo generated hierarchical geographies. '
            'All geographies separated by ">"'
        )
    )
    analytical_code = DataColumn(
        raw_name='Code analytique',
        dtype='string',
        post_processing=convert_string,
        name='analytical_code',
    )
    analytical_entity_1 = DataColumn(
        raw_name='Analytique 1',
        dtype='string',
        post_processing=convert_string,
        name='analytical_entity_1',
    )
