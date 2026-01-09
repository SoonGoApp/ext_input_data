import logging
import os
import re
import typing
from dataclasses import dataclass

import numpy as np
import pandas as pd

from soongo_data.connectors.__base__.check_utils import (check_columns,
                                                         check_no_dup_values,
                                                         get_record_date,
                                                         set_record_cols)
from soongo_data.data_models.base import DataColumn
from soongo_data.utils.aws import load_file_from_s3
from soongo_data.utils.enums import SynchronizationTypes
from soongo_data.utils.images import base64_image_encode
from soongo_data.utils.imports import MissingImport, safe_import
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.type import get_dtype_null

mistralai = safe_import(
    module_name='mistralai',
    min_major_version=1,
    min_minor_version=7,
)
pytesseract = safe_import(
    module_name='pytesseract',
    min_major_version=0,
    min_minor_version=3,
)
pdf2image = safe_import(
    module_name='pdf2image',
    min_major_version=1,
    min_minor_version=16,
)
pdfplumber = safe_import(
    module_name='pdfplumber',
    min_major_version=0,
    min_minor_version=11,
)


@dataclass
class PDFParsingParams:

    cols: typing.Collection[DataColumn]
    match_func: typing.Callable
    scope: str = 'line'

    def __post_init__(self):
        """ Run post initialization attribute value checks

        :raise ValueError: if scope is not page, or line
        """
        authorized_scopes = ('page', 'line')
        if self.scope not in authorized_scopes:
            raise ValueError(
                f'Scope value must be one of {authorized_scopes} '
                f'but {self.scope} was passed'
            )


class UnauthorizedOverwrite(Exception):

    def __init__(
        self: typing.Self,
        field_value: typing.Any,
        field_name: str,
        previous_value: typing.Any,
    ):
        message = (
            f'Trying to set value {field_value} on col {field_name} '
            f'but value {previous_value} had already been set'
        )
        super().__init__(message)


class MissingColumnError(Exception):

    def __init__(
        self: typing.Self,
        col_name: str,
    ):
        message = (
            f'Column {col_name} is mandatory but absent in df'
        )
        super().__init__(message)


