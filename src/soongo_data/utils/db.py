""" Script to inject data from the input tables csv / dfs into a local database
"""
import json
import os
import typing
from contextlib import contextmanager
from functools import cached_property, lru_cache

import pandas as pd
from sqlalchemy import create_engine, DateTime
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker, class_mapper

from soongo_data.utils.logging_utils import gen_logger
from soongo_data.sql_mappings import KpisTable, OrganizationsTable, VehiclesTable
from soongo_data.utils.secrets_utils import get_local_secret


# Update db_config file to update database
def gen_engine(
    db_username: typing.Optional[str] = None,
    db_password: typing.Optional[str] = None,
    db_host: typing.Optional[str] = None,
    db_port: typing.Optional[str] = None,
    db_name: typing.Optional[str] = None,
    database_url: typing.Optional[str] = None,
    **engine_kwargs
) -> Engine:
    """ Generate an SQLAlchemy database engine object to connect to the local
    soongo database.

    :returns: SQLAlchemy engine connected to the SoonGo local db
    """
    if database_url:
        return create_engine(database_url, **engine_kwargs)

    db_config = {
        'db_username': db_username,
        'db_password': db_password,
        'db_host': db_host,
        'db_port': db_port,
        'db_name': db_name,
    }
    filtered_arg_lst = [
        arg for arg in db_config.values() if arg
    ]
    if (
        any(filtered_arg_lst) and
        len(filtered_arg_lst) != len(db_config.values())
    ):
        raise ValueError(
            'May either connect through a database_url or by providing all'
            'other arguments.'
        )

    # Create a connection string
    if filtered_arg_lst:
        connection_string = (
            'postgresql://{db_username}:{db_password}@{db_host}:{db_port}/'
            '{db_name}'.format(**db_config)
        )

    else:
        logger = gen_logger(__name__)
        logger.info(
            'No database connection arguments were provided, using local secrets'
        )
        connection_string = get_local_secret(
            logger=logger,
        )['DATABASE_URL']

    # Create an engine object
    return create_engine(connection_string, **engine_kwargs)


def gen_session(
    db_username: typing.Optional[str] = None,
    db_password: typing.Optional[str] = None,
    db_host: typing.Optional[str] = None,
    db_port: typing.Optional[str] = None,
    db_name: typing.Optional[str] = None,
    database_url: typing.Optional[str] = None,
) -> Session:
    """ Generate an SQLAlchemy session object to connect to the local
    soongo database.

    :returns: SQLAlchemy session connected to the SoonGo local db
    """

    return sessionmaker(
        bind=gen_engine(
            db_username=db_username,
            db_password=db_password,
            db_host=db_host,
            db_port=db_port,
            db_name=db_name,
            database_url=database_url,
        )
    )()


@contextmanager
def session_scope(
    db_username: typing.Optional[str] = None,
    db_password: typing.Optional[str] = None,
    db_host: typing.Optional[str] = None,
    db_port: typing.Optional[str] = None,
    db_name: typing.Optional[str] = None,
    database_url: typing.Optional[str] = None,
):
    """Provide a transactional scope around a series of operations."""
    session = gen_session(
        db_username=db_username,
        db_password=db_password,
        db_host=db_host,
        db_port=db_port,
        db_name=db_name,
        database_url=database_url,
    )
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@lru_cache
def get_organization_id(
    organization_name: str,
    db_username: typing.Optional[str] = None,
    db_password: typing.Optional[str] = None,
    db_host: typing.Optional[str] = None,
    db_port: typing.Optional[str] = None,
    db_name: typing.Optional[str] = None,
    database_url: typing.Optional[str] = None,
) -> str:
    """ Get organization uuid id from db

    :param organization_name: str name of the organization whose id should be
        returned
    """
    with gen_session(
        db_username=db_username,
        db_password=db_password,
        db_host=db_host,
        db_port=db_port,
        db_name=db_name,
        database_url=database_url,
    ) as session:
        organization_id = session.query(OrganizationsTable.id).filter(
            OrganizationsTable.slug == organization_name
        ).scalar()
        if organization_id is None:
            raise ValueError(
                f'There are no organization named {organization_name} in '
                'database'
            )
        return organization_id


