""" Fines Column

Defines columns used across all Gac datasets
"""
import dateparser

from soongo_data.data_models.base import BaseModel, DataColumn
from soongo_data.utils.type import (convert_date, convert_numeric,
                                    convert_string)


class FinesModel(BaseModel):
    antai_status: DataColumn = DataColumn(
        raw_name="Statut ANTAI",
        dtype='string',
        post_processing=convert_string,
        name='antai_status',
    )
    antai_submission_date: DataColumn = DataColumn(
        raw_name="Date de soumission ANTAI",
        dtype='string',
        post_processing=convert_string,
        name='antai_submission_date',
    )
    offense_date: DataColumn = DataColumn(
        raw_name="Date d'infraction",
        dtype='datetime64[ns]',
        post_processing=lambda x: x.apply(dateparser.parse),
        name='offense_date',
    )
    offense_type: DataColumn = DataColumn(
        raw_name="Nature",
        dtype='string',
        post_processing=convert_string,
        name='offense_type',
    )
    antai_number: DataColumn = DataColumn(
        raw_name="N° ANTAI",
        dtype='Int64',
        name='antai_number',
    )
    first_request_date: DataColumn = DataColumn(
        raw_name="Date 1ere demande",
        dtype='string',
        post_processing=convert_string,
        name='first_request_date',
    )
    reminder_count: DataColumn = DataColumn(
        raw_name="Nombre de relances",
        dtype='string',
        post_processing=convert_string,
        name='reminder_count',
    )
    response_datetime: DataColumn = DataColumn(
        raw_name="Date de réponse",
        dtype='datetime64[ns]',
        post_processing=lambda x: x.fillna('').apply(dateparser.parse),
        name='response_datetime',
    )
    employee_notification_date: DataColumn = DataColumn(
        raw_name="Date de notification au collborateur",
        dtype='datetime64[ns]',
        post_processing=lambda x: x.fillna('').apply(dateparser.parse),
        name='employee_notification_date',
    )
    aknowledgement_date: DataColumn = DataColumn(
        raw_name="Accusé de réception le",
        dtype='datetime64[ns]',
        post_processing=lambda x: x.fillna('').apply(dateparser.parse),
        name='aknowledgement_date',
    )
    fine_ref: DataColumn = DataColumn(
        raw_name="N° de référence",
        dtype='string',
        post_processing=convert_string,
        name='fine_ref',
    )
    surcharge_date: DataColumn = DataColumn(
        raw_name="Date limite de paiement avant majoration",
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='surcharge_date',
    )
    fine_status: DataColumn = DataColumn(
        raw_name='Statut',
        dtype='string',
        post_processing=convert_string,
        # TODO: Add a Enum and mapping
        name='fine_status',
    )
    ticket_last_send: DataColumn = DataColumn(
        raw_name='Dernier envoi',
        dtype='datetime64[ns]',
        post_processing=lambda x: x.fillna('').apply(dateparser.parse),
        name='ticket_last_send',
    )
    ticket_send_n1: DataColumn = DataColumn(
        raw_name='renvoi antérieur -1',
        dtype='datetime64[ns]',
        post_processing=lambda x: x.fillna('').apply(dateparser.parse),
        name='ticket_send_n1',
    )
    ticket_send_n2: DataColumn = DataColumn(
        raw_name='renvoi antérieur -2',
        dtype='datetime64[ns]',
        post_processing=lambda x: x.fillna('').apply(dateparser.parse),
        name='ticket_send_n2',
    )
    surcharge_reference: DataColumn = DataColumn(
        raw_name='N° de référence (Majoration)',
        dtype='string',
        post_processing=convert_string,
        name='surcharge_reference',
    )
    ticket_base_value: DataColumn = DataColumn(
        raw_name='Montant',
        dtype='float64',
        post_processing=convert_numeric,
        name='ticket_base_value',
    )
    surcharge_value: DataColumn = DataColumn(
        raw_name='Majoration',
        dtype='float64',
        post_processing=convert_numeric,
        name='surcharge_value',
    )
    surcharge_ref: DataColumn = DataColumn(
        raw_name='N° de référence (Majoration)',
        dtype='string',
        post_processing=convert_string,
        name='surcharge_ref',
    )
    fine_payer: DataColumn = DataColumn(
        raw_name='Coût à charge (PV/FPS)',
        dtype='string',
        post_processing=convert_string,
        name='fine_payer',
    )
    fine_type: DataColumn = DataColumn(
        raw_name='Type de PV',
        dtype='string',
        post_processing=convert_string,
        # TODO: create a mapping of types
        name='fine_type',
    )
    notice_date: DataColumn = DataColumn(
        raw_name="Date de l'avis",
        dtype='string',
        post_processing=convert_string,
        name='notice_date',
    )
    remote_payment_ref: DataColumn = DataColumn(
        raw_name="N° de télépaiement",
        dtype='Int64',
        name='remote_payment_ref',
    )
    licence_points_lost: DataColumn = DataColumn(
        raw_name="Points retirés",
        dtype='Int64',
        name='licence_points_lost',
    )
    payment_date: DataColumn = DataColumn(
        raw_name="Date règlement",
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='payment_date',
    )
    fine_overdue: DataColumn = DataColumn(
        raw_name="Dépassement",
        dtype='string',
        post_processing=convert_string,
        name='fine_overdue',
    )
    offense_comment = DataColumn(
        raw_name='Description',
        dtype='string',
        post_processing=convert_string,
        name='offense_comment'
    )
    road_type = DataColumn(
        raw_name='Voie',
        dtype='string',
        post_processing=convert_string,
        name='road_type',
    )
    currency: DataColumn = DataColumn(
        raw_name="Devise du reporting",
        dtype='string',
        name='currency'
    )
    total_cost: DataColumn = DataColumn(
        raw_name='Coût total',
        dtype='float64',
        name='total_cost',
        post_processing=convert_numeric,
    )
    creation_date: DataColumn = DataColumn(
        raw_name="Date de création",
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='creation_date',
    )
