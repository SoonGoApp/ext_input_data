""" Vehicle Reports

Defines columns used across all Gac datasets
"""
import dateparser

from soongo_data.data_models.base import BaseModel, DataColumn
from soongo_data.utils.type import (convert_date, convert_numeric,
                                    convert_string)


class VehicleReportsModel(BaseModel):
    avg_daily_expense_tax_exc = DataColumn(
        raw_name='Par jour',
        dtype='float64',
        name='avg_daily_expense_tax_exc'
    )
    avg_monthly_expense_tax_exc = DataColumn(
        raw_name='Par mois',
        dtype='float64',
        name='avg_monthly_expense_tax_exc'
    )
    missing_expenses_tax_exc = DataColumn(
        raw_name='*Dps manquantes',
        dtype='float64',
        name='missing_expenses_tax_exc'
    )
    future_expenses_tax_exc = DataColumn(
        raw_name='*Dps à venir',
        dtype='float64',
        name='future_expenses_tax_exc'
    )
    tco_tax_exc = DataColumn(
        raw_name='TCO',
        dtype='float64',
        name='tco_tax_exc'
    )
    avg_daily_expense_tax_inc = DataColumn(
        raw_name='Par jour',
        dtype='float64',
        name='avg_daily_expense_tax_inc'
    )
    avg_monthly_expense_tax_inc = DataColumn(
        raw_name='Par mois',
        dtype='float64',
        name='avg_monthly_expense_tax_inc'
    )
    missing_expenses_tax_inc = DataColumn(
        raw_name='*Dps manquantes',
        dtype='float64',
        name='missing_expenses_tax_inc'
    )
    future_expenses_tax_inc = DataColumn(
        raw_name='*Dps à venir',
        dtype='float64',
        name='future_expenses_tax_inc'
    )
    tco_tax_inc = DataColumn(
        raw_name='TCO',
        dtype='float64',
        name='tco_tax_inc',
        post_processing=convert_numeric,
    )
    export_date = DataColumn(
        raw_name="Date de l'export",
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='export_date'
    )
    export_status = DataColumn(
        raw_name="État de l'export",
        dtype='string',
        post_processing=convert_string,
        name='export_status'
    )
    export_cost_centers = DataColumn(
        raw_name="Centres de Coûts exporté",
        dtype='string',
        post_processing=convert_string,
        name='export_cost_centers'
    )
    validation_date = DataColumn(
        raw_name="Date de validation",
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='validation_date'
    )
    vehicle_avg_monthly_mileage = DataColumn(
        raw_name="Moyenne kilométrique du véhicule (Km (s) par mois)",
        dtype="Int64",
        name='vehicle_avg_monthly_mileage',
    )
    CO2_emissions = DataColumn(
        raw_name='CO2 emis (kg)',
        dtype='Int64',
        name='C02_emissions',
    )
    expected_CO2_emissions = DataColumn(
        raw_name='CO2 prévu (kg)',
        dtype='Int64',
        name='expected_CO2_emissions',
    )
    insurance_ttc = DataColumn(
        raw_name="Assurance",
        dtype='float64',
        name='insurance_ttc',
    )
    insurance_final = DataColumn(
        raw_name="Assurance réelle",
        dtype='float64',
        name='insurance_final',
    )
    fuel_cost = DataColumn(
        raw_name="Dépenses carburant",
        dtype='float64',
        name='fuel_cost',
    )
    fuel_consumption = DataColumn(
        raw_name="Litrage",
        dtype='float64',
        name='fuel_consumption',
        description='Fuel consumption in liters',
    )
    other_cost = DataColumn(
        raw_name="Autres dépenses",
        dtype='float64',
        name='other_cost',
    )
    vehicle_count = DataColumn(
        raw_name='Nb Véh.',
        dtype='float64',
        name='vehicle_count',
    )
    entry_into_circulation_fees_tax_inc = DataColumn(
        raw_name='Frais de mise en circulation',
        dtype='float64',
        name='entry_into_circulation_fees_tax_inc',
    )
    entry_into_circulation_fees_tax_exc = DataColumn(
        raw_name='frais de mise en circulation HT',
        dtype='float64',
        name='entry_into_circulation_fees_tax_exc',
    )
    refurbishment_charges = DataColumn(
        raw_name='Contrat - Frais de remise en état',
        dtype='float64',
        name='refurbishment_charges',
    )
    committed_budget = DataColumn(
        raw_name='Budget engagé',
        dtype='float64',
        name='committed_budget',
    )
    days_hired = DataColumn(
        raw_name='Jours engagés',
        dtype="Int64",
        name='days_hired',
    )
    daily_budget = DataColumn(
        raw_name='Par jour',
        dtype='float64',
        name='daily_budget',
    )
    total_days = DataColumn(
        raw_name='Jours période',
        dtype="Int64",
        name='total_days',
    )
    total_budget = DataColumn(
        raw_name='Budget période',
        dtype='float64',
        name='total_budget',
    )
    cost_per_km = DataColumn(
        raw_name='Coût / Km',
        dtype='float64',
        name='cost_per_km',
    )
    total_rent_per_car = DataColumn(
        raw_name='Loyer Moy.',
        dtype='float64',
        name='total_rent_per_car',
    )
    vehicle_avg_monthly_mileage = DataColumn(
        raw_name='Moyenne kilométrique du véhicule (Km (s) par mois)',
        dtype='Int64',
        name='vehicle_avg_monthly_mileage',
    )
    monthly_spend = DataColumn(
        raw_name='Dépense Mensuelle',
        dtype='string',
        post_processing=convert_string,
        name='monthly_spend'
    )
    monthly_in_kind_benefits = DataColumn(
        raw_name=(
            "Données calculées > Affectation courante > Montant d'avantage en "
            "nature"
        ),
        name="monthly_in_kind_benefits",
        dtype='Int64',
    )
    monthly_participation = DataColumn(
        raw_name=(
            "Données calculées > Affectation courante > Montant de "
            "participation"
        ),
        name="monthly_participation",
        dtype='Int64',
    )
    total_monthly_rent = DataColumn(
        raw_name='Contrat > Dernière loi de roulage > Loyer mensuel',
        name="total_monthly_rent",
        dtype='float64',
    )
    restitution_charges = DataColumn(
        raw_name='Contrat - Frais de restitution',
        dtype='float64',
        name='restitution_charges',
    )
    expense_count = DataColumn(
        raw_name='Nombre de dépenses',
        dtype="Int64",
        name='expense_count'
    )
    year = DataColumn(
        raw_name="year",
        dtype=int,
        name='year',
    )
    month = DataColumn(
        raw_name='Month',
        dtype='datetime64[ns]',
        post_processing=lambda x: x.apply(dateparser.parse),
        name='month'
    )
    consumption_gap: DataColumn = DataColumn(
        raw_name='Ecart',
        dtype='string',
        post_processing=convert_string,
        name='consumption_gap',
    )