class PDFInput:
    """ A PDFInput is a class which collects DataFrame information from pdf
    file(s).

    It is initiated from a list of ParsingParams, which contains a list of
    DataColumns to match, a scope attribute (whether they apply on a text
    line or a page), and a matching function (generally a regex) which returns
    values for these DataColumns upon a match.

    At init, the PDFInput stores page level ParsingParams and line level
    parsing params in a dictionary params_dict. When parsing a document,
    load_pdf first call update_values with a page scope passing it the page as
    text, and the text inputs stores the values for all the page scope parsing
    params, and the same applies then to parsing params with a line scope on a
    line by line basis. When all information for mandatory data column is com
    plete, the PDFInput stores the dataframe line in a data_lst as a dictionary
    erases data column with no memorization options and move on to the next
    line until the document is over and all data was stored in data_lst.
    PDFInput can then be turned into a dataframe using the method to_df.
    """

    def __init__(
        self: typing.Self,
        parsing_params: typing.Collection[PDFParsingParams],
        logger: logging.Logger,
    ):
        """ Generates hidden attributes for memorization and DataFrame
        construction"""
        self.logger: logging.Logger = logger
        self.memorized_values: typing.Dict[str, typing.Any] = {}
        self.col_lst: typing.List[DataColumn] = []
        self.no_mem_col_lst: typing.List[DataColumn] = []
        self.page_mem_col_lst: typing.List[DataColumn] = []
        self.params_dict: typing.Dict[str, typing.List[PDFParsingParams]] = {}
        for param in parsing_params:
            self.col_lst.extend(param.cols)
            self.no_mem_col_lst.extend(
                 [col for col in param.cols if col.memorization is None]
            )
            self.page_mem_col_lst.extend(
                 [col for col in param.cols if col.memorization == 'page']
            )
            self.params_dict[param.scope] = self.params_dict.get(
                param.scope,
                [],
            ) + [param]

        self.mandatory_col_names: typing.Set[str] = {
            col.name for col in self.col_lst if not col.optional
        }
        self.data_lst: typing.List[typing.Dict[str: typing.Any]] = []

    def is_complete(self):
        return self.mandatory_col_names.issubset(self.memorized_values.keys())

    def update_values(
        self: typing.Self,
        scope: str,
        text_to_parse: str,
    ) -> None:
        """ Update the memorized_values dict by matching the text using the
        functions in the parsing params.

        :param scope: whether the passed text is a page or a line
        :param text_to_parse: string text to parse to attempt to match the
        matching functions in the parsing params

        :raises UnauthorizedOverwrite: if a value is matched for a data column
        for whom a value was already memorized and that data column overwrite
        attribute is 'forbid'

        :returns: None but updates the internal values
        """

        for parsing_param in self.params_dict.get(scope, []):
            text_match = self.match_text_inputs(
                parsing_param=parsing_param,
                text_to_parse=text_to_parse,
                logger=self.logger,
            )

            if text_match is None:
                continue

            for data_col in parsing_param.cols:

                if data_col.name not in self.memorized_values.keys():
                    self.memorized_values[data_col.name] = (
                        text_match[data_col.name]
                    )
                    if self.is_complete():
                        self.gen_new_line()

                elif data_col.overwrite == 'preserve':
                    # If preserve, keep first occurence and ignore subsequent
                    continue

                elif data_col.overwrite == 'allow':
                    self.memorized_values[data_col.name] = (
                        text_match[data_col.name]
                    )
                    # No need to gen new_line because value already existed

                else:  # Value already existed but overwrite is forbidden
                    raise UnauthorizedOverwrite(
                        field_value=text_match[data_col.name],
                        field_name=data_col.name,
                        previous_value=self.memorized_values[data_col.name],
                    )

    @staticmethod
    def match_text_inputs(
        parsing_param: PDFParsingParams,
        text_to_parse: str,
        logger: logging.Logger,
    ) -> typing.Optional[typing.Dict[str, typing.Any]]:
        """ Attempts to match text input to text, return values if any match

        :param parsing_param: ParsingParam with DataCols to fil and matching
        function to extract values from text
        :param text_to_parse: page or line text to parse
        :param logger: logger

        :raises ValueError: if the number of values returned by the matching
        function does not match the number of columns

        :returns: None if no match, values if match
        """
        col_name_lst = [col.name for col in parsing_param.cols]
        try:
            values = parsing_param.match_func(text_to_parse)

        except Exception as error:
            logger.debug(
                'Matching func raised error %s when parsing'
                'pdf text %s for cols %s',
                error,
                text_to_parse,
                col_name_lst,
            )

        else:

            if values is None:
                return

            if len(values) != len(col_name_lst):
                raise ValueError(
                    f'Matching func only returned '
                    f'{len(values)} elements whilst '
                    f'{len(col_name_lst)} were expected when '
                    f'parsing pdf text {text_to_parse} for cols '
                    f'{col_name_lst}',
                )

            return dict(zip(col_name_lst, values))

    def gen_new_line(self):
        """ Generate a new dataframe line.

        """
        # Copy mandatory otherwise changes to self.memorized_values
        # propagate to all elements in the list
        self.data_lst.append(self.memorized_values.copy())
        for col in self.no_mem_col_lst:
            if col.name in self.memorized_values:
                self.memorized_values.pop(col.name)

    def reset_page(self):
        for col in self.page_mem_col_lst:
            self.memorized_values.pop(col.name)

    def to_df(self):
        """ Transform the text input into DataFrame"""

        df = pd.DataFrame(self.data_lst)
        for col in self.col_lst:
            if col.name not in df.columns:
                if col.optional:
                    df[col.name] = get_dtype_null(col.dtype)
                else:
                    raise MissingColumnError(col.name)

        return df


class ParserFactory:

    def __init__(self, pattern: str):
        self.pattern = re.compile(pattern)

    def __call__(self, line: str) -> typing.Optional[typing.Collection]:
        pattern_match = re.search(
            self.pattern,
            line,
        )
        if pattern_match:
            return pattern_match.groups()


def parse_pdf(
    file_path: str,
    param_lst: typing.Collection[typing.Collection[PDFParsingParams]],
    read_param_lst: typing.Collection[dict],
    record_dates: typing.List[str],
    check_len_dict: typing.Mapping[str, int],
    organization_name: str,
    connector_name: str,
    source_dataset: str,
    source_table: str,
    synchronization_type: SynchronizationTypes,
    s3_bucket: str,
    ocr_engine: typing.Optional[str] = None,
    ocr_processing: typing.Optional[typing.Callable] = None,
):
    """ Utility function to iterate through each param and attempt parsing
        the pdf.
    """
    # Loggers are non pickleable need to be regenerated for multiprocessing
    logger = gen_logger('pdf_parser')
    for param_index, param_set in enumerate(param_lst):

        try:
            df = load_pdf(
                logger=logger,
                file_path=file_path,
                parsing_params=param_set,
                record_dates=record_dates,
                organization_name=organization_name,
                connector_name=connector_name,
                source_dataset=source_dataset,
                source_table=source_table,
                synchronization_type=synchronization_type,
                ocr_engine=ocr_engine,
                s3_bucket=s3_bucket,
                ocr_processing=ocr_processing,
                **read_param_lst[param_index],
            )

            file_check = check_len_dict[os.path.basename(file_path)]
            if isinstance(file_check, int):
                total_count = file_check
            else:
                total_count = 0
                for check in check_len_dict[
                    os.path.basename(file_path)
                ]:
                    check_col = [key for key in check.keys() if key != 'count']
                    check_col = check_col[0]
                    actual_count = (df[check_col] == check[check_col]).sum()
                    expected_count = check['count']
                    total_count += expected_count

                    if actual_count != expected_count:
                        raise ValueError(
                            f'Expected {expected_count} rows from '
                            f'file {file_path} for column {check_col} value '
                            f'{check[check_col]} but {actual_count} collected'
                        )

            if total_count != len(df):
                raise ValueError(
                    f'Expected {total_count} rows in the entire '
                    f'file {file_path} but {len(df)} collected'
                )

            return df

        except (
            KeyError,
            UnauthorizedOverwrite,
            MissingColumnError,
        ) as error:
            logger.debug(
                'Format %d failed for file %s on %s, attemping next format',
                param_index,
                file_path,
                error,
            )
            if (param_index + 1) == len(param_lst):
                logger.error(
                    'Could not parse file %s using any of the %d'
                    'provided formats',
                    file_path,
                    (param_index + 1),
                )
                raise  # Raise original error for traceback