@lru_cache
def get_kpi_id(
    kpi_name: str,
    db_username: typing.Optional[str] = None,
    db_password: typing.Optional[str] = None,
    db_host: typing.Optional[str] = None,
    db_port: typing.Optional[str] = None,
    db_name: typing.Optional[str] = None,
) -> str:
    """ Get kpi uuid id

    :param kpi_name: str display name of the kpi
    """
    with session_scope(
        db_username=db_username,
        db_password=db_password,
        db_host=db_host,
        db_port=db_port,
        db_name=db_name,
    ) as session:
        kpi_id = session.query(KpisTable.id).filter(
            KpisTable.display_name == kpi_name
        ).one_or_none()
        if kpi_id is None:
            raise ValueError(
                f'There are no kpi named {kpi_name} in database'
            )
        return kpi_id


class Perimeter:

    def __init__(
        self,
        filter_values: typing.Optional[typing.Dict[str, typing.List]] = None,
        extra_args: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ):
        self.filter_values = filter_values if filter_values else {}
        self.extra_args = extra_args if extra_args else {}

    @cached_property
    def json(self) -> typing.Dict:
        return_dict = {'extra': self.extra_args}
        return_dict.update(self.filter_values)
        return json.dumps(return_dict)


def compute_kpi_value(
    kpi_name: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    organization_name: str,
    perimeter: Perimeter,
    db_username: typing.Optional[str] = None,
    db_password: typing.Optional[str] = None,
    db_host: typing.Optional[str] = None,
    db_port: typing.Optional[str] = None,
    db_name: typing.Optional[str] = None,
):
    """ Compute kpi value on a start and end date, an organization_name and
        perimeter value.

        :param kpi_name: string name of the kpi to compute
        :param start_date: date to start computing it from
        :param end_date: date to compute it until
        :param organization_name: organization to compute it for
        :param perimeter: perimeter to subset it to.
    """
    # TODO: Convert to SQLAlchemy
    # Define the subquery to select the specific row
    from sqlalchemy import text
    organization_id = get_organization_id(
        organization_name=organization_name,
        db_username=db_username,
        db_password=db_password,
        db_host=db_host,
        db_port=db_port,
        db_name=db_name,
    )
    with session_scope(
        db_username=db_username,
        db_password=db_password,
        db_host=db_host,
        db_port=db_port,
        db_name=db_name,
    ) as session:
        return session.execute(
            text(
                f"""
                SELECT value from publ.kpis_value(
                        (
                            SELECT k FROM publ.kpis k
                            WHERE k.display_name = '{kpi_name}'
                        ),
                        '{start_date}'::date,
                        '{end_date}'::date,
                        '{organization_id}'::uuid,
                        '{perimeter.json}'::json,
                        NULL::uuid
                );
                """
            )
        ).scalar()


if __name__ == '__main__':
    session = gen_session()

    # Execute the query using the session
    print(
        compute_kpi_value(
            kpi_name='TCO (new)',
            start_date='2023-01-01',
            end_date='2023-12-31',
            organization_name='Quartus',
            perimeter=Perimeter(),
        )
    )


def get_vehicle_id(organization_id: str, plate_number: str) -> str:
    """Get the vehicle ID from the database based on the plate number."""
    with Session(gen_engine(database_url=os.environ['DATABASE_URL'])) as session:
        vehicle_id = session.query(VehiclesTable.id).filter(
            VehiclesTable.plate_number == plate_number,
            VehiclesTable.organization_id == organization_id
        ).scalar()
        if not vehicle_id:
            raise ValueError(f"Vehicle with plate number {plate_number} not found.")
        return vehicle_id


def list_timestamptz_columns(sqlalchemy_model):
    """
    List all timestamptz columns from an SQLAlchemy model.

    :param sqlalchemy_model: The SQLAlchemy model to inspect.
    :return: A list of column names that are timestamptz.
    """
    # Get all columns from the model
    columns = class_mapper(sqlalchemy_model).columns

    # Filter columns that are DateTime with timezone=True
    timestamptz_columns = [
        column.name
        for column in columns
        if isinstance(column.type, DateTime) and getattr(column.type, 'timezone', False)
    ]

    return timestamptz_columns
