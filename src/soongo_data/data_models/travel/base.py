""" TravelBaseModel

Defines columns used across all fleet connectors datasets
"""
from soongo_data.data_models.base import BaseModel, DataColumn
from soongo_data.utils.enums import (TravelServiceTypes, TravelTypes,
                                     mapper_factory)
from soongo_data.utils.type import (convert_boolean, convert_date,
                                    convert_string)


class TravelBaseModel(BaseModel):
    expense_id = DataColumn(
        raw_name='ID Interne ligne',
        dtype='string',
        name='expense_id',
        post_processing=convert_string,
    )
    billing_id = DataColumn(
        raw_name='N° de facture',
        dtype='Int64',
        name='billing_id',
    )
    billing_date = DataColumn(
        raw_name='Date facture',
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='billing_date',
    )
    transaction_type = DataColumn(
        raw_name='Type de transaction',
        dtype='string',
        post_processing=convert_string,
        name='transaction_type',
    )
    booking_date = DataColumn(
        raw_name='Date Commande',
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='booking_date',
    )
    booking_method = DataColumn(
        raw_name='Mode commande',
        dtype='string',
        post_processing=convert_string,
        name='booking_method',
    )
    amount_tax_inc = DataColumn(  # TODO: check whether the amount is HT or TTC
        raw_name='Prix payé Billet',
        dtype='float64',
        name='amount_tax_inc',
    )
    amount_tax_exc = DataColumn(
        raw_name='Montant HT',
        dtype='float64',
        name='amount_tax_exc',
    )
    supplier = DataColumn(
        raw_name='Cie émettrice',
        dtype='string',
        post_processing=convert_string,
        name='supplier',
    )
    start_location_name = DataColumn(
        raw_name='Nom lieu départ',
        dtype='string',
        post_processing=convert_string,
        name='start_location_name',
    )
    start_city = DataColumn(
        raw_name='Ville départ',
        dtype='string',
        post_processing=convert_string,
        name='start_city',
    )
    start_country_name = DataColumn(
        raw_name='Pays départ',
        dtype='string',
        post_processing=convert_string,
        name='start_country_name',
    )
    start_continent_name = DataColumn(
        raw_name='Continent départ',
        dtype='string',
        post_processing=convert_string,
        name='start_continent_name',
    )
    arrival_location_name = DataColumn(
        raw_name='Nom lieu arrivée',
        dtype='string',
        post_processing=convert_string,
        name='arrival_location_name',
    )
    arrival_city = DataColumn(
        raw_name='Ville arrivée',
        dtype='string',
        post_processing=convert_string,
        name='arrival_city',
    )
    arrival_country_name = DataColumn(
        raw_name='Pays arrivée',
        dtype='string',
        post_processing=convert_string,
        name='arrival_country_name',
    )
    arrival_continent_name = DataColumn(
        raw_name='Continent arrivée',
        dtype='string',
        post_processing=convert_string,
        name='arrival_continent_name',
    )
    internal_category_1 = DataColumn(
        raw_name='ref601',
        dtype='string',
        post_processing=convert_string,
        name='internal_category_1'
    )
    internal_category_2 = DataColumn(
        raw_name='ref602',
        dtype='string',
        post_processing=convert_string,
        name='internal_category_2'
    )
    internal_category_3 = DataColumn(
        raw_name='ref603',
        dtype='string',
        post_processing=convert_string,
        name='internal_category_3'
    )
    internal_category_4 = DataColumn(
        raw_name='ref607',
        dtype='string',
        post_processing=convert_string,
        name='internal_category_4'
    )
    internal_category_5 = DataColumn(
        raw_name='ref608',
        dtype='string',
        post_processing=convert_string,
        name='internal_category_5'
    )
    internal_category_6 = DataColumn(
        raw_name='ref609',
        dtype='string',
        post_processing=convert_string,
        name='internal_category_6'
    )
    internal_category_7 = DataColumn(
        raw_name='ref610',
        dtype='string',
        post_processing=convert_string,
        name='internal_category_7'
    )
    internal_category_8 = DataColumn(
        raw_name='ref619',
        dtype='string',
        post_processing=convert_string,
        name='internal_category_8'
    )
    approver = DataColumn(
        raw_name='Valideur',
        dtype='string',
        post_processing=convert_string,
        name='approver',
    )
    demander = DataColumn(
        raw_name='Demandeur',
        dtype='string',
        post_processing=convert_string,
        name='demander',
    )
    start_country_code = DataColumn(
        raw_name='Code pays Hôtel',
        dtype='string',
        post_processing=convert_string,
        name='start_country_code',
    )
    start_datetime = DataColumn(
        raw_name='Date départ',
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='start_datetime',
    )
    end_datetime = DataColumn(
        raw_name='Date Arrivée',
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='end_datetime',
    )
    amount_fees = DataColumn(
        raw_name='Montant Frais induits',
        dtype='string',
        post_processing=convert_string,
        name='amount_fees',
    )
    negotiated_fare_code = DataColumn(
        raw_name='Code tarif négocié',
        dtype='string',
        post_processing=convert_string,
        name='negotiated_fare_code',
    )
    booking_type = DataColumn(
        raw_name='Type de vente',
        dtype='string',
        post_processing=convert_string,
        name='booking_type',
    )
    anticipated_days = DataColumn(
        raw_name='Anticipation jours',
        dtype='Int64',
        name='anticipated_days',
    )
    travel_type = DataColumn(
        raw_name='Activité',
        dtype='string',
        post_processing=mapper_factory(TravelTypes),
        name='travel_type',
    )
    is_aligned_policy = DataColumn(
        raw_name='Respect PV label',
        dtype='boolean',
        post_processing=lambda x: convert_boolean(x.replace('NS', '')),
        name='is_aligned_policy',
    )
    service_type = DataColumn(
        raw_name="Prestation",
        name="service_type",
        dtype='string',
        post_processing=mapper_factory(TravelServiceTypes),
    )
    was_negotiated = DataColumn(
        raw_name='Tarif négocié',
        dtype='boolean',
        post_processing=convert_boolean,
        name='was_negotiated',
    )
    activity_type = DataColumn(
        raw_name='Activité',
        dtype='string',
        post_processing=convert_string,
        name='activity_type',
    )
    travel_cost_type = DataColumn(
        raw_name='Type de frais',
        dtype='string',
        post_processing=convert_string,
        name='travel_cost_type',
    )
    service_ref = DataColumn(
        raw_name='ID Prestation',
        dtype='string',
        post_processing=convert_string,
        name='service_ref',
    )
    base_service = DataColumn(
        raw_name='Activité de base',
        dtype='string',
        post_processing=convert_string,
        name='base_service',
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
    supplier_code = DataColumn(
        raw_name='Code Cie émettrice',
        dtype='string',
        post_processing=convert_string,
        name='supplier_code',
    )
    co2_footprint = DataColumn(
        raw_name='CO2 Cie-',
        dtype='float64',
        name='co2_footprint',
    )
    supplier_alliance = DataColumn(
        raw_name='Alliance',
        dtype='string',
        post_processing=convert_string,
        name='supplier_alliance',
    )
    transporter_code = DataColumn(
        raw_name='Code Cie transport',
        dtype='string',
        post_processing=convert_string,
        name='transporter_code',
    )
    transporter_name = DataColumn(
        raw_name='Cie transport',
        dtype='string',
        post_processing=convert_string,
        name='transporter_name',
    )
    transport_ref = DataColumn(
        raw_name='N° vol/train',
        dtype='string',
        post_processing=convert_string,
        name='transport_ref',
    )
    transport_class = DataColumn(
        raw_name='Classe de service',
        dtype='string',
        post_processing=convert_string,
        name='transport_class',
    )
    travel_time = DataColumn(
        raw_name='Durée trajet',
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='travel_time',
    )
    layover_time = DataColumn(
        raw_name='Durée stop',
        dtype='string',
        post_processing=convert_string,
        name='layover_time',
    )
    distance = DataColumn(
        raw_name='Distance Km',
        dtype='Int64',
        name='distance',
    )
    travel_level = DataColumn(
        raw_name='Axe',
        dtype='string',
        post_processing=convert_string,
        name='travel_level',
    )
    deductible_vat = DataColumn(
        raw_name='deductible_vat',
        dtype='float64',
        name='deductible_vat',
        description='Amount of deductible VAT.'
    )
    net_amount = DataColumn(
        raw_name='net_amount',
        dtype='float64',
        name='net_amount',
        description='Amount, all taxes included, deductible VAT deducted.'
    )
