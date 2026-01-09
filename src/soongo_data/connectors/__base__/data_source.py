"""
Defines the base class for data sources.
This class is responsible for holding (i) the parsing logic for a specific
data source and (ii) a logic to fetch a path where to get this data.
"""
from __future__ import annotations

from itertools import zip_longest
import logging
import multiprocessing
import io
import os
import re
from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from typing import (
    TYPE_CHECKING, Callable, Dict, List, Mapping, Optional, Self, Sequence,
    Tuple, Type, Union
)
import zipfile

import pandas as pd
import requests

from soongo_data.connectors.__base__.api_utils import load_from_api, APICacher
from soongo_data.connectors.__base__.check_utils import (
    RECORD_COLS,
    check_col_matching,
    check_columns,
    check_no_dup_values,
    get_record_date,
    set_record_cols
)
from soongo_data.connectors.__base__.pdf_utils import (
    PDFParsingParams, parse_pdf
)
from soongo_data.data_models import CollaboratorsModel, SoonGoRecordsModel
from soongo_data.data_models.base import DataColumn
from soongo_data.utils.api import APIPaginatorTemplate
from soongo_data.utils.aws import (
    check_file_exists, load_file_from_s3, get_s3_file_creation_date, read_file_from_s3
)
from soongo_data.utils.imports import MissingImport, safe_import
from soongo_data.utils.type import DateConverter
from soongo_data.utils.typing_utils import ExceptionType

if TYPE_CHECKING:
    from soongo_data.connectors.__base__.dataset import Dataset


pdfplumber = safe_import(
    module_name='pdfplumber',
    min_major_version=0,
    min_minor_version=11,
)


@dataclass
class FixedWidthParams:

    col: DataColumn
    start: int
    end: int

    def __post_init__(self):
        """ Run post initialization attribute value checks

        :raise ValueError: if scope is not page, or line
        """
        if self.start < 0:
            raise ValueError(
                f'start must be a positive integer but {self.start} was passed'
            )
        if self.end <= self.start:
            raise ValueError(
                f'end must be greater than start but {self.end} was passed '
                f'and start was {self.start}'
            )


