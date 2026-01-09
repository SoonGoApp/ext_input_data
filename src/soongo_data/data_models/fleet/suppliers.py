
""" Suppliers

Defines columns used across all Gac datasets
"""
from soongo_data.data_models.base import BaseModel, DataColumn
from soongo_data.utils.enums import Suppliers, mapper_factory
from soongo_data.utils.type import convert_string


class SuppliersModel(BaseModel):
    supplier = DataColumn(
        raw_name="Fournisseur",
        name="supplier",
        post_processing=mapper_factory(Suppliers),
        dtype='string',
    )
    supplier_id = DataColumn(
        raw_name="supplier_id",
        name="supplier_id",
        dtype='string',
        post_processing=convert_string,
        description='Soongo internal db uuid',
    )
