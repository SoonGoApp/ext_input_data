""" BaseModel

Defines the base class of our DataModels classes which lists DataColumns
for a specific object
"""
import typing
from dataclasses import asdict, dataclass, fields


@dataclass(frozen=True)
class BaseModel:

    def columns(self):
        for column in fields(self):
            yield getattr(self, column.name)


@dataclass
class DataColumn:
    """ Data Column object identifies the type and clean names of columns in
    the raw data

    :ivar raw_name: string name of the column in the raw data
    :ivar dtype: pandas type of the column
    :ivar clean_name: post processing name of the column in the raw_data
    :ivar post_processing: a function to process the raw data with post import.
        If None, no post_processing.
    :ivar description: an optional text describing the column content
    :ivar optional: whether that DataColumn is optional. Used when parsing
    pdf or when checking data integrity.
    :ivar memorization: whether that DataColumn should be memorized across
    lines when parsing pdf.
    :ivar overwrite: whether overwriting the value of that DataColumn should
    be memorized when parsing pdf.
    """
    raw_name: str
    dtype: str
    name: str
    post_processing: typing.Optional[typing.Callable] = None
    description: typing.Optional[str] = None
    optional: bool = False
    memorization: typing.Optional[str] = None
    overwrite: str = 'forbid'
    # Json dtype does not exist in pandas, must be added as separate attribute
    is_json: bool = False

    def __post_init__(self):
        """ Run post initialization attribute value checks

        :raise ValueError: if memorization is not None, page, or doc or
        overwrite not in ('forbid', 'allow', 'preserve')
        """
        authorized_mem_values = (None, 'page', 'doc')
        if self.memorization not in authorized_mem_values:
            raise ValueError(
                f'Memorization value must be one of {authorized_mem_values} '
                f'but {self.memorization} was passed'
            )

        authorized_overwrite_values = ('forbid', 'allow', 'preserve')
        if self.overwrite not in authorized_overwrite_values:
            raise ValueError(
                f'Overwrite value must be one of {authorized_overwrite_values}'
                f' but {self.overwrite} was passed'
            )

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return (
            isinstance(other, DataColumn)
            and self.name == other.name
        )

    def return_variant(
        self,
        **kwargs,
    ) -> typing.Self:
        """ Return an alternative DataColumn with an alternative name,
            post processing, or other param.

        :param raw_name: string name of the column in the raw data
        :param dtype: pandas type of the column
        :param clean_name: post processing name of the column in the raw_data
        :param post_processing: a function to process the raw data with post
            import processing. If None, no post_processing.
        """
        data_col_params = asdict(self)
        data_col_params.update(kwargs)
        return DataColumn(**data_col_params)
