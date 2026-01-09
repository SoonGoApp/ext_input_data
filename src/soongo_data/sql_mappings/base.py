"""Module declaring the database to map tables onto"""

from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.schema import SchemaItem

# Create a metadata object
Base = declarative_base()


# Extend the base class to include a custom view class
class BaseView(Base):
    __abstract__ = True

    # Automatically add to __table_args__ the info that this is a view
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        table_args = getattr(cls, '__table_args__', ())

        if isinstance(table_args, dict):
            constraints = ()
            options = table_args
        elif isinstance(table_args, tuple):
            if table_args and isinstance(table_args[-1], dict):
                *constraints, options = table_args
            else:
                constraints = table_args
                options = {}
        else:
            constraints = ()
            options = {}

        info = dict(options.get('info', {}))
        info['is_view'] = True
        options['info'] = info

        if constraints:
            cls.__table_args__ = (*constraints, options)
        else:
            cls.__table_args__ = options


class CustomSchema(SchemaItem):
    def __init__(self, schema_name):
        self.schema_name = schema_name

    def _set_parent(self, table, **kw):
        # Set the schema for the table
        table.schema = self.schema_name


# Use the custom SchemaItem to define a schema
publ_schema = CustomSchema('publ')