class DataSource:
    """
    Base class for data sources.
    """
    CONNECTOR_NAME = None
    DATASET_NAME = None
    DATASET_TYPE = None
    NAME = None

    def __init__(
        self,
        folder: str,
        logger: logging.Logger,
        organization_name: str,
        s3_bucket: Optional[str] = None,
    ):
        """
        Initialize the DataSource class.

        :param folder: The folder path where the data is stored.
        :param organization_name: The name of the organization.
        :param log_file: The path to the log file (optional).
        :param s3_bucket: The S3 bucket name (optional).
        """
        self.folder = folder
        self.logger = logger
        self.organization_name = organization_name
        self.s3_bucket = s3_bucket

        for attr_name in [
            'NAME', 'DATASET_NAME', 'DATASET_TYPE', 'CONNECTOR_NAME'
        ]:
            if getattr(self, attr_name) is None:
                raise AttributeError(
                    f'{attr_name} must be defined in the subclass'
                )

    def fetch(self: Self) -> Sequence[str]:
        try:
            return self.__fetch__()
        except FileNotFoundError:
            self.logger.error(
                'No file found for dataset %s and source %s',
                self.DATASET_NAME,
                self.NAME
            )
            return tuple()

    @abstractmethod
    def __fetch__(self: Self) -> Sequence[str]:
        """
        Fetch data from the data source.
        This method should be implemented in subclasses.

        This returns either a file_path (for CSV_UPLOAD or EDI) or a string url
        (for API).

        :return: The path(s) to the data source.
        """
        raise NotImplementedError("Subclasses must implement this method.")

    def parse(
        self: Self,
        data_path: Optional[Sequence[str]] = None,
        **parsing_kwargs,
    ) -> pd.DataFrame:
        if data_path is None:
            data_path = self.fetch()

        if len(data_path) == 0:
            return pd.DataFrame()

        return self.__parse__(data_path, **parsing_kwargs)

    @abstractmethod
    def __parse__(
        self: Self,
        data_path: Sequence[str],
        **parsing_kwargs,
    ) -> pd.DataFrame:
        """
        Parse the data from the data source.
        This method should be implemented in subclasses.

        :param data_path: The path to the data source (optional). If None
        provided then uses the fetch method to get the path.
        :return: The parsed data.
        """
        raise NotImplementedError("Subclasses must implement this method.")

    def agg_and_meld(
        self,
        eligible_files: Sequence[str],
        id_cols: List[DataColumn],
        value_col: DataColumn,
        var_col: DataColumn,
        record_dates: Sequence[str],
        meld: bool = True,
        skip_cols: Optional[Sequence[str]] = None,
        error_skipping: Sequence[Type[ExceptionType]] = tuple(),
        zip_password: Optional[str] = None,
        **read_params,
    ) -> pd.DataFrame:
        """ Import target csv table and melt non id cols. Returns table
        and adds attribute with table name into Dataset

        :param logger: logging.Logger
        :param file_path: str path to the monthly driver mileage data
        :param id_cols: List of DataColumns, part of the target csv tables,
            which should be kept as is in the final dataset
        :param value_name: name to be given to the long form column regrouping
            the values of all non id columns
        :param var_name: name to give to the long form column regrouping
            the header name of all non id columns
        :param meld: boolean melds if True, else just imports it
        """
        if not eligible_files:
            self.logger.warning(
                'No files to concatenate in passed list'
            )
            return pd.DataFrame(
                columns=[col.name for col in id_cols] + [value_col, var_col],
            )
        self.logger.info(
            'Aggregate %d csv files: %s',
            len(eligible_files),
            eligible_files,
        )
        list_dfs = []

        for file_path in eligible_files:
            try:
                if meld:
                    df = self.meld_df(
                        file_path=file_path,
                        id_cols=id_cols,
                        value_col=value_col,
                        var_col=var_col,
                        skip_cols=skip_cols,
                        record_dates=record_dates,
                        zip_password=zip_password,
                        **read_params,
                    )
                else:
                    df = self.load_table(
                        file_path=file_path,
                        col_lst=id_cols,
                        skip_cols=skip_cols,
                        record_dates=record_dates,
                        zip_password=zip_password,
                        **read_params,
                    )
                list_dfs.append(df)
            except Exception as error:
                if any(
                    [
                        isinstance(error, accepted_type)
                        for accepted_type in error_skipping
                    ]
                ):
                    self.logger.warning(
                        (
                            'Data parsing from file %s failed on error %s, '
                            'but continuing to next file.'
                        ),
                        file_path,
                        error,
                    )
                    continue

                else:
                    raise

        if list_dfs == []:
            self.logger.warning(
                'No dataframes were successfully parsed from the files'
            )
            return pd.DataFrame(
                columns=[col.name for col in id_cols],
            )

        df = pd.concat(
            list_dfs,
            axis=0,
            ignore_index=True,
        )

        return df

    def meld_df(
        self: Self,
        file_path: str,
        id_cols: List[DataColumn],
        value_col: DataColumn,
        var_col: DataColumn,
        record_dates: Sequence[str],
        skip_cols: Optional[List[str]] = None,
        zip_password: Optional[str] = None,
        **read_params,
    ):
        df = self.load_table(
            file_path=file_path,
            col_lst=id_cols,
            check_cols=False,
            skip_cols=skip_cols,
            record_dates=record_dates,
            zip_password=zip_password,
            **read_params,
        )
        source_vars = [
            SoonGoRecordsModel.record_date.name,
            SoonGoRecordsModel.file_creation_date.name
        ] + RECORD_COLS
        id_vars = [col.name for col in id_cols] + source_vars
        if (
            (CollaboratorsModel.employee_full_name.name not in id_vars)
            and
            (CollaboratorsModel.employee_full_name.name in df.columns)
        ):
            id_vars += [CollaboratorsModel.employee_full_name.name]
        df = pd.melt(
            frame=df,
            id_vars=id_vars,
            value_name=value_col.name,
            var_name=var_col.name,
        )
        for col in [value_col, var_col]:
            if col.post_processing:
                df[col.name] = col.post_processing(df[col.name])
            df[col.name] = df[col.name].astype(col.dtype)

        return df

    def load_table(
        self: Self,
        file_path: str,
        col_lst: List[DataColumn],
        record_dates: List[str],
        skip_cols: Optional[List[str]] = None,
        check_cols: bool = True,
        use_sheets: Optional[List[str]] = None,
        zip_password: Optional[str] = None,
        **read_params,
    ) -> pd.DataFrame:
        """ Load a csv or excel table as a pandas DataFrame

        :param file_path: str path to the csv file
        :param logger: logger
        :param col_lst: list of DataColumns this file contains
        :param record_dates: list of str column names to compute the record
            date from.
        :param skip_cols: raw str col name to skip, if any
        :param check_cols: check whether col_lst matches df cols.
        :param connector_name: str name of the connector the data was
            extracted from.
        :param source_dataset: str name of the dataset the data was
            extracted from.
        :param use_sheets: list of str sheet names to use in case of an excel.
            To use all sheets, pass ['*']

        :raises ValueError: if different number of columns in col_lst than in
        df after skipping columns, or if column raw_names don't match columns
        in df

        :returns: Pandas Dataframe with the loaded data, normalized at expected
            name and type.
        """
        EXCEL_EXTENSIONS = (
            'xlsx', '.xls', '.ods', '.xlsm', '.xlsb', '.odf', '.odt'
        )

        if self.s3_bucket:
            if not check_file_exists(self.s3_bucket, file_path):
                self.logger.error(
                    'Did not find any file under path %s',
                    file_path,
                )
                return pd.DataFrame(
                    columns=[col.name for col in col_lst] + RECORD_COLS,
                )
            file_creation_date = get_s3_file_creation_date(
                self.s3_bucket,
                file_path,
            )

        elif not os.path.isfile(file_path):
            self.logger.error(
                'Did not find any file under path %s',
                file_path,
            )
            return pd.DataFrame(
                columns=[col.name for col in col_lst] + RECORD_COLS,
            )

        else:
            file_creation_date = datetime.fromtimestamp(
                os.stat(file_path).st_ctime
            )

        skip_cols = [] if skip_cols is None else skip_cols
        default_params = {
            'header': 0,
            'index_col': False,
            'decimal': ',',
            'dtype': return_dtypes(col_lst),
            'usecols': lambda x: x not in skip_cols if skip_cols else True,
        }
        csv_params = {
            'encoding': 'latin_1',
            'sep': ';',
        }

        file_data = None

        if file_path.endswith('.zip'):
            extension_type = 'zip'
        elif file_path[-4:] in EXCEL_EXTENSIONS:
            extension_type = 'excel'
        else:
            extension_type = 'csv'

        # Handle zipped files
        if extension_type == 'zip':

            # Check if the file is on S3
            if self.s3_bucket:
                # Download the zip file from S3 into memory
                zip_data = load_file_from_s3(
                    s3_bucket=self.s3_bucket,
                    file_path=file_path,
                    return_type='bytes',
                )
                self.logger.info('Downloaded zip file from S3: %s', file_path)
            else:
                # Open the local zip file
                zip_data = file_path

            with zipfile.ZipFile(zip_data, 'r') as z:
                # Get the first file in the zip archive
                file_list = z.namelist()
                if not file_list:
                    self.logger.error('Zip file is empty: %s', file_path)
                    return pd.DataFrame(columns=[col.name for col in col_lst] + RECORD_COLS)

                # Extract the first file (assuming it's the tabular file)
                extracted_file_name = file_list[0]
                self.logger.info('Extracting file %s from zip archive %s', extracted_file_name, file_path)

                # Handle password-protected zip files
                if zip_password:
                    z.setpassword(zip_password.encode())

                with z.open(extracted_file_name) as extracted_file:
                    # Read the extracted file as a binary stream
                    file_data = io.BytesIO(extracted_file.read())
                    if extracted_file_name[-4:] in EXCEL_EXTENSIONS:
                        extension_type = 'excel'
                    else:
                        extension_type = 'csv'

        if extension_type == 'excel':
            if self.s3_bucket and file_data is None:
                file_data = load_file_from_s3(
                    s3_bucket=self.s3_bucket,
                    file_path=file_path,
                    return_type='bytes',
                )  # Cannot path direct file_path to pandas otherwise goes through internet
            default_params.update(read_params)
            if use_sheets:
                # Passing sheet_name=None to read_excel to get a dict of df
                default_params.update({'sheet_name': None})
                df_dict = pd.read_excel(
                    file_path if file_data is None else file_data,
                    **default_params
                )

                df_lst = []
                for sheet_name, df in df_dict.items():
                    if (sheet_name in use_sheets) or ('*' in use_sheets):
                        df[SoonGoRecordsModel.sheet_name.name] = sheet_name
                        df_lst.append(df)

                df = pd.concat(
                    objs=df_lst,
                    axis=0,
                    ignore_index=True,
                )
            else:
                df = pd.read_excel(
                    file_path if file_data is None else file_data,
                    **default_params
                )

        else:
            default_params.update(csv_params)
            default_params.update(read_params)

            if self.s3_bucket and file_data is None:
                # Cannot path direct file_path to pandas otherwise goes
                # through internet and access is denied (403)
                file_data = load_file_from_s3(
                    s3_bucket=self.s3_bucket,
                    file_path=file_path,
                    return_type='string',
                    encoding=default_params['encoding'],
                )
            df = pd.read_csv(
                file_path if file_data is None else file_data,
                **default_params,
            )

        # usecols interfers with skip_cols hence needs a second pass
        if ('usecols' in read_params) and skip_cols:
            df = df[[col for col in df.columns if col not in skip_cols]]

        self.logger.info(
            'Successfully imported %d lines from %s',
            len(df),
            file_path,
        )
        if check_cols:
            check_col_matching(
                gac_col_lst=col_lst,
                raw_df=df,
                logger=self.logger,
            )

        for table_col in col_lst:
            df.rename(
                columns={table_col.raw_name: table_col.name},
                inplace=True,
            )

        df = check_columns(
            df=df,
            col_lst=col_lst,
            organization_name=self.organization_name,
        )

        df = get_record_date(data_df=df, record_dates=record_dates)
        df = set_record_cols(
            df=df,
            connector_name=self.CONNECTOR_NAME,
            source_dataset=self.DATASET_NAME,
            source_table=self.NAME,
            synchronization_type=self.DATASET_TYPE,
        )
        df[SoonGoRecordsModel.file_creation_date.name] = file_creation_date

        check_no_dup_values(df.columns)

        return df

    def agg_pdf(
        self,
        eligible_files: Sequence[str],
        param_lst: Sequence[Sequence[PDFParsingParams]],
        read_param_lst: Sequence[dict],
        record_dates: List[str],
        check_len_dict: Mapping[str, int],
        ocr_engine: Optional[str] = None,
        parallelize: bool = True,
        ocr_processing: Optional[Callable] = None,
    ) -> pd.DataFrame:
        """ Import target pdf data and agg different files. Returns table
        and adds attribute with table name into Dataset

        :param eligible_files: list of file paths to fetch data from
        :param param_lst: Sequence of sequences of parsing params. Each
            sequence of parsing params corresponds to a file format to parse.
            The different formats are attempted until one matches.
        :param record_dates: list of str column names to compute the record
            date from.
        :param check_len_dict: Mapping of file_name to an expected number of
            records as integer. Used to confirm that all lines were indeed
            captured.
        :param ocr_engine: which engine to use for Optical Character Recognition. Only
            turn to True to bypasse PDF copy protection.
        :param read_params_lst: read params to use with each of the formats
            provided in param_lst; provided as a dict. Must provide a read
            param per parsing_param sequence.
        :param parallelize: whether to run aggregations in multiprocessing
        :param ocr_processing: function taking an image numpy ndarray
            and returning a modified ndarray. Used to improve OCR performance
            by denoising and thresholding.

        :raises ValueError: if read_param_lst len does not equal
        parsing_param_lst len.
        """
        start = datetime.now()
        if len(read_param_lst) != len(param_lst):
            raise ValueError(
                f'Must provide as many read_params as parsing params but'
                f' {len(read_param_lst)} read params provided and '
                f'{len(param_lst)} parsing params provided.'
            )

        if not eligible_files:
            self.logger.warning(
                'No files to concatenate in passed list'
            )
            col_set = set()
            for param in param_lst[0]:
                col_set = col_set.union([col.name for col in param.cols])
            return pd.DataFrame(
                columns=list(col_set),
            )

        file_name_set = {
           os.path.basename(file_path) for file_path in eligible_files
        }
        key_set = set(check_len_dict.keys())
        if file_name_set != key_set:
            missing_files = file_name_set.difference(
                key_set
            )
            missing_keys = key_set.difference(
                file_name_set
            )
            raise ValueError(
                f'The check len dict keys do not match the eligible files '
                f'list: {missing_files} have no key and {missing_keys} have '
                f'no file in the list'
            )

        self.logger.info(
            'Aggregate %d pdf files: %s',
            len(eligible_files),
            eligible_files,
        )
        if parallelize:
            os.environ['OMP_THREAD_LIMIT'] = '1'
            parse_args = [
                (
                    file,
                    param_lst,
                    read_param_lst,
                    record_dates,
                    check_len_dict,
                    self.organization_name,
                    self.CONNECTOR_NAME,
                    self.DATASET_NAME,
                    self.NAME,
                    self.DATASET_TYPE,
                    self.s3_bucket,
                    ocr_engine,
                    ocr_processing,
                )
                for file in eligible_files
            ]
            with multiprocessing.Pool(
                processes=multiprocessing.cpu_count()
            ) as pool:
                list_dfs = pool.starmap(parse_pdf, parse_args)
        else:
            list_dfs = [
                parse_pdf(
                    file_path=file,
                    param_lst=param_lst,
                    read_param_lst=read_param_lst,
                    record_dates=record_dates,
                    check_len_dict=check_len_dict,
                    organization_name=self.organization_name,
                    connector_name=self.CONNECTOR_NAME,
                    source_dataset=self.DATASET_NAME,
                    synchronization_type=self.DATASET_TYPE,
                    source_table=self.NAME,
                    ocr_engine=ocr_engine,
                    s3_bucket=self.s3_bucket,
                    ocr_processing=ocr_processing,
                )
                for file in eligible_files
            ]

        df = pd.concat(
            list_dfs,
            axis=0,
            ignore_index=True,
        )

        self.logger.info('Process completes in %s', datetime.now() - start)
        return df

    def agg_pdf_table(
        self: Self,
        eligible_files: Sequence[str],
        col_lst: Sequence[DataColumn],
        record_dates: List[str],
        bounding_box: Optional[Tuple[int, int, int, int]] = None,
        skip_table: Optional[Callable] = None,
        skip_rows: Optional[Callable] = None,
        skip_cols: Optional[Callable] = None,
        **read_params,
    ) -> pd.DataFrame:
        """ Agg PDF table

        This pdf load logic aggregates tables contained within pdf files
        instead of going through a text pattern detection logic.
        To be preferred to text approach; use cropbox and read_params for
        calibration.

        :param eligible_files: list of file paths to extract data from
        :param col_lst: list of DataColumns to match in the pdf
        :param record_dates: list of str column names to compute the record
            date from.
        :param bounding_box: whether to crop the page (x0, top, x1, bottom).
        See pdfplumber bouding_box parameter description
        :param skip_table: callable returning indexes to drop from a list of
            lists
        :param skip_cols: callable returning a df with dropped cols
        :param skip_rows: callable returning a df with dropped rows
        """
        if pdfplumber is None:
            raise MissingImport('pdfplumber')

        if not eligible_files:
            self.logger.warning(
                'No files to concatenate in passed list'
            )
            return pd.DataFrame(
                columns=[col.name for col in col_lst],
            )

        table_lst = []
        for file_path in eligible_files:

            if self.s3_bucket:
                # TODO: make robust to S3, likely to generate an error
                file_content = load_file_from_s3(
                    s3_bucket=self.s3_bucket,
                    file_path=file_path,
                    return_type='raw_bytes',
                )
            else:
                # Let pdfplumber directly open the file_content
                file_content = file_path

            with pdfplumber.open(file_content) as pdf:

                for page in pdf.pages:

                    if bounding_box:
                        page = page.crop(bounding_box)
                    table_lst.extend(
                        page.extract_tables(**read_params)
                    )

        if skip_table:
            # Need to reverse order to avoid index shifting issue
            for table_index in sorted(skip_table(table_lst), reverse=True):
                table_lst.pop(table_index)

        df_lst = []
        for table in table_lst:
            table_df = pd.DataFrame(table)
            if skip_rows:
                table_df = skip_rows(table_df)
            if skip_cols:
                table_df = skip_cols(table_df)
            table_df.columns = [col.name for col in col_lst]
            df_lst.append(table_df)

        df = pd.concat(
            df_lst,
            axis=0,
            ignore_index=True,
        )

        df = check_columns(
            df=df,
            col_lst=col_lst,
            organization_name=self.organization_name,
        )
        if self.s3_bucket:
            df[SoonGoRecordsModel.file_creation_date.name] = get_s3_file_creation_date(
                self.s3_bucket,
                file_path,
            )
        else:
            df[SoonGoRecordsModel.file_creation_date.name] = datetime.fromtimestamp(
                os.stat(file_path).st_ctime
            )
        df = get_record_date(data_df=df, record_dates=record_dates)
        df = set_record_cols(
            df=df,
            connector_name=self.CONNECTOR_NAME,
            source_dataset=self.DATASET_NAME,
            source_table=self.NAME,
            synchronization_type=self.DATASET_TYPE,
        )

        check_no_dup_values(df.columns)

        return df

    def agg_from_api(
        self: Self,
        url_lst: Sequence[str],
        col_lst: List[DataColumn],
        record_dates: List[str],
        paginator: Optional[APIPaginatorTemplate] = None,
        parallelize: bool = True,
        skip_cols: List[str] = tuple(),
        response_keys: Sequence[str] = tuple(),
        params_tup: Sequence[dict] = (None, ),
        headers: Optional[dict] = None,
        auth: Optional[requests.auth.HTTPBasicAuth] = None,
        api_cacher: Optional[APICacher] = None,
        put_values_lst: Optional[List[Dict[str, str]]] = None,
    ) -> pd.DataFrame:
        """ Aggregate a number of responses from multiple API urls

            :param url_lst: sequence url path string, including base url and
                route
            :param params: query params provided as a dictionary
            :param headers: query headers as a dictionary
            :param auth: requests auth object if auth not provided in headers
            :param col_lst: list of DataColumns this file contains
            :param record_dates: list of str column names to compute the record
                date from.
            :param skip_cols: raw str col name to skip, if any
            :param check_cols: check whether col_lst matches df cols.
            :param paginator: Paginator object yielding the responses

            :returns: queried data as a pandas DataFrame
        """
        if put_values_lst is None:
            put_values_lst = []
        load_args = [
            {
                "organization_name": self.organization_name,
                "url": url,
                "col_lst": col_lst,
                "record_dates": record_dates,
                "connector_name": self.CONNECTOR_NAME,
                "source_dataset": self.DATASET_NAME,
                "source_table": self.NAME,
                "synchronization_type": self.DATASET_TYPE,
                "skip_cols": skip_cols,
                "response_keys": response_keys,
                "params": params,
                "headers": headers,
                "auth": auth,
                "check_cols": False,
                "paginator": paginator,
                "api_cacher": api_cacher,
                "put_values": put_values,
            }
            for url in url_lst
            for params, put_values in zip_longest(params_tup, put_values_lst)
        ]

        if parallelize:
            with multiprocessing.Pool(
                processes=multiprocessing.cpu_count()
            ) as pool:
                async_results = [
                    pool.apply_async(
                        load_from_api,
                        kwds=kwargs
                    )
                    for kwargs in load_args
                ]
                df_lst = []
                error_count = 0
                for async_result in async_results:
                    try:
                        df_lst.append(async_result.get())
                    except Exception as error:
                        self.logger.error(
                            'API data loading failed on error: %s',
                            error,
                            exc_info=True,
                        )
                        error_count += 1
                if error_count > 0:
                    self.logger.warning(
                        '%d API data loading calls failed out of %d',
                        error_count,
                        len(async_results),
                    )

        else:
            df_lst = [
                load_from_api(**kwargs)
                for kwargs in load_args
            ]

        df_lst = [df for df in df_lst if not df.empty]
        df = pd.concat(df_lst, axis=0, ignore_index=True)

        df = check_columns(
            df=df,
            col_lst=col_lst,
            organization_name=self.organization_name,
        )
        df = get_record_date(data_df=df, record_dates=record_dates)

        return df

    def agg_from_fixed_width(
        self: Self,
        param_lst: Sequence[FixedWidthParams],
        eligible_files: List[str],
        record_dates: List[str],
        line_pattern: Optional[str] = None,
        encoding: str = 'utf-8',
        **read_params,
    ) -> pd.DataFrame:
        if not eligible_files:
            self.logger.warning(
                'No files to concatenate in passed list'
            )
            return pd.DataFrame(
                columns=[param.col.name for param in param_lst],
            )
        self.logger.info(
            'Aggregate %d csv files: %s',
            len(eligible_files),
            eligible_files,
        )
        list_dfs = []

        for file_path in eligible_files:
            df = self.load_from_fixed_width(
                file_path=file_path,
                param_lst=param_lst,
                record_dates=record_dates,
                line_pattern=line_pattern,
                encoding=encoding,
                **read_params,
            )
            list_dfs.append(df)

        df = pd.concat(
            list_dfs,
            axis=0,
            ignore_index=True,
        )

        return df

    def load_from_fixed_width(
        self: Self,
        param_lst: Sequence[FixedWidthParams],
        file_path: str,
        record_dates: List[str],
        line_pattern: Optional[str] = None,
        encoding: str = 'utf-8',
        **read_params,
    ):
        """ Load a fixed width table as a pandas DataFrame

        :param param_lst: Sequence of FixedWidthParams
        :param file_path: str path to the fixed width file
        :param record_dates: list of str column names to compute the record
            date from.
        :param skip_cols: raw str col name to skip, if any
        :param prefix: prefix to add to the column names
        """
        if self.s3_bucket:
            if not check_file_exists(self.s3_bucket, file_path):
                self.logger.error(
                    'Did not find any file under path %s',
                    file_path,
                )
            else:
                file_path = load_file_from_s3(
                    s3_bucket=self.s3_bucket,
                    file_path=file_path,
                    return_type='string',
                    encoding=encoding,
                )

        elif not os.path.isfile(file_path):
            self.logger.error(
                'Did not find any file under path %s',
                file_path,
            )
            return pd.DataFrame(
                columns=[col.col.name for col in param_lst] + RECORD_COLS,
            )

        if line_pattern:
            file_path = self.filter_lines(
                file_path=file_path,
                line_pattern=line_pattern,
                encoding=encoding,
            )

        df = pd.read_fwf(
            file_path,
            colspecs=[
                (param.start, param.end)
                for param in param_lst
            ],
            header=None,
            names=[
                param.col.name
                for param in param_lst
            ],
            **read_params,
            encoding=encoding,
        )

        df = check_columns(
            df=df,
            col_lst=[param.col for param in param_lst],
            organization_name=self.organization_name,
        )
        df = get_record_date(data_df=df, record_dates=record_dates)
        df = set_record_cols(
            df=df,
            connector_name=self.CONNECTOR_NAME,
            source_dataset=self.DATASET_NAME,
            source_table=self.NAME,
            synchronization_type=self.DATASET_TYPE,
        )

        check_no_dup_values(df.columns)

        return df

    @staticmethod
    def filter_lines(
        file_path: Union[str, StringIO],
        line_pattern: str,
        encoding: str,
    ) -> StringIO:
        """ Filter lines from a file or StringIO object

        :param file_path: str path to the file
        :param prefix: str regex to filter lines
        """
        if isinstance(file_path, str):
            with open(file_path, 'r', encoding=encoding) as file:
                lines = file.readlines()
        else:
            lines = file_path.readlines()

        filtered_lines = [
            line for line in lines if re.match(line_pattern, line)
        ]
        return StringIO(''.join(filtered_lines))


