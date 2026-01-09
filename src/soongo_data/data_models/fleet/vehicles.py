""" Vehicle

Defines vehicle characteristics as table column to be fetched across the
different connectors. Different connectors may use column variants
(e.g. different raw_name or different post_processing required)
"""
from soongo_data.data_models.base import BaseModel, DataColumn
from soongo_data.utils.enums import (
    EnergyTypes, FiscalType, Suppliers, TransmissionTypes, VehicleStatus,
    mapper_factory, Models, Makes, RegistrationType
)
from soongo_data.utils.post_processing import (convert_makes, convert_model)
from soongo_data.utils.type import (BooleanConverter, DateConverter,
                                    VinConverter,
                                    convert_0_to_nan, convert_boolean,
                                    convert_date, convert_g_to_kg,
                                    convert_numeric, convert_string,
                                    default_plate_converter)


class VehiclesModel(BaseModel):
    plate_number: DataColumn = DataColumn(
        raw_name='Immatriculation',
        dtype='string',
        post_processing=default_plate_converter,
        name='plate_number',
    )
    vin: DataColumn = DataColumn(
        raw_name='Num CHassis',
        dtype='string',
        post_processing=VinConverter(),
        name='vin',
    )
    vehicle_connector_id: DataColumn = DataColumn(
        raw_name='id',
        dtype='string',
        post_processing=convert_string,
        name='vehicle_connector_id',
    )
    vehicle_id: DataColumn = DataColumn(
        raw_name='vehicle_id',
        dtype='string',
        post_processing=convert_string,
        name='vehicle_id',
        description='SoonGo internal id',
    )
    vehicle_name: DataColumn = DataColumn(
        raw_name='Nom du véhicule',
        dtype='string',
        post_processing=convert_string,
        name='vehicle_name',
    )
    registration_date: DataColumn = DataColumn(
        raw_name="Date de l'immatriculation",
        dtype='string',
        post_processing=convert_string,
        name='registration_date',
    )
    entity_1: DataColumn = DataColumn(
        raw_name='Entité 1',
        dtype='string',
        post_processing=convert_string,
        name='entity_1',
    )
    entity_2: DataColumn = DataColumn(
        raw_name='Entité 2',
        dtype='string',
        post_processing=convert_string,
        name='entity_2',
    )
    entity_3: DataColumn = DataColumn(
        raw_name='Entité 3',
        dtype='string',
        post_processing=convert_string,
        name='entity_3',
    )
    cost_center: DataColumn = DataColumn(
        raw_name='Centre de coûts',
        dtype='string',
        post_processing=convert_string,
        name='cost_center',
    )
    cost_center_id: DataColumn = DataColumn(raw_name="N° centre de coûts", dtype="string", name="cost_center_id")
    car_supplier: DataColumn = DataColumn(
        raw_name='Fournisseur',
        dtype='string',
        post_processing=mapper_factory(Suppliers),
        name='car_supplier',
    )
    make: DataColumn = DataColumn(
        raw_name='Marque',
        dtype='string',
        post_processing=mapper_factory(Makes),
        name='make',
    )
    model: DataColumn = DataColumn(
        raw_name='Modèle',
        dtype='string',
        post_processing=mapper_factory(Models),
        name='model',
    )
    model_category: DataColumn = DataColumn(
        raw_name='model_category',
        dtype='string',
        post_processing=convert_string,
        name='model_category',
    )
    model_version: DataColumn = DataColumn(
        raw_name='Version',
        dtype='string',
        post_processing=convert_string,
        name='model_version',
    )
    model_ref = DataColumn(
        raw_name='Modèle constructeur > Référence',
        name="model_ref",
        dtype='string',
        post_processing=convert_string,
    )
    vehicle_internal_category = DataColumn(
        raw_name='Catégorie interne',
        dtype='string',
        post_processing=convert_string,
        name='vehicle_internal_category',
    )
    order_reference: DataColumn = DataColumn(
        raw_name='Référence de commande',
        dtype='string',
        post_processing=convert_string,
        name='order_reference',
    )
    owner: DataColumn = DataColumn(
        raw_name='Propriétaire',
        dtype='string',
        post_processing=convert_string,
        name='owner',
    )
    fiscal_type: DataColumn = DataColumn(
        raw_name='Genre fiscal',
        dtype='string',
        name='fiscal_type',
        post_processing=mapper_factory(FiscalType),
    )
    vehicle_status: DataColumn = DataColumn(
        raw_name="Statut du véhicule",
        dtype='string',
        name='vehicle_status',
        post_processing=mapper_factory(VehicleStatus),
        # TODO: consider extracting the date information in a column
    )
    full_model: DataColumn = DataColumn(
        raw_name="Description du véhicule",
        dtype='string',
        post_processing=convert_string,
        name='full_model',
    )
    vehicle_tag: DataColumn = DataColumn(
        raw_name="Étiquette",
        dtype='string',
        post_processing=convert_string,
        name='vehicle_tag',
    )
    fiscal_power: DataColumn = DataColumn(
        raw_name="Puissance fiscale",
        dtype="Int64",
        name='fiscal_power',
    )
    energy: DataColumn = DataColumn(
        raw_name="Énergie",
        dtype='string',
        name='energy',
        post_processing=mapper_factory(EnergyTypes),
    )
    secondary_energy: DataColumn = DataColumn(
        raw_name="Énergie",
        dtype='string',
        name='secondary_energy',
        post_processing=convert_string,
    )
    hybridation_type: DataColumn = DataColumn(
        raw_name="Énergie",
        dtype='string',
        name='hybridation_type',
        post_processing=convert_string,
    )
    motor_energy_type: DataColumn = DataColumn(
        raw_name='energyType',
        dtype='string',
        name='motor_energy_type',
        post_processing=convert_string,
        description=(
            'Motor type such as hybrid ICE and plugin, not specifying fuel'
        )
    )
    motor_fuels: DataColumn = DataColumn(
        raw_name='fuelType',
        dtype='string',
        name='motor_fuels',
        post_processing=convert_string,
        description=(
            'Motor fuels such as petrol or diesel not specifying plugin or not'
        )
    )
    serial_number: DataColumn = DataColumn(
        raw_name="Numéro de série",
        dtype='string',
        post_processing=convert_string,
        name='serial_number',
    )
    manufacturer_price_tax_inc: DataColumn = DataColumn(
        raw_name="Prix constructeur - TTC",
        dtype='float64',
        post_processing=convert_string,
        name='manufacturer_price_tax_inc',
    )
    manufacturer_price_tax_exc: DataColumn = DataColumn(
        raw_name="Prix constructeur - HT",
        dtype='float64',
        post_processing=convert_numeric,
        name='manufacturer_price_tax_exc',
    )
    rebate_rate: DataColumn = DataColumn(
        raw_name="Pourcentage de remise",
        dtype='float64',
        name='rebate_rate',
    )
    rebate_value: DataColumn = DataColumn(
        raw_name="rebate_value",
        dtype='float64',
        name='rebate_value',
    )
    rebate_price: DataColumn = DataColumn(
        raw_name="Prix d'achat remisé",
        dtype='float64',
        name='rebate_price',
        post_processing=convert_0_to_nan,
        description='Rebate price TTC',
    )
    rebate_price_ht: DataColumn = DataColumn(
        raw_name="Contrat - Prix d'achat remisé HT",
        dtype='float64',
        name='rebate_price_ht',
    )
    rebate_price_exc_accessory_ht: DataColumn = DataColumn(
        raw_name="Contrat - Prix d'achat remisé HT",
        dtype='float64',
        name='rebate_price_exc_accessory_ht',
    )
    vehicle_age: DataColumn = DataColumn(
        raw_name="Âge du véhicule",
        dtype='Int64',
        name='vehicle_age',
    )
    door_count: DataColumn = DataColumn(
        raw_name="Nombre de portes",
        dtype='Int64',
        name='door_count',
    )
    seat_count: DataColumn = DataColumn(
        raw_name="Nb places assises (S.1)",
        dtype='Int64',
        name='seat_count',
    )
    vehicle_country: DataColumn = DataColumn(
        raw_name="Pays",
        dtype='string',
        post_processing=convert_string,
        name='vehicle_country',
    )
    montain_law_applicable: DataColumn = DataColumn(
        raw_name="Concerné par la loi montagne",
        dtype='string',
        post_processing=convert_string,
        name='montain_law_applicable',
    )
    winter_gear: DataColumn = DataColumn(
        raw_name="Dispose d'un équipement hivernal",
        dtype='string',
        post_processing=convert_string,
        name='winter_gear',
    )
    winter_gear_type: DataColumn = DataColumn(
        raw_name="Type d'équipement",
        dtype='string',
        post_processing=convert_string,
        name='winter_gear_type',
    )
    to_renew: DataColumn = DataColumn(
        raw_name="A renouveler",
        dtype='string',
        post_processing=convert_string,
        name='to_renew',
    )
    steps_before_issuance: DataColumn = DataColumn(
        raw_name="Étapes avant MEC",
        dtype='string',
        post_processing=convert_string,
        name='unknown',
    )
    entry_into_service_date: DataColumn = DataColumn(
        raw_name='Première mise en circulation',
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='entry_into_service_date',
    )
    country_entry_into_service_date: DataColumn = DataColumn(
        raw_name='Date de la première immatriculation en France',
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='country_entry_into_service_date',
        description='Date of first immatriculation in current country',
    )
    entry_into_fleet_date = DataColumn(
        raw_name="Date d'entrée",
        name="entry_into_fleet_date",
        dtype="datetime64[ns]",
    )
    exit_from_fleet_date = DataColumn(
        raw_name="Date de sortie",
        name="exit_from_fleet_date",
        dtype="datetime64[ns]",
    )
    billed_entity: DataColumn = DataColumn(
        raw_name='Entité Facturée',
        dtype='string',
        post_processing=convert_string,
        name='billed_entity',
    )
    vehicle_time_in_fleet: DataColumn = DataColumn(
        raw_name='Ancienneté dans le parc',
        dtype='Int64',
        name='vehicle_time_in_fleet'
    )
    air_quality_certificate_number: DataColumn = DataColumn(
        raw_name="Numéro vignette Crit'Air",
        dtype='Int64',
        name='air_quality_certificate_number',
    )
    is_air_quality_certified: DataColumn = DataColumn(
        raw_name="Vignette Crit'Air reçue",
        dtype='boolean',
        post_processing=convert_boolean,
        name='is_air_quality_certified',
    )
    air_quality_certificate_level: DataColumn = DataColumn(
        raw_name="Niveau de la vignette",
        dtype='Int64',
        name='air_quality_certificate_level',
    )
    is_axle_tax: DataColumn = DataColumn(
        raw_name='Taxe essieu',
        dtype='boolean',
        post_processing=convert_boolean,
        name='axle_tax',
    )
    initial_mileage: DataColumn = DataColumn(
        raw_name="Premier relevé km",
        dtype="Int64",
        name="initial_mileage",
    )
    final_mileage: DataColumn = DataColumn(
        raw_name="Dernier relevé km",
        dtype="Int64",
        name="final_mileage",
    )
    estimated_fuel_consumption: DataColumn = DataColumn(
        raw_name='Estim.',
        dtype='float64',
        name='estimated_fuel_consumption',
    )
    manufacturer_fuel_consumption: DataColumn = DataColumn(
        raw_name='Constr.',
        dtype='float64',
        post_processing=convert_numeric,
        name='manufacturer_fuel_consumption',
    )
    order_date: DataColumn = DataColumn(
        raw_name='Contrat - Date de commande',
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='order_date',
    )
    participation_at_purchase: DataColumn = DataColumn(
        raw_name="Contrat - Participation totale à l'achat TTC",
        dtype='float64',
        name='participation_at_purchase',
    )
    accessory_price_tax_inc: DataColumn = DataColumn(
        raw_name="Contrat - Prix accessoires TTC",
        dtype='float64',
        name='accessory_price_tax_inc',
    )
    accessory_price_tax_exc: DataColumn = DataColumn(
        raw_name="Contrat - Prix accessoires HT",
        dtype='float64',
        name='accessory_price_tax_exc',
    )
    option_price_tax_inc: DataColumn = DataColumn(
        raw_name="Contrat - Prix des options TTC",
        dtype='float64',
        name='option_price_tax_inc',
    )
    option_price_tax_exc: DataColumn = DataColumn(
        raw_name="Contrat - Prix des options HT",
        dtype='float64',
        name='option_price_tax_exc',
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
        post_processing=DateConverter(date_format=r'%d/%m/%Y'),
    )
    battery_price_tax_inc: DataColumn = DataColumn(
        raw_name='Contrat - Prix batterie TTC',
        dtype='float64',
        name='battery_price_tax_inc',
    )
    battery_price_tax_exc: DataColumn = DataColumn(
        raw_name='Contrat - Prix batterie HT',
        dtype='float64',
        name='battery_price_tax_exc',
    )
    CO2_emissions_norm: DataColumn = DataColumn(
        raw_name='Véhicule - Norme d?émissions de CO2',
        dtype='string',
        name='CO2_emissions_norm',
    )
    vehicle_type_identification_code: DataColumn = DataColumn(
        raw_name='Véhicule - Type Mine',
        dtype='string',
        name='vehicle_type_identification_code',
    )
    vehicle_finishing: DataColumn = DataColumn(
        raw_name='Véhicule - Finition',
        dtype='string',
        name='vehicle_finishing',
    )
    vehicle_external_colour: DataColumn = DataColumn(
        raw_name='Véhicule - Couleur extérieure',
        dtype='string',
        name='vehicle_external_colour',
    )
    hybrid_theoretical_consumption: DataColumn = DataColumn(
        raw_name='Véhicule - Conso. hybride moteur thermique',
        dtype='float64',
        name='hybrid_theoretical_consumption',
    )
    electricity_consumption: DataColumn = DataColumn(
        raw_name='Véhicule - Conso. hybride moteur thermique',
        dtype='float64',
        name='electricity_consumption',
    )
    fuel_tank_capacity: DataColumn = DataColumn(
        raw_name='Véhicule - Capacité du réservoir',
        dtype='float64',
        name='fuel_tank_capacity',
    )
    transmission_type: DataColumn = DataColumn(
        raw_name='Véhicule - Transmission',
        dtype='string',
        name='transmission_type',
        post_processing=mapper_factory(TransmissionTypes),
    )
    transmission_details: DataColumn = DataColumn(
        raw_name='Véhicule - Détails transmission',
        dtype='string',
        name='transmission_details',
    )
    transmission_description: DataColumn = DataColumn(
        raw_name='Véhicule - Description transmission',
        dtype='string',
        name='transmission_description',
    )
    gear_count: DataColumn = DataColumn(
        raw_name='Véhicule - Nombre de rapports',
        dtype='Int64',
        name='gear_count',
    )
    vehicle_variant: DataColumn = DataColumn(
        raw_name='Véhicule - Type, variante, version (D.2)',
        dtype='string',
        name='vehicle_variant',
    )
    vehicle_max_technical_weight: DataColumn = DataColumn(
        raw_name='Véhicule - Masse max. techn. (F.1)',
        dtype='Int64',
        name='vehicle_max_technical_mass',
        post_processing=convert_0_to_nan,
    )
    vehicle_max_rolling_weight: DataColumn = DataColumn(
        raw_name='Véhicule - F3',
        dtype='Int64',
        name='vehicle_max_rolling_weight',
        post_processing=convert_0_to_nan,
    )
    vehicle_max_weight: DataColumn = DataColumn(
        raw_name='Véhicule - PTRA',
        dtype='Int64',
        name='vehicle_max_weight',
        post_processing=convert_0_to_nan,
    )
    curb_weight: DataColumn = DataColumn(
        raw_name='Véhicule - Poids à vide (G)',
        dtype='Int64',
        name='curb_weight',
        post_processing=convert_0_to_nan,
    )
    vehicle_empty_weight: DataColumn = DataColumn(
        raw_name='Véhicule - Poids à vide national (G.1)',
        dtype='Int64',
        name='vehicle_empty_weight',
        post_processing=convert_0_to_nan,
    )
    vehicle_official_category: DataColumn = DataColumn(
        raw_name='Véhicule - Catégorie du véhicule (J)',
        dtype='string',
        name='vehicle_official_category',
    )
    official_body_category: DataColumn = DataColumn(
        raw_name='Véhicule - Carrosserie (nationale) (J.3)',
        dtype='string',
        name='official_body_category',
    )
    gac_body_category: DataColumn = DataColumn(
        raw_name='Véhicule - Carrosserie',
        dtype='string',
        name='gac_body_category',
    )
    motor_volume: DataColumn = DataColumn(
        raw_name='Véhicule - Cylindrée (P.1)',
        dtype='Int64',
        name='motor_volume',
    )
    motor_power: DataColumn = DataColumn(
        raw_name='Véhicule - Puissance nette max. (P.2)',
        dtype='Int64',
        name='motor_power',
        post_processing=convert_0_to_nan,
    )
    vehicule_sound_level: DataColumn = DataColumn(
        raw_name='Véhicule - Niveau sonore (U.1)',
        dtype='Int64',
        name='vehicule_sound_level',
    )
    motor_speed: DataColumn = DataColumn(
        raw_name='Véhicule - Vitesse du moteur (U.2)',
        dtype='Int64',
        name='motor_speed',
    )
    order_dealership: DataColumn = DataColumn(
        raw_name='Véhicule - Garage de commande (détails)',
        dtype='string',
        name='order_dealership',
    )
    order_delivery_place: DataColumn = DataColumn(
        raw_name='Véhicule - Lieu de livraison',
        dtype='string',
        name='order_delivery_place',
    )
    restitution_address: DataColumn = DataColumn(
        raw_name='Adresse de restitution <br/>(détails)',
        dtype='string',
        name='restitution_address',
    )
    front_tire_size: DataColumn = DataColumn(
        raw_name='Véhicule - Dimension pneu AV',
        dtype='string',
        name='front_tire_size',
    )
    back_tire_size: DataColumn = DataColumn(
        raw_name='Véhicule - Dimension pneu AR',
        dtype='string',
        name='back_tire_size',
    )
    has_speed_regulator: DataColumn = DataColumn(
        raw_name='Véhicule - Régulateur de vitesse',
        dtype="boolean",
        name='has_speed_regulator',
        post_processing=BooleanConverter(pos_value='1.0', neg_value='0'),
    )
    has_speed_limiter: DataColumn = DataColumn(
        raw_name='Véhicule - Limiteur de vitesse',
        dtype="boolean",
        name='has_speed_limiter',
        post_processing=convert_boolean,
    )
    has_particle_filter: DataColumn = DataColumn(
        raw_name='Véhicule - Filtre à particules',
        dtype="boolean",
        name='particle_filter',
        post_processing=convert_boolean,
    )
    vehicle_length: DataColumn = DataColumn(
        raw_name='Véhicule - Longueur',
        dtype='Int64',
        name='vehicle_length',
    )
    vehicle_height: DataColumn = DataColumn(
        raw_name='Véhicule - Hauteur',
        dtype='Int64',
        name='vehicle_height',
    )
    vehicle_width: DataColumn = DataColumn(
        raw_name='Véhicule - Largeur',
        dtype='Int64',
        name='vehicle_width',
    )
    has_double_cabin: DataColumn = DataColumn(
        raw_name='Véhicule - Double cabine',
        dtype="boolean",
        name='has_double_cabin',
        post_processing=BooleanConverter(pos_value='oui', neg_value='non'),
    )
    make_code: DataColumn = DataColumn(
        raw_name='Véhicule - Code constructeur',
        dtype='string',
        name='make_code',
    )
    battery_capacity: DataColumn = DataColumn(
        raw_name='Véhicule - Capacité de la batterie',
        dtype='Int64',
        name='battery_capacity',
    )
    machinery_insurance: DataColumn = DataColumn(
        raw_name='Véhicule - Assurance bris de machine',
        dtype="boolean",
        name='machinery_insurance',
    )
    vehicle_record_date: DataColumn = DataColumn(
        raw_name='Véhicule - Date de saisie',
        dtype='datetime64[ns]',
        name='vehicle_record_date',
        post_processing=lambda x: convert_date(x, date_format=r'%d/%m/%Y'),
    )
    vehicle_last_update: DataColumn = DataColumn(
        raw_name='Véhicule - Date de modification',
        dtype='datetime64[ns]',
        name='vehicle_last_update',
        post_processing=lambda x: convert_date(x, date_format=r'%d/%m/%Y'),
    )
    next_technical_inspection: DataColumn = DataColumn(
        raw_name='Prochain contrôle technique',
        dtype='datetime64[ns]',
        name='next_technical_inspection',
        post_processing=lambda x: convert_date(x, date_format=r'%d/%m/%Y'),
    )
    manufacturer_rebate_value_tax_inc: DataColumn = DataColumn(
        raw_name='Contrat - Remise constructeur TTC',
        dtype='float64',
        name='manufacturer_rebate_value_tax_inc',
        post_processing=convert_numeric,
    )
    manufacturer_rebate_value_tax_exc: DataColumn = DataColumn(
        raw_name='Contrat - Remise constructeur HT',
        dtype='float64',
        name='manufacturer_rebate_value_tax_exc',
        post_processing=convert_numeric,
    )
    accessories_employee: DataColumn = DataColumn(
        raw_name="Véhicule - Accessoires à charge collaborateur",
        dtype='string',
        name="accessories_employee",
    )
    accessories_organisation: DataColumn = DataColumn(
        raw_name="Véhicule - Accessoires à charge client",
        dtype='string',
        name="accessories_organisation",
    )
    options_employee: DataColumn = DataColumn(
        raw_name="Véhicule - Options remisées à charge collaborateur",
        dtype='string',
        name="options_employee",
    )
    options_organisation: DataColumn = DataColumn(
        raw_name="Véhicule - Options remisées à charge client",
        dtype='string',
        name="options_organisation",
    )
    registration_update_date: DataColumn = DataColumn(
        raw_name="Date de MAJ de l'immat",
        dtype="datetime64[ns]",
        name="registration_update_date",
        post_processing=lambda x: convert_date(x, date_format=r'%d/%m/%Y'),
    )
    registration_record_date: DataColumn = DataColumn(
        raw_name="Date de 1ère saisie de l'immat",
        dtype="datetime64[ns]",
        name="registration_record_date",
        post_processing=lambda x: convert_date(x, date_format=r'%d/%m/%Y'),
    )
    registration_type = DataColumn(
        raw_name='Genre carte grise',
        dtype='string',
        post_processing=mapper_factory(RegistrationType),
        name='registration_type'
    )
    recording_datetime = DataColumn(
        raw_name="Date d'insertion",
        dtype='string',
        post_processing=convert_string,
        name='recording_datetime'
    )
    vehicle_site = DataColumn(
        raw_name='Site de rattachement',
        dtype='string',
        post_processing=convert_string,
        name='vehicle_site',
    )
    laden_weight = DataColumn(
        raw_name='PTAC',
        dtype='string',
        post_processing=convert_numeric,
        name='laden_weight',
    )
    maximum_load_weight = DataColumn(
        raw_name='Charge utile',
        dtype='string',
        post_processing=convert_numeric,
        name='maximum_load_weight',
    )
    theoretical_fuel_consumption = DataColumn(
        raw_name="theoretical_fuel_consumption",
        dtype='float64',
        name='theoretical_fuel_consumption',
    )
    theoretical_urban_fuel_consumption = DataColumn(
        raw_name="theoretical_urban_fuel_consumption",
        dtype='float64',
        name='theoretical_urban_fuel_consumption',
    )
    theoretical_extra_urban_fuel_consumption = DataColumn(
        raw_name="theoretical_extra_urban_fuel_consumption",
        dtype='float64',
        name='theoretical_extra_urban_fuel_consumption',
    )
    co2_per_km = DataColumn(
        raw_name="co2_per_km",
        dtype="float64",
        name='co2_per_km',
        post_processing=convert_g_to_kg,
        description='Theoretical, manufacturer provided, CO2 per km',
    )
    measured_fuel_consumption = DataColumn(
        raw_name="measured_fuel_consumption",
        dtype='float64',
        name='measured_fuel_consumption',
    )
    measured_CO2_per_km = DataColumn(
        raw_name="measured_CO2_per_km",
        dtype='string',
        name='measured_CO2_per_km',
    )
    co2_production = DataColumn(
        raw_name='co2_production',
        dtype='float64',
        name='co2_production',
    )
    co2_recycling = DataColumn(
        raw_name='co2_recycling',
        dtype='float64',
        name='co2_recycling',
    )
    max_elec_recharge = DataColumn(
        raw_name='max_elec_recharge',
        dtype='float64',
        name='max_elec_recharge',
    )
    model_id = DataColumn(
        raw_name='model_id',
        dtype='string',
        name='model_id',
    )
    brand_id = DataColumn(
        raw_name='brand_id',
        dtype='string',
        name='brand_id',
    )
    trim_id = DataColumn(
        raw_name='trim_id',
        dtype='string',
        name='trim_id',
    )
    vehicle_type = DataColumn(
        raw_name='vehicle_type',
        dtype='string',
        name='vehicle_type',
    )