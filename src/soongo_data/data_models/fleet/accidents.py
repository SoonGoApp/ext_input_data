""" BusinessUnitsModel

Defines columns used across all fleet connectors datasets
"""
from soongo_data.data_models.base import BaseModel, DataColumn
from soongo_data.utils.enums import (AccidentContextTypes,
                                     AccidentGarageStatus,
                                     AccidentInsurerStatus, AccidentStatus,
                                     AccidentTypes, ResponsibilityTypes,
                                     mapper_factory)
from soongo_data.utils.type import (convert_boolean, convert_date,
                                    convert_numeric, convert_string)


class AccidentsModel(BaseModel):

    accident_id: DataColumn = DataColumn(
        raw_name='accident_id',
        dtype='string',
        post_processing=convert_string,
        name='accident_id',
    )
    accident_date: DataColumn = DataColumn(
        raw_name='Date',
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='accident_date',
    )
    accident_time = DataColumn(
        raw_name='HeureSinistre',
        dtype='object',
        name='accident_time',
    )
    accident_ref: DataColumn = DataColumn(
        raw_name='N° de sinistre',
        dtype='string',
        post_processing=convert_string,
        name='accident_ref',
    )
    accident_type: DataColumn = DataColumn(
        raw_name='Type',
        dtype='string',
        post_processing=mapper_factory(AccidentTypes),
        name='accident_type',
    )
    accident_context: DataColumn = DataColumn(
        raw_name='Circonstance',
        dtype='string',
        post_processing=mapper_factory(AccidentContextTypes),
        name='accident_context',
    )
    insurer_context: DataColumn = DataColumn(
        raw_name='CirconstanceAssureur',
        dtype='string',
        post_processing=convert_string,
        name='insurer_context',
    )
    third_party: DataColumn = DataColumn(
        raw_name='Tiers',
        dtype="boolean",
        post_processing=convert_boolean,
        name='third_party',
    )
    third_part_reimbursement: DataColumn = DataColumn(
        raw_name='Remboursement Tiers',
        dtype='float64',
        name='third_part_reimbursement',
        post_processing=convert_numeric,
    )
    responsibility: DataColumn = DataColumn(
        raw_name='Resp.',
        dtype='string',
        post_processing=mapper_factory(ResponsibilityTypes),
        name='responsibility',
    )
    insurer: DataColumn = DataColumn(
        raw_name='Assureur/Courtier',
        dtype='string',
        post_processing=convert_string,
        name='insurer',
    )
    damage_costs = DataColumn(
        raw_name='CoutDommages',
        dtype='float64',
        name='damage_costs',
        post_processing=convert_numeric,
    )
    third_party_cost = DataColumn(
        raw_name='CoutTiers',
        dtype='float64',
        name='third_party_cost',
        post_processing=convert_numeric,
    )
    financial_loss = DataColumn(
        raw_name='CoutCreance',
        dtype='float64',
        name='financial_loss',
        post_processing=convert_numeric,
    )
    insurer_cost: DataColumn = DataColumn(
        raw_name='Coût assureur',
        dtype='float64',
        name='insurer_cost',
        post_processing=convert_numeric,
    )
    self_insurance_cost: DataColumn = DataColumn(
        raw_name='Auto assurance',
        dtype='float64',
        name='self_insurance_cost',
        post_processing=convert_numeric,
    )
    organization_cost: DataColumn = DataColumn(
        raw_name='Coût client',
        dtype='float64',
        name='organization_cost',
        post_processing=convert_numeric,
    )
    total_accident_cost: DataColumn = DataColumn(
        raw_name='Coût global',
        dtype='float64',
        name='total_accident_cost',
        post_processing=convert_numeric,
    )
    accident_status: DataColumn = DataColumn(
        raw_name='Clôturé',
        dtype='string',
        post_processing=mapper_factory(AccidentStatus),
        name='accident_status'
    )
    expert_first_name: DataColumn = DataColumn(
        raw_name='Expert - Prénom',
        dtype='string',
        post_processing=convert_string,
        name='expert_first_name'
    )
    expert_last_name: DataColumn = DataColumn(
        raw_name='Expert - Nom',
        dtype='string',
        post_processing=convert_string,
        name='expert_last_name'
    )
    expert_phone_number: DataColumn = DataColumn(
        raw_name='Expert - Téléphone',
        dtype='string',
        post_processing=convert_string,
        name='expert_phone_number'
    )
    expert_email: DataColumn = DataColumn(
        raw_name='Expert - Email',
        dtype='string',
        post_processing=convert_string,
        name='export_email'
    )
    expert_days: DataColumn = DataColumn(
        raw_name='Expert - Jours de présence',
        dtype='Int64',
        name='expert_days'
    )
    expert_date: DataColumn = DataColumn(
        raw_name="Date de passage de l'expert",
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='expert_date'
    )
    expert_costs = DataColumn(
        raw_name='CoutExpertise',
        dtype='float64',
        name='expert_costs',
        post_processing=convert_numeric,
    )
    was_reimbursed: DataColumn = DataColumn(
        raw_name='Remboursement',
        dtype="boolean",
        post_processing=convert_boolean,
        name='was_reimbursed',
    )
    complaint_filed: DataColumn = DataColumn(
        raw_name='Dépôt de plainte',
        dtype='Int64',
        name='complaint_filed',
    )
    closing_date: DataColumn = DataColumn(
        raw_name='Date clôture',
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='closing_date',
    )
    claim_reception_date: DataColumn = DataColumn(
        raw_name='Date de réception du constat',
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='claim_reception_date',
    )
    claim_sent_insurer: DataColumn = DataColumn(
        raw_name="Constat envoyé à l'assureur",
        dtype="boolean",
        post_processing=convert_boolean,
        name='claim_sent_insurer',
    )
    claim_sent_insurer_date: DataColumn = DataColumn(
        raw_name="Date d'envoi du constat à l'assureur",
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='claim_sent_insurer_date',
    )
    deductible_higher_than_damage: DataColumn = DataColumn(
        raw_name="Franchise supérieure à la réparation",
        dtype="boolean",
        post_processing=convert_boolean,
        name='deductible_higher_than_damage',
    )
    commute_accident: DataColumn = DataColumn(
        raw_name="Trajet domicile travail",
        dtype="boolean",
        post_processing=convert_boolean,
        name='commute_accident',
    )
    weekend_accident: DataColumn = DataColumn(
        raw_name="Accident de week-end",
        dtype="boolean",
        post_processing=convert_boolean,
        name='weekend_accident',
    )
    expert_rapport_date: DataColumn = DataColumn(
        raw_name="Date de rapport d'expertise",
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='expert_rapport_date',
    )
    accident_repair_start_date: DataColumn = DataColumn(
        raw_name="Date de début de réparation",
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='accident_repair_start_date',
    )
    accident_repair_end_date: DataColumn = DataColumn(
        raw_name="Date de fin de réparation",
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='accident_repair_end_date',
    )
    vehicle_return_date: DataColumn = DataColumn(
        raw_name=(
            "Date de remise du véhicule au collaborateur après réparation"
        ),
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='vehicle_return_date',
    )
    accident_location: DataColumn = DataColumn(
        raw_name="Lieu du sinistre",
        dtype='string',
        post_processing=convert_string,
        name='accident_location',
    )
    insurance_deductible_cost: DataColumn = DataColumn(
        raw_name='insurance_deductible_cost',
        dtype="float64",
        name='insurance_deductible_cost'
    )
    deductible_level = DataColumn(
        raw_name='Franchise contractuelle',
        dtype='float64',
        name='deductible_level'
    )
    insurance_policy_ref = DataColumn(
        raw_name='N° Police cie',
        name='insurance_policy_ref',
        dtype='string',
    )
    insurance_policy_version = DataColumn(
        raw_name='NumeroAvenant',
        name='insurance_policy_version',
        dtype='string',
        post_processing=convert_string,
    )
    insurance_yearly_cost = DataColumn(
        raw_name='CoutAssurance',
        dtype='float64',
        name='insurance_yearly_cost',
        post_processing=convert_numeric,
    )
    insurance_product = DataColumn(
        raw_name='Produit',
        dtype='string',
        name='insurance_product',
        post_processing=convert_string,
    )
    third_party_name = DataColumn(
        raw_name='Tiers : saisis ou identifiés',
        dtype='string',
        post_processing=convert_string,
        name='third_party_name',
    )
    accident_description = DataColumn(
        raw_name='Circonstances',
        dtype='string',
        post_processing=convert_string,
        name='accident_description'
    )
    repair_provider = DataColumn(
        raw_name='Reparateur',
        dtype='string',
        post_processing=convert_string,
        name='repair_provider'
    )
    post_code_provider = DataColumn(
        raw_name='CPFournisseur',
        dtype='Int64',
        post_processing=convert_numeric,
        name='post_code_provided'
    )
    city_provider = DataColumn(
        raw_name='VilleFournisseur',
        dtype='string',
        post_processing=convert_string,
        name='city_provider'
    )
    is_prefered_provider = DataColumn(
        raw_name='FournisseurPrivilegie',
        dtype='boolean',
        post_processing=convert_boolean,
        name='is_prefered_provider',
    )
    bodily_injury = DataColumn(
        raw_name='FlagCorporel',
        dtype='boolean',
        name='bodily_injury',
        post_processing=convert_boolean,
    )
    accident_weekday = DataColumn(
        raw_name='JourSemaineSinistre',
        dtype='string',
        name='accident_weekday',
        post_processing=lambda x: convert_string(x).str[4:]
    )
    is_total_damage = DataColumn(
        raw_name='NatureSinistre',
        dtype='boolean',
        name='is_total_damage',
        post_processing=lambda x: convert_boolean(
            x,
            pos_value='total',
            neg_value='partiel',
        ),
    )
    is_damages = DataColumn(
        raw_name='Degats',
        dtype='boolean',
        name='is_damages',
        post_processing=convert_boolean,
    )
    accident_comment = DataColumn(
        raw_name='Circonstance',
        dtype='string',
        name='accident_comment',
        post_processing=convert_string,
    )
    opening_date: DataColumn = DataColumn(
        raw_name="Date de création",
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='opening_date',
    )
    public_liability_material_costs = DataColumn(
        raw_name='Coût',
        dtype='float64',
        name='public_liability_material_costs',
        post_processing=convert_numeric,
    )
    public_liability_bodily_costs = DataColumn(
        raw_name='Coût',
        dtype='float64',
        name='public_liability_bodily_costs',
        post_processing=convert_numeric,
    )
    public_liability_deductible = DataColumn(
        raw_name='Coût',
        dtype='float64',
        name='public_liability_deductible',
        post_processing=convert_numeric,
    )
    glass_costs = DataColumn(
        raw_name='Coût.6',
        dtype='float64',
        name='glass_costs',
        post_processing=convert_numeric,
    )
    insurer_status: DataColumn = DataColumn(
        raw_name='StatutAssureur',
        dtype='string',
        post_processing=mapper_factory(AccidentInsurerStatus),
        name='insurer_status',
    )
    garage_status: DataColumn = DataColumn(
        raw_name='garage_status',
        dtype='string',
        post_processing=mapper_factory(AccidentGarageStatus),
        name='garage_status',
    )