def attach_dataset(dataset: Type[Dataset]) -> Type[DataSource]:
    """
    Decorator to attach a DataSource to a parent DataSet (composition).

    :param dataset: child DataSet class to attach the DataSource to.

    :return: The decorated DataSource with an added DATASET_NAME attribute.
    the passed dataset class gains the DataSource as an attribute.
    """

    def decorate_attribute(data_source: Type[DataSource]) -> Type[DataSource]:

        def decorator():
            if hasattr(dataset, data_source.NAME):
                raise AttributeError(
                    f'Dataset {dataset.__name__} already has a '
                    f'{data_source.NAME} attribute'
                )

            # Modify DataSource class to add dataset attributes
            setattr(data_source, 'DATASET_NAME', dataset.NAME)
            setattr(data_source, 'DATASET_TYPE', dataset.TYPE)
            setattr(data_source, 'CONNECTOR_NAME', dataset.CONNECTOR_NAME)

            # Attach the DataSource to the DataSet
            setattr(
                dataset,
                data_source.NAME,
                data_source
            )
            return data_source

        return decorator()

    return decorate_attribute


def split_df(df: pd.DataFrame, split_cond: pd.Series) -> List[pd.DataFrame]:
    """ Split a DataFrame into multiple DataFrames based on a condition

    :param df: DataFrame to split
    :param split_cond: Series with the same index as df, with a boolean
        condition to split the DataFrame on

    :returns: list of DataFrames
    """
    split_indices = split_cond.cumsum()
    split_dfs = [
        df.loc[split_indices == index]
        for index in split_indices.unique()
    ]
    return split_dfs


def return_dtypes(
    data_col_lst: List[DataColumn],
) -> Dict:
    """ Return pandas style dtypes for import

    :param col_names: list of GacColumn attributes as str

    :raises ValueError: if attribute are repeated

    :returns: dtypes with column name and dtype
    """
    check_no_dup_values(data_col_lst)

    return {
        attr.name: attr.dtype
        for attr in data_col_lst
    }


def local_cache_decorator(
    cache_file_name: str,
    date_cols: List[str],
) -> Callable:
    """
    Parametrizable decorator to cache the results of a DataSource method
    in a local cache directory or an S3 bucket.

    :param cache_file_name: Name of the cache file to use.
    """
    def decorator(data_source_method: Callable) -> Callable:

        def local_cache_wrapper(
            self: DataSource,
            *args,
            **kwargs,
        ):
            if SoonGoRecordsModel.record_date.name not in date_cols:
                date_cols.append(SoonGoRecordsModel.record_date.name)

            cache_dir = os.path.join(self.folder, 'cache/')
            if self.s3_bucket:
                if check_file_exists(
                    s3_bucket=self.s3_bucket,
                    file_path=os.path.join(cache_dir, cache_file_name),
                ):
                    self.logger.info('Loading data from s3 cache')
                    byte_file = load_file_from_s3(
                        s3_bucket=self.s3_bucket,
                        file_path=os.path.join(cache_dir, cache_file_name),
                        return_type='bytes',
                    )
                    data_df = pd.read_csv(
                        byte_file,
                        sep=';',
                    )

                    for col in date_cols:
                        data_df[col] = DateConverter(r'%Y-%m-%d %H:%M:%S')(
                            data_df[col]
                        )
                    return data_df

            elif os.path.exists(os.path.join(cache_dir, cache_file_name)):
                self.logger.info('Loading data from local cache')
                data_df = pd.read_csv(
                        os.path.join(cache_dir, cache_file_name),
                        sep=';',
                    )

                for col in date_cols:
                    data_df[col] = DateConverter(r'%Y-%m-%d %H:%M:%S')(
                        data_df[col]
                    )

                return data_df

            else:
                data_df = data_source_method(self, *args, **kwargs)

                # Cache results
                os.makedirs(cache_dir, exist_ok=True)
                data_df.to_csv(
                    os.path.join(cache_dir, cache_file_name),
                    index=False,
                    sep=';',
                )

                return data_df

        return local_cache_wrapper

    return decorator
