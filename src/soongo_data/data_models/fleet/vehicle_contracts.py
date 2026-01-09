""" Gac Column

Defines columns used across all Gac datasets
"""
from __future__ import annotations

import typing

import numpy as np

from soongo_data.data_models.base import BaseModel, DataColumn
from soongo_data.utils.enums import ContractType, mapper_factory
from soongo_data.utils.type import (convert_date, convert_numeric,
                                    convert_string)

if typing.TYPE_CHECKING:
    import pandas as pd


def convert_numeric_0_nan(series: pd.Series):
    return convert_numeric(series.replace(0, np.nan))


def convert_day_first_date(series: pd.Series):
    return convert_date(series, date_format=r'%d/%m/%Y')


class VehicleContractsModel(BaseModel):
    contract_reference: DataColumn = DataColumn(
        raw_name="Contrat",
        dtype='string',
        post_processing=convert_string,
        name='contract_reference'
    )
    has_fluidity_matrix: DataColumn = DataColumn(
        raw_name="Matrice de fluidité",
        dtype='string',
        post_processing=convert_string,
        name='has_fluidity_matrix',
    )
    update_date: DataColumn = DataColumn(
        raw_name='Date de màj',
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='update_date',
    )
    purchase_date: DataColumn = DataColumn(
        raw_name="Date d'achat",
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='purchase_date',
    )
    contract_type: DataColumn = DataColumn(
        raw_name="Type de contrat",
        dtype='string',
        post_processing=mapper_factory(ContractType),
        name='contract_type',
    )
    contract_status: DataColumn = DataColumn(
        raw_name="Contrat - Statut actuel",
        dtype='string',
        post_processing=convert_string,
        name='contract_status',
    )
    lease_start_date: DataColumn = DataColumn(
        raw_name="Date de début",
        dtype='datetime64[ns]',
        name='lease_start_date',
        post_processing=convert_date,
    )
    contract_start_date: DataColumn = DataColumn(
        raw_name="Début du contrat",
        dtype='datetime64[ns]',
        name='contract_start_date',
    )
    contract_end_date: DataColumn = DataColumn(
        raw_name="Contrat - Date de clôture",
        dtype='datetime64[ns]',
        name='contract_end_date',
    )
    contract_creation_date: DataColumn = DataColumn(
        raw_name="Date de création",
        dtype='datetime64[ns]',
        name='contract_creation_date',
    )
    lease_end_date: DataColumn = DataColumn(
        raw_name="Date de fin",
        dtype='datetime64[ns]',
        name='lease_end_date',
        post_processing=convert_date,
    )
    lease_months: DataColumn = DataColumn(
        raw_name="Durée souscrite",
        dtype='Int64',
        post_processing=convert_numeric_0_nan,
        name='lease_months',
    )
    lease_mileage: DataColumn = DataColumn(
        raw_name="Distance souscrite",
        dtype='Int64',
        post_processing=convert_numeric_0_nan,
        name='lease_mileage',
    )
    lease_month_and_mileage: DataColumn = DataColumn(
        raw_name="lease_month_and_mileage",
        dtype='str',
        post_processing=convert_string,
        name='lease_month_and_mileage',
    )
    lease_mileage_update: DataColumn = DataColumn(
        raw_name="Nvx kilométrages",
        dtype='Int64',
        post_processing=convert_numeric_0_nan,
        name='lease_mileage_update',
    )
    financial_rent_ttc: DataColumn = DataColumn(
        raw_name="Loyer financier théorique (mensuel)",
        dtype='float64',
        name='financial_rent_ttc',
        post_processing=convert_numeric,
    )
    insurance_rent_ttc: DataColumn = DataColumn(
        raw_name="Loyer assurance théorique (mensuel)",
        dtype='float64',
        name='insurance_rent_ttc',
        post_processing=convert_numeric,
    )
    civil_liability_rent_ttc: DataColumn = DataColumn(
        raw_name="Loyer assurance RC",
        dtype='float64',
        name='civil_liability_rent_ttc',
        post_processing=convert_numeric,
    )
    damage_insurance_rent_ttc: DataColumn = DataColumn(
        raw_name="Loyer assurance dommages (Topaze)",
        dtype='float64',
        name='damage_insurance_rent_ttc',
    )
    management_fee_rent_ttc: DataColumn = DataColumn(
        raw_name="Loyer Gestion",
        dtype='float64',
        name='management_fee_rent_ttc',
        post_processing=convert_numeric,
    )
    accident_management_rent_ttc: DataColumn = DataColumn(
        raw_name="Loyer Gest. Sinistre",
        dtype='float64',
        name='accident_management_fee_rent_ttc',
        post_processing=convert_numeric,
    )
    replacement_vehicle_rent_ttc: DataColumn = DataColumn(
        raw_name="Loyer Vehicule Relais",
        dtype='float64',
        name='replacement_vehicle_rent_ttc',
        post_processing=convert_numeric,
    )
    relay_vehicle_rent_ttc: DataColumn = DataColumn(
        raw_name="Loyer Vehicule Relais",
        dtype='float64',
        name='relay_vehicle_rent_ttc',
        post_processing=convert_numeric,
    )
    fuel_card_management_rent_ttc: DataColumn = DataColumn(
        raw_name="Loyer Gestion carte carbu.",
        dtype='float64',
        name='fuel_card_management_rent_ttc',
        post_processing=convert_numeric,
    )
    toll_card_management_rent_ttc: DataColumn = DataColumn(
        raw_name="Loyer gestion carte péage théorique (mensuel) HT",
        dtype='float64',
        name='toll_card_management_rent_ttc',
        post_processing=convert_numeric,
    )
    tires_rent_ttc: DataColumn = DataColumn(
        raw_name="Loyer Pneumatiques",
        dtype='float64',
        name='tires_rent_ttc',
        post_processing=convert_numeric,
    )
    tires_contract_nb: DataColumn = DataColumn(
        raw_name="Nb Pneus ete",
        dtype='Int64',
        name='tires_contract_nb',
        post_processing=convert_numeric,
    )
    tires_used_nb: DataColumn = DataColumn(
        raw_name="Nb Pneus ete",
        dtype='Int64',
        name='tires_used_nb',
        post_processing=convert_numeric,
    )
    tires_remaining_nb: DataColumn = DataColumn(
        raw_name="Nb Pneus ete",
        dtype='Int64',
        name='tires_remaining_nb',
        post_processing=convert_numeric,
    )
    summer_tires_contract_nb: DataColumn = DataColumn(
        raw_name="Nb Pneus ete",
        dtype='Int64',
        name='summer_tires_contract_nb',
        post_processing=convert_numeric,
    )
    summer_tires_used_nb: DataColumn = DataColumn(
        raw_name="Nb Pneus ete",
        dtype='Int64',
        name='summer_tires_used_nb',
        post_processing=convert_numeric,
    )
    summer_tires_rent_ttc: DataColumn = DataColumn(
        raw_name="Loyer Pneumatiques",
        dtype='float64',
        name='summer_tires_rent_ttc',
        post_processing=convert_numeric,
    )
    all_weather_tires_rent_ttc: DataColumn = DataColumn(
        raw_name="Loyer pneus mixtes",
        dtype='float64',
        name='all_weather_tires_rent_ttc',
        post_processing=convert_numeric,
    )
    winter_tires_contract_nb: DataColumn = DataColumn(
        raw_name="Nb Pneus hiver",
        dtype='Int64',
        name='winter_tires_contract_nb',
        post_processing=convert_numeric,
    )
    winter_tires_rent_ttc: DataColumn = DataColumn(
        raw_name="Loyer pneus hiver",
        dtype='float64',
        name='winter_tires_rent_ttc',
        post_processing=convert_numeric,
    )
    maintenance_rent_ttc: DataColumn = DataColumn(
        raw_name="Loyer Maint. / Entretien",
        dtype='float64',
        name='maintenance_rent_ttc',
        post_processing=convert_numeric,
    )
    fuel_card_management_fee_rent_ttc: DataColumn = DataColumn(
        raw_name="Loyer Gestion carte carbu.",
        dtype='float64',
        name='fuel_card_management_fee_rent_ttc',
        post_processing=convert_numeric,
    )
    assistance_rent_ttc: DataColumn = DataColumn(
        raw_name="Loyer Assistance",
        dtype='float64',
        name='roadside_assistance_rent_ttc',
        post_processing=convert_numeric,
    )
    financial_loss_rent_ttc: DataColumn = DataColumn(
        raw_name="Perte financière",
        dtype='float64',
        name='financial_loss_rent_ttc',
        post_processing=convert_numeric,
    )
    electricity_rent_ttc: DataColumn = DataColumn(
        raw_name="Loyer Electrique",
        dtype='float64',
        name='electricity_rent_ttc',
        post_processing=convert_numeric,
    )
    telematics_rent_ttc: DataColumn = DataColumn(
        raw_name="Loyer Boitier Télématique",
        dtype='float64',
        name='telematics_rent_ttc',
        post_processing=convert_numeric,
    )
    vignette_rent_ttc: DataColumn = DataColumn(
        raw_name="Vignettes",
        dtype='float64',
        name='vignette_rent_ttc',
        post_processing=convert_numeric,
    )
    service_fees_rent_ttc: DataColumn = DataColumn(
        raw_name="Frais de Service",
        dtype='float64',
        name='service_fees_rent_ttc',
        post_processing=convert_numeric,
    )
    other_rent_ttc: DataColumn = DataColumn(
        raw_name="Autres loyers théoriques (mensuel)",
        dtype='float64',
        name='other_rent_ttc',
        post_processing=convert_numeric,
    )
    fine_rent_ttc: DataColumn = DataColumn(
        raw_name="Loyer Fine HT",
        dtype='float64',
        name='fine_rent_ttc',
        post_processing=convert_numeric,
    )
    total_rent_ttc: DataColumn = DataColumn(
        raw_name="Total des loyers théoriques (mensuel)",
        dtype='float64',
        name='total_rent_ttc',
        post_processing=convert_numeric,
    )
    total_rent_vat: DataColumn = DataColumn(
        raw_name="Total des loyers théoriques (mensuel)",
        dtype='float64',
        name='total_rent_vat',
        post_processing=convert_numeric,
    )
    financial_rent_tax_exc: DataColumn = DataColumn(
        raw_name="Loyer financier théorique (mensuel) HT",
        dtype='float64',
        name='financial_rent_tax_exc',
        post_processing=convert_numeric,
    )
    insurance_rent_tax_exc: DataColumn = DataColumn(
        raw_name="Loyer assurance théorique (mensuel) HT",
        dtype='float64',
        name='insurance_rent_tax_exc',
        post_processing=convert_numeric,
    )
    civil_liability_rent_tax_exc: DataColumn = DataColumn(
        raw_name="Loyer assurance RC",
        dtype='float64',
        name='civil_liability_rent_tax_exc',
        post_processing=convert_numeric,
    )
    damage_insurance_rent_tax_exc: DataColumn = DataColumn(
        raw_name="Loyer assurance dommages (Topaze)",
        dtype='float64',
        name='damage_insurance_rent_tax_exc',
        post_processing=convert_numeric,
    )
    management_fee_rent_tax_exc: DataColumn = DataColumn(
        raw_name="Loyer gestion théorique (mensuel) HT",
        dtype='float64',
        name='management_fee_rent_tax_exc',
        post_processing=convert_numeric,
    )
    accident_management_fee_rent_tax_exc: DataColumn = DataColumn(
        raw_name="Loyer gest. sinistre théorique (mensuel) HT",
        dtype='float64',
        name='accident_management_fee_rent_tax_exc',
        post_processing=convert_numeric,
    )
    tires_rent_tax_exc: DataColumn = DataColumn(
        raw_name="Loyer pneumatiques théorique (mensuel) HT",
        dtype='float64',
        name='tires_rent_tax_exc',
        post_processing=convert_numeric,
    )
    summer_tires_rent_tax_exc: DataColumn = DataColumn(
        raw_name="Loyer pneumatiques théorique (mensuel) HT",
        dtype='float64',
        name='summer_tires_rent_tax_exc',
        post_processing=convert_numeric,
    )
    all_weather_tires_rent_tax_exc: DataColumn = DataColumn(
        raw_name="Loyer pneus mixtes",
        dtype='float64',
        name='all_weather_tires_rent_tax_exc',
        post_processing=convert_numeric,
    )
    winter_tires_rent_tax_exc: DataColumn = DataColumn(
        raw_name="Loyer pneus hiver",
        dtype='float64',
        name='winter_tires_rent_tax_exc',
        post_processing=convert_numeric,
    )
    maintenance_rent_tax_exc: DataColumn = DataColumn(
        raw_name="Loyer maint. / entretien théorique (mensuel) HT",
        dtype='float64',
        name='maintenance_rent_tax_exc',
        post_processing=convert_numeric,
    )
    fuel_card_management_fee_rent_tax_exc: DataColumn = DataColumn(
        raw_name="Loyer gestion carte carbu. théorique (mensuel) HT",
        dtype='float64',
        name='fuel_card_management_fee_rent_tax_exc',
        post_processing=convert_numeric,
    )
    assistance_rent_tax_exc: DataColumn = DataColumn(
        raw_name="Loyer assistance (mensuel) HT",
        dtype='float64',
        name='assistance_rent_tax_exc',
        post_processing=convert_numeric,
    )
    financial_loss_rent_tax_exc: DataColumn = DataColumn(
        raw_name="Loyer perte financière théorique (mensuel) HT",
        dtype='float64',
        name='financial_loss_rent_tax_exc',
        post_processing=convert_numeric,
    )
    electricity_rent_tax_exc: DataColumn = DataColumn(
        raw_name="Loyer électrique théorique (mensuel) HT",
        dtype='float64',
        name='electricity_rent_tax_exc',
        post_processing=convert_numeric,
    )
    telematics_rent_tax_exc: DataColumn = DataColumn(
        raw_name="Loyer boitier Télématique théorique (mensuel) HT",
        dtype='float64',
        name='telematics_rent_tax_exc',
        post_processing=convert_numeric,
    )
    vignette_rent_tax_exc: DataColumn = DataColumn(
        raw_name="Vignettes",
        dtype='float64',
        name='vignette_rent_tax_exc',
        post_processing=convert_numeric,
    )
    service_fees_rent_tax_exc: DataColumn = DataColumn(
        raw_name="Frais de Service",
        dtype='float64',
        name='service_fees_rent_tax_exc',
        post_processing=convert_numeric,
    )
    accident_management_rent_tax_exc: DataColumn = DataColumn(
        raw_name="Loyer gest. sinistre théorique (mensuel) HT",
        dtype='float64',
        name='accident_management_rent_tax_exc',
        post_processing=convert_numeric,
    )
    other_rent_tax_exc: DataColumn = DataColumn(
        raw_name="Autres loyers théoriques (mensuel) HT",
        dtype='float64',
        name='other_rent_tax_exc',
        post_processing=convert_numeric,
    )
    fine_rent_tax_exc: DataColumn = DataColumn(
        raw_name="Loyer Fine HT",
        dtype='float64',
        name='fine_rent_tax_exc',
        post_processing=convert_numeric,
    )
    replacement_vehicle_rent_tax_exc: DataColumn = DataColumn(
        raw_name="Loyer vehicule relais théorique (mensuel) HT",
        dtype='float64',
        name='replacement_vehicle_rent_tax_exc',
        post_processing=convert_numeric,
    )
    relay_vehicle_rent_tax_exc: DataColumn = DataColumn(
        raw_name="Loyer vehicule relais théorique (mensuel) HT",
        dtype='float64',
        name='relay_vehicle_rent_tax_exc',
        post_processing=convert_numeric,
    )
    fuel_card_management_rent_tax_exc: DataColumn = DataColumn(
        raw_name="Loyer gestion carte carbu. théorique (mensuel) HT",
        dtype='float64',
        name='fuel_card_management_rent_tax_exc',
        post_processing=convert_numeric,
    )
    toll_card_management_rent_tax_exc: DataColumn = DataColumn(
        raw_name="Loyer gestion carte péage théorique (mensuel) HT",
        dtype='float64',
        name='toll_card_management_rent_tax_exc',
        post_processing=convert_numeric,
    )
    total_rent_tax_exc: DataColumn = DataColumn(
        raw_name="Total des loyers théoriques (mensuel) HT",
        dtype='float64',
        name='total_rent_tax_exc',
        post_processing=convert_numeric,
    )
    financial_rent_net: DataColumn = DataColumn(
        raw_name="Loyer financier théorique (mensuel) HT",
        dtype='float64',
        name='financial_rent_net',
        post_processing=convert_numeric,
    )
    maintenance_rent_net: DataColumn = DataColumn(
        raw_name="Loyer maint. / entretien théorique (mensuel) HT",
        dtype='float64',
        name='maintenance_rent_net',
        post_processing=convert_numeric,
    )
    summer_tires_rent_net: DataColumn = DataColumn(
        raw_name="Loyer pneumatiques théorique (mensuel) HT",
        dtype='float64',
        name='summer_tires_rent_net',
        post_processing=convert_numeric,
    )
    winter_tires_rent_net: DataColumn = DataColumn(
        raw_name="Loyer pneus hiver",
        dtype='float64',
        name='winter_tires_rent_net',
        post_processing=convert_numeric,
    )
    tires_rent_net: DataColumn = DataColumn(
        raw_name="Loyer pneumatiques théorique (mensuel) HT",
        dtype='float64',
        name='tires_rent_net',
        post_processing=convert_numeric,
    )
    financial_loss_rent_net: DataColumn = DataColumn(
        raw_name="Loyer perte financière théorique (mensuel) HT",
        dtype='float64',
        name='financial_loss_rent_net',
        post_processing=convert_numeric,
    )
    replacement_vehicle_rent_net: DataColumn = DataColumn(
        raw_name="Loyer vehicule relais théorique (mensuel) HT",
        dtype='float64',
        name='replacement_vehicle_rent_net',
        post_processing=convert_numeric,
    )
    relay_vehicle_rent_net: DataColumn = DataColumn(
        raw_name="Loyer vehicule relais théorique (mensuel) HT",
        dtype='float64',
        name='relay_vehicle_rent_net',
        post_processing=convert_numeric,
    )
    insurance_rent_net: DataColumn = DataColumn(
        raw_name="Loyer assurance théorique (mensuel) HT",
        dtype='float64',
        name='insurance_rent_net',
        post_processing=convert_numeric,
    )
    fuel_card_management_rent_net: DataColumn = DataColumn(
        raw_name="Loyer gestion carte carbu. théorique (mensuel) HT",
        dtype='float64',
        name='fuel_card_management_rent_net',
        post_processing=convert_numeric,
    )
    management_fee_rent_net: DataColumn = DataColumn(
        raw_name="Loyer gestion théorique (mensuel) HT",
        dtype='float64',
        name='management_fee_rent_net',
        post_processing=convert_numeric,
    )
    assistance_rent_net: DataColumn = DataColumn(
        raw_name="Loyer assistance (mensuel) HT",
        dtype='float64',
        name='assistance_rent_net',
        post_processing=convert_numeric,
    )
    telematics_rent_net: DataColumn = DataColumn(
        raw_name="Loyer boitier Télématique théorique (mensuel) HT",
        dtype='float64',
        name='telematics_rent_net',
        post_processing=convert_numeric,
    )
    accident_management_rent_net: DataColumn = DataColumn(
        raw_name="Loyer gest. sinistre théorique (mensuel) HT",
        dtype='float64',
        name='accident_management_rent_net',
        post_processing=convert_numeric,
    )
    vignette_rent_net: DataColumn = DataColumn(
        raw_name="Vignettes",
        dtype='float64',
        name='vignette_rent_net',
        post_processing=convert_numeric,
    )
    service_fees_rent_net: DataColumn = DataColumn(
        raw_name="Frais de Service",
        dtype='float64',
        name='service_fees_rent_net',
        post_processing=convert_numeric,
    )
    other_rent_net: DataColumn = DataColumn(
        raw_name="Autres loyers théoriques (mensuel) HT",
        dtype='float64',
        name='other_rent_net',
        post_processing=convert_numeric,
    )
    total_rent_net: DataColumn = DataColumn(
        raw_name="Total des loyers théoriques (mensuel) HT",
        dtype='float64',
        name='total_rent_net',
        post_processing=convert_numeric,
    )
    add_km_unit_price: DataColumn = DataColumn(
        raw_name="Prix Km.supp.",
        dtype='float64',
        name='add_km_unit_price',
    )
    add_km_cost: DataColumn = DataColumn(
        raw_name="Prix Km.supp.",
        dtype='float64',
        name='add_km_cost',
    )
    lease_comment: DataColumn = DataColumn(
        raw_name="Commentaire du contrat",
        dtype='string',
        post_processing=convert_string,
        name='lease_comment',
    )
    residual_value: DataColumn = DataColumn(
        raw_name="Contrat - Valeur résiduelle",
        dtype='float64',
        name='residual_value',
    )
    contract_record_date: DataColumn = DataColumn(
        raw_name='Contrat - Date de saisie',
        dtype='datetime64[ns]',
        name='contract_record_date',
        post_processing=convert_day_first_date,
    )
    contract_final_mileage: DataColumn = DataColumn(
        raw_name='Contrat - Kilométrage de clôture',
        dtype='float64',
        name='contract_final_mileage',
    )
    contract_file_count: DataColumn = DataColumn(
        raw_name='Nombre de fichiers du contrat',
        dtype='Int64',
        name='contract_file_count',
    )
    lease_mileage_at_constant_months: DataColumn = DataColumn(
        raw_name="LDR en conservant la durée actuelle (Km)",
        dtype='Int64',
        name="lease_mileage_at_constant_months",
    )
    contract_comment = DataColumn(
        raw_name='Contrat - Commentaire du contrat',
        dtype='string',
        name='contract_comment',
    )
    sales_date = DataColumn(
        raw_name="Date de la vente",
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='sales_date',
    )
    restitution_date = DataColumn(
        raw_name="Date de restitution",
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='restitution_date',
    )
    restitution_km = DataColumn(
        raw_name="Km lors de la restitution",
        dtype='float64',
        name='restitution_km',
    )
    start_km = DataColumn(
        raw_name="Km début contrat",
        dtype='float64',
        name='start_km',
    )
    close_date = DataColumn(
        raw_name="Date de clôture",
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='close_date',
    )
    lease_closure_ground = DataColumn(
        raw_name='Motif de clôture',
        dtype='string',
        post_processing=convert_string,
        name='lease_closure_ground',
    )
    interest_rate = DataColumn(
        raw_name="Taux d'intérêt",
        dtype='float64',
        name='interest_rate',
    )
    lease_month_at_constant_km = DataColumn(
        raw_name='LDR en conservant le km (Durée en mois)',
        dtype='Int64',
        name='lease_month_at_constant_km',
    )
    is_tax_included: DataColumn = DataColumn(
        raw_name='Loyers HT/TTC',
        dtype='string',
        post_processing=convert_string,
        name='is_tax_included',
    )
    resale_price = DataColumn(
        raw_name='Contrat - Prix de vente',
        dtype='float64',
        name='resale_price',
    )
    resale_date = DataColumn(
        raw_name='Date de la vente',
        dtype='datetime64[ns]',
        name='resale_date',
    )
    sync_key: DataColumn = DataColumn(
        raw_name='sync_key',
        dtype='string',
        name='sync_key',
    )
    # temporary column with both lease month and lease mileage (ex: 16M/50000KM)
    lease_month_mileage: DataColumn = DataColumn(
        raw_name="lease_month_mileage",
        dtype="string",
        name="lease_month_mileage",
    )