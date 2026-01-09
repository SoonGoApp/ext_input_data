"""DocumentsModel

Defines columns used across all documents datasets
"""

from soongo_data.data_models.base import BaseModel, DataColumn
from soongo_data.utils.enums import DocumentType, mapper_factory


class DocumentsModel(BaseModel):
    path: DataColumn = DataColumn(
        raw_name="path",
        dtype="string",
        name="path",
        description='Internal document path within Soongo system'
    )
    external_url: DataColumn = DataColumn(
        raw_name="external_path",
        dtype="string",
        name="external_path",
        description='Document URL from external source'
    )
    filename: DataColumn = DataColumn(
        raw_name="filename",
        dtype="string",
        name="filename",
    )
    document_details: DataColumn = DataColumn(
        raw_name="document",
        dtype="object",
        name="document_details",
    )
    doc_type: DataColumn = DataColumn(
        raw_name="doc_type",
        dtype="string",
        name="doc_type",
        post_processing=mapper_factory(DocumentType),
    )
    size: DataColumn = DataColumn(
        raw_name="size",
        dtype="int",
        name="size",
    )
    hash_content: DataColumn = DataColumn(
        raw_name="hash_content",
        dtype="string",
        name="hash_content",
    )
