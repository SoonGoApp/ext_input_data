""" TrainPlaneTravelModel

Defines columns used across all fleet connectors datasets
"""
from soongo_data.data_models.base import DataColumn
from soongo_data.data_models.travel.base import TravelBaseModel
from soongo_data.utils.enums import (CabinClassTypes, TicketTypes, TravelTypes,
                                     mapper_factory)
from soongo_data.utils.type import convert_boolean, convert_string


class TrainPlaneTravelModel(TravelBaseModel):

    cabin_class = DataColumn(
        raw_name='Classe cabine',
        dtype='string',
        post_processing=mapper_factory(CabinClassTypes),
        name='cabin_class',
    )
    pnr = DataColumn(
        raw_name='PNR',
        dtype='string',
        post_processing=convert_string,
        name='pnr',
    )
    routing = DataColumn(
        raw_name='Routing',
        dtype='string',
        post_processing=convert_string,
        name='routing',
    )
    travel_type = DataColumn(
        raw_name='Activité',
        dtype='string',
        post_processing=mapper_factory(TravelTypes),
        name='travel_type',
    )
    ticket_type = DataColumn(
        raw_name='Type Trajet Billet',
        dtype='string',
        post_processing=mapper_factory(TicketTypes),
        name='ticket_type',
    )
    leg_id = DataColumn(
        raw_name='ID interne coupon',
        dtype='string',
        name='leg_id',
        post_processing=convert_string,
    )
    is_low_cost = DataColumn(
        raw_name='Low cost',
        dtype='bool',
        name='is_low_cost',
        post_processing=convert_boolean,
    )
    rail_code_type = DataColumn(
        raw_name='Code type billet rail',
        dtype='string',
        post_processing=convert_string,
        name='rail_code_type',
    )
    rail_ticket_type = DataColumn(
        raw_name='Type document Rail',
        dtype='string',
        post_processing=convert_string,
        name='rail_ticket_type',
    )
    used_tickets = DataColumn(
        raw_name='Billets utilisés',
        dtype='Int64',
        name='used_tickets',
    )
    generated_tickets = DataColumn(
        raw_name='Billets émis',
        dtype='Int64',
        name='generated_tickets',
    )
    ticket_ref = DataColumn(
        raw_name='N° Billet',
        dtype='string',
        post_processing=convert_string,
        name='ticket_ref',
    )
    leg_number = DataColumn(
        raw_name='Num coupon',
        dtype='Int64',
        name='leg_number',
    )
    start_location_code = DataColumn(
        raw_name='Code lieu départ',
        dtype='string',
        post_processing=convert_string,
        name='start_location_code',
    )
    start_station_code = DataColumn(
        raw_name='Code gare NLS départ',
        dtype='string',
        post_processing=convert_string,
        name='start_station_code',
    )
    start_country_code = DataColumn(
        raw_name='Code pays départ',
        dtype='string',
        post_processing=convert_string,
        name='start_country_code',
    )
    arrival_location_code = DataColumn(
        raw_name='Code leu arrivée',
        dtype='string',
        post_processing=convert_string,
        name='arrival_location_code',
    )
    arrival_station_code = DataColumn(
        raw_name='Code gare NLS arrivée',
        dtype='string',
        post_processing=convert_string,
        name='arrival_station_code',
    )
    arrival_country_code = DataColumn(
        raw_name='Code pays arrivée',
        dtype='string',
        post_processing=convert_string,
        name='arrival_country_code',
    )
    fare_class = DataColumn(
        raw_name='Classe tarif',
        dtype='string',
        post_processing=convert_string,
        name='fair_class',
    )
    fare_class_rail = DataColumn(
        raw_name='Classe tarif rail',
        dtype='string',
        post_processing=convert_string,
        name='fare_class_rail',
    )
    leg_count = DataColumn(
        raw_name='Nb trajets',
        dtype='Int64',
        name='leg_count',
    )
    airport_tax = DataColumn(
        raw_name='Montant Taxes Billet',
        dtype='float64',
        name='airport_tax',
    )
    routing_countries = DataColumn(
        raw_name='Routing pays',
        dtype='string',
        post_processing=convert_string,
        name='routing_countries',
    )