def load_pdf(
    logger: logging.Logger,
    file_path: str,
    parsing_params: typing.Collection[PDFParsingParams],
    record_dates: typing.List[str],
    connector_name: str,
    source_dataset: str,
    source_table: str,
    synchronization_type: SynchronizationTypes,
    organization_name: str,
    s3_bucket: str,
    ocr_engine: typing.Optional[str] = None,
    ocr_processing: typing.Optional[typing.Callable] = None,
    **read_params,
) -> pd.DataFrame:
    """ Read PDF files.

    The load pdf logic loads the file and turns its pages to text either
    through parsing using pdf plumber (default) or OCR (to use in case) of
    copy protection. 4 different types of parsing inputs are accepted

    :param file_path: str path to the csv file
    :param parsing_params: list of PDFParsingParams to match page by page
    or line by line depending on scope to extract information from the pdf
    :param record_dates: list of str column names to compute the record
        date from.
    :param connector_name: str name of the connector the data was
        extracted from.
    :param source_dataset: str name of the dataset the data was
        extracted from.
    :param source_table: str name of the table the data was
        extracted from.
    :param synchronization_type: SynchronisationTypes enum value
    :param ocr_engine: which engine to use for Optical Character Recognition.
        pass None for no OCR, tesseract or mistral.
    """
    if pdfplumber is None:
        raise MissingImport('pdfplumber')
    if pdf2image is None:
        raise MissingImport('pdf2image')
    if pytesseract is None:
        raise MissingImport('pytesseract')

    with pdfplumber.open(file_path) as pdf:
        pdf_input = PDFInput(
            parsing_params=parsing_params,
            logger=logger,
        )
        if ocr_engine is not None:
            # Convert PDF pages to images and images to text using OCR
            if s3_bucket:
                file_content = load_file_from_s3(
                    s3_bucket=s3_bucket,
                    file_path=file_path,
                    return_type='raw_bytes'
                )
                page_images = pdf2image.convert_from_bytes(
                    file_content,
                    **read_params
                )
            else:
                page_images = pdf2image.convert_from_path(
                    file_path,
                    **read_params
                )

            if not ocr_processing:
                def ocr_processing(page):
                    return page

            if ocr_engine == 'tesseract':
                pages = [
                    pytesseract.image_to_string(
                        ocr_processing(page),
                        lang='fra',
                        config='--psm 4',
                    ) for page in page_images
                ]
            elif ocr_engine == 'mistral':
                pages = [
                    mistral_ocr(
                        ocr_processing(page)
                    ) for page in page_images
                ]
        else:
            pages = [
                page.extract_text(**read_params) for page in pdf.pages
            ]
        for page_text in pages:

            pdf_input.update_values(
                scope='page',
                text_to_parse=page_text,
            )

            for line in page_text.split('\n'):

                pdf_input.update_values(
                    scope='line',
                    text_to_parse=line,
                )

    df = pdf_input.to_df()

    df = check_columns(
        df=df,
        col_lst=pdf_input.col_lst,
        organization_name=organization_name,
    )
    df = get_record_date(data_df=df, record_dates=record_dates)
    df = set_record_cols(
        df=df,
        connector_name=connector_name,
        source_dataset=source_dataset,
        source_table=source_table,
        synchronization_type=synchronization_type,
    )

    check_no_dup_values(df.columns)

    return df


def mistral_ocr(
    image_array: np.ndarray,
) -> str:
    """ OCR function using mistral engine

    :param image: image to OCR
    :param lang: language to use for the OCR

    :returns: OCRed text
    """
    image_base64 = base64_image_encode(image_array=image_array)

    api_key = os.environ["MISTRAL_API_KEY"]
    client = mistralai.Mistral(api_key=api_key)

    ocr_response = client.ocr.process(
        model="mistral-ocr-latest",
        document={
            "type": "image_url",
            "image_url": f"data:image/jpeg;base64,{image_base64}",
        }
    )

    return ocr_response.model_dump_json()['text']
