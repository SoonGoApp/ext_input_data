""" TaxesModels

Defines columns used across all fleet connectors datasets
"""
from soongo_data.data_models.base import BaseModel, DataColumn
from soongo_data.utils.type import (convert_date, convert_numeric,
                                    convert_string)
from soongo_data.utils.enums import InKindBenefitType, mapper_factory


class TaxesModel(BaseModel):
    ikb_start_date: DataColumn = DataColumn(
        raw_name='ikb_period_start',
        dtype='datetime64[ns]',
        name='ikb_start_date'
    )
    ikb_end_date: DataColumn = DataColumn(
        raw_name='ikb_period_end',
        dtype='datetime64[ns]',
        name='ikb_end_date'
    )
    ikb_period: DataColumn = DataColumn(
        raw_name='Date de début de l?évènement à date',
        dtype='string',
        post_processing=convert_string,
        name='ikb_period'
    )
    tax_status_start_date: DataColumn = DataColumn(
        raw_name="Date d'effet",
        dtype='datetime64[ns]',
        name='tax_status_start_date',
        post_processing=convert_date,
    )
    tax_status_end_date: DataColumn = DataColumn(
        raw_name="Date de fin",
        dtype='datetime64[ns]',
        name='tax_status_end_date',
        post_processing=convert_date,
    )
    tax_category: DataColumn = DataColumn(
        raw_name="catégorie",
        dtype='string',
        post_processing=convert_string,
        name='tax_category',
    )
    tax_vehicle_age: DataColumn = DataColumn(
        raw_name="Total (en )",
        dtype='float64',
        name='tax_vehicle_age',
    )
    tax_CO2_emission: DataColumn = DataColumn(
        raw_name="Total (en )",
        dtype='float64',
        name='tax_CO2_emission',
        post_processing=convert_numeric,
    )
    tax_pollutant: DataColumn = DataColumn(
        raw_name="Total (en )",
        dtype='float64',
        name='tax_pollutant',
        post_processing=convert_numeric,
    )
    tax_pollutant_base: DataColumn = DataColumn(
        raw_name="Total (en )",
        dtype='float64',
        name='tax_pollutant_base',
        post_processing=convert_numeric,
    )
    tax_corporate_vehicles: DataColumn = DataColumn(
        raw_name="Total (en )",
        dtype='float64',
        name='tax_corporate_vehicles',
    )
    tax_error: DataColumn = DataColumn(
        raw_name="Erreur Taxation",
        dtype='float64',
        name='tax_error',
    )
    tax_credit_description: DataColumn = DataColumn(
        raw_name="Exonération",
        dtype='string',
        post_processing=convert_string,
        name='tax_credit_description',
    )
    tax_CO2_base: DataColumn = DataColumn(
        raw_name="Tarif applicable en fonction des émissions de CO2",
        dtype='float64',
        name='tax_CO2_base',
    )
    nb_days_CO2: DataColumn = DataColumn(
        raw_name="Nombre de jours",
        dtype='float64',
        name='nb_days_CO2',
        description='Nombre de jour utilisation imposable au nom de la taxe CO2'
    )
    nb_days_pollutant: DataColumn = DataColumn(
        raw_name="Nombre de jours",
        dtype='float64',
        name='nb_days_pollutant',
        description='Nombre de jour utilisation imposable au nom de la taxe pollution atmosphérique'
    )
    tax_power_base: DataColumn = DataColumn(
        raw_name="Tarif applicable en fonction de la puissance fiscale",
        dtype='float64',
        name='tax_power_base',
    )
    tax_clean_air: DataColumn = DataColumn(
        raw_name="Tarif Air",
        dtype='float64',
        name='tax_clean_air',
    )
    tax_credit_previous_plate: DataColumn = DataColumn(
        raw_name="Immat. du véhicule précédent si exonération",
        dtype='string',
        post_processing=convert_string,
        name='tax_credit_previous_plate',
    )
    tax_credit_next_plate: DataColumn = DataColumn(
        raw_name="Immat. du véhicule suivant si exonération",
        dtype='string',
        post_processing=convert_string,
        name='tax_credit_next_plate',
    )
    nb_quarters: DataColumn = DataColumn(
        raw_name='Nombre de trimestres retenus',
        dtype=int,
        name='nb_quarters',
    )
    yearly_corporate_car_tax: DataColumn = DataColumn(
        raw_name='TVS',
        name='yearly_corporate_car_tax',
        dtype='float64',
    )
    quarter: DataColumn = DataColumn(
        raw_name='quarter',
        name='quarter',
        dtype='string',
        post_processing=convert_string,
    )
    company_car_tax_method: DataColumn = DataColumn(
        raw_name='Véhicules taxés selon',
        dtype='string',
        post_processing=convert_string,
        name='company_car_tax_method',
    )
    ikb_prorata: DataColumn = DataColumn(
        raw_name='Calcul prorata',
        dtype='float64',
        name='ikb_prorata',
        description='Valeur des ikb au pro rata du temps dans année',
    )
    ikb_value = DataColumn(
        raw_name='Calcul actuel',
        dtype='float64',
        name='ikb_value',
        description='Ikb value as per current calculation method',
        post_processing=convert_numeric,
    )
    ikb_monthly_value = DataColumn(
        raw_name='ikb_monthly_value',
        dtype='float64',
        name='ikb_monthly_value',
        description='Monthly ikb value',
        post_processing=convert_numeric,
    )
    ikb_price_based_nofuel = DataColumn(
        raw_name=(
            "9% ou 6% du prix du d'achat TTC (En propriété et uniquement hors "
            "carburant)"
        ),
        dtype='float64',
        name='ikb_price_based_nofuel',
    )
    ikb_price_based_fuel = DataColumn(
        raw_name=(
            "12% ou 9% du prix du d'achat TTC (En propriété et uniquement si "
            "carburant inclus)"
        ),
        dtype='float64',
        name='ikb_price_based_fuel',
    )
    ikb_net_participation = DataColumn(
        raw_name='Valeur retenue (Actuel - Particip. Récur.)',
        dtype='float64',
        name='ikb_net_participation',
    )
    ikb_type = DataColumn(
        raw_name='type',
        dtype='string',
        post_processing=mapper_factory(InKindBenefitType),
        name='ikb_type',
    )
    adjusted_ikb_net_participation = DataColumn(
        raw_name='Valeur retenue proratisée (Prorata - Particip. réc.)',
        dtype='float64',
        name='adjusted_ikb_net_participation',
    )
    ikb_method = DataColumn(
        raw_name="Méthode de calcul de l'AN",
        dtype='string',
        post_processing=convert_string,
        name='ikb_method',
    )
    ikb_personalized = DataColumn(
        raw_name="Montant AN personnalisé",
        dtype='float64',
        name='ikb_personalized',
    )
    amortization_start_date = DataColumn(
        raw_name="Date de début",
        dtype='datetime64[ns]',
        name='amortization_start_date',
        post_processing=convert_date,
    )
    amortization_end_date = DataColumn(
        raw_name="Date de fin",
        dtype='datetime64[ns]',
        name='amortization_end_date',
        post_processing=convert_date,
    )
    amortization_length = DataColumn(
        raw_name="Durée d'amortissement",
        dtype='float64',
        post_processing=convert_numeric,
        name='amortization_length',
    )
    monthly_non_deductible_amortization = DataColumn(
        raw_name="monthly_non_deductible_amortization",
        dtype='float64',
        post_processing=convert_numeric,
        name='monthly_non_deductible_amortization',
    )
    declared_non_deductible_amortization = DataColumn(
        raw_name="declared_non_deductible_amortization",
        dtype='float64',
        name='declared_non_deductible_amortization',
    )
    amortization_deduction = DataColumn(
        raw_name="amortization_deduction",
        dtype=int,
        name='amortization_deduction',
        post_processing=convert_numeric,
    )
    billing_date: DataColumn = DataColumn(
        raw_name='Facturation',
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='billing_date',
    )
    year = DataColumn(
        raw_name="year",
        dtype=int,
        name='year',
    )
    nb_months = DataColumn(
        raw_name="nb_months",
        dtype=int,
        name='nb_months',
    )
    nb_days = DataColumn(
        raw_name="nb_days",
        dtype=int,
        name='nb_days',
    )
    nb_days_amortization = DataColumn(
        raw_name="nb_days",
        dtype=int,
        name='nb_days_amortization',
    )
