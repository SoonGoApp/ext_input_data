"""Key Product Indicators

List all KPIs and their definition
"""

import logging
import typing
from dataclasses import dataclass
from enum import Enum, StrEnum, auto, unique

import pandas as pd

from soongo_data.utils.type import convert_string, str_is_nan


class UpperStrEnum(StrEnum):
    def _generate_next_value_(name, start, count, last_values):
        return name.upper()


@unique
class ContractType(Enum):
    long_duration = "LLD"
    short_medium_duration = "LCD_LMD"
    acquisition = "ACQ"
    lop = "LOP"  # Lease with option to purchase e.g. LOA

    @classmethod
    def mapping(cls):
        return {
            "LLD": cls.long_duration.value,
            "LCD/LMD": cls.short_medium_duration.value,
            "LMD": cls.short_medium_duration.value,
            "ACQ": cls.acquisition.value,
            "GESTION": cls.acquisition.value,
            "Achat": cls.acquisition.value,
            "LOA": cls.lop.value,
            "LME": cls.short_medium_duration.value,
            "LCD": cls.short_medium_duration.value,
            "crédit bail": cls.lop.value,
            "cb": cls.lop.value,
            "location": cls.long_duration.value,
            "l - md": cls.short_medium_duration.value,
            "location à durée et kilométrage variable": None,
            "ldd": cls.long_duration.value,
            "location md": cls.short_medium_duration.value,
            "credit bail": cls.lop.value,
            "location courte": cls.short_medium_duration.value,
            "ld": cls.long_duration.value,
            "mco": None,
            "location courte durée": cls.short_medium_duration.value,
            "propriétaire": cls.acquisition.value,
            "location longue durée": cls.long_duration.value,
        }


@unique
class RentCategory(Enum):
    financial_rent = "FINANCIAL_RENT"
    financial_rent_adjustment = "FINANCIAL_RENT_ADJUSTMENT"
    rent_management_fees = "RENT_MANAGEMENT_FEES"
    rent_maintenance = "RENT_MAINTENANCE"
    rent_telematic = "RENT_TELEMATIC"
    rent_tires = "RENT_TIRES"
    rent_fuel_card = "RENT_FUEL_CARD"
    rent_financial_loss = "RENT_FINANCIAL_LOSS"
    rent_replacement_vehicle_actual = "RENT_REPLACEMENT_VEHICLE_ACTUAL"
    rent_replacement_vehicle_flat_fee = "RENT_REPLACEMENT_VEHICLE_FLAT_FEE"
    rent_relay_vehicle_actual = "RENT_RELAY_VEHICLE_ACTUAL"
    rent_relay_vehicle_flat_fee = "RENT_RELAY_VEHICLE_FLAT_FEE"
    rent_assistance = "RENT_ASSISTANCE"
    rent_others = "RENT_OTHERS"
    rent_end_of_year = "RENT_END_OF_YEAR"


@unique
class InsurancePremiums(Enum):
    insurance_vehicle = "INSURANCE_VEHICLE"
    insurance_glass = "INSURANCE_GLASS"
    insurance_replacement_vehicle = "INSURANCE_REPLACEMENT_VEHICLE"
    insurance_assistance = "INSURANCE_ASSISTANCE"
    insurance_financial_loss = "INSURANCE_FINANCIAL_LOSS"
    insurance_restitution = "INSURANCE_RESTITUTION"


@unique
class FuelTypes(Enum):
    sp95 = "SP95"
    sp95_premium = "SP95_PREMIUM"
    sp95e10 = "SP95_E10"
    sp98 = "SP98"
    sp98_premium = "SP98_PREMIUM"
    sp100 = "SP100"
    diesel = "DIESEL"
    diesel_premium = "DIESEL_PREMIUM"
    b8 = "B8"
    b10 = "B10"
    b20 = "B20"
    b30 = "B30"
    b50 = "B50"
    b70 = "B70"
    b100 = "B100"
    e85 = "E85"
    lpg = "LPG"
    gnc = "GNC"
    bio_gnc = "BIO_GNC"
    default_gaz = "DEFAULT_GAZ"
    adblue = "ADBLUE"
    electricity = "ELECTRICITY"
    hydrogen = "HYDROGEN"

    @classmethod
    def mapping(cls):
        return {
            # SP 95E10
            "Sans Plomb 95 E10": cls.sp95e10.value,
            "Sans Plomb 95 E10 - (vide)": cls.sp95e10.value,
            "SP95 - E10": cls.sp95e10.value,
            # SP 95
            "SP95": cls.sp95.value,
            "ESSENCE 95": cls.sp95.value,
            "Super 95 Sans PL": cls.sp95.value,
            "Super 95 Sans PL - (vide)": cls.sp95.value,
            # SP95 always containst 5% Ethanol:
            "Sans Plomb 95 E5": cls.sp95.value,
            # SP95 premium
            "SSP95 Excellium": cls.sp95_premium.value,
            # SP 98
            "SP98": cls.sp98.value,
            "ESSENCE 98": cls.sp98.value,
            "Super 98 Sans PL": cls.sp98.value,
            "Super 98 Sans PL - (vide)": cls.sp98.value,
            # SP98
            "SSP98 Excellium": cls.sp98_premium.value,
            # SP 100
            "SSP 100": cls.sp100.value,
            # Diesel
            "Gazole Excellium": cls.diesel_premium.value,
            "Gazole Excellium - (vide)": cls.diesel_premium.value,
            "Gazole Premier": cls.diesel.value,
            "DIESEL": cls.diesel.value,
            "Gazole Premier - (vide)": cls.diesel.value,
            "DIESEL EXCELLIUM": cls.diesel_premium.value,
            "GASOIL": cls.diesel.value,
            "GASOIL HP": cls.diesel.value,
            "Diesel": cls.diesel.value,
            "Gazole MF": cls.diesel.value,
            # Ad blue
            "ADBLUE": cls.adblue.value,
            "Adblue Bidon": cls.adblue.value,
            "AdBlue Pompe": cls.adblue.value,
            "Lubrifiant": cls.adblue.value,  # Actually unsure
            # B8
            "Diesel B8": cls.b8.value,
            # B10
            "Diesel B10": cls.b10.value,
            "Diesel B10 - (vide)": cls.b10.value,
            # B20
            "BIO DIESEL": cls.b20.value,
            # E85
            "E85 Superéthanol": cls.e85.value,
            "SuperEthanol E85": cls.e85.value,
            # Electricity
            "Recharge électrique débit rapide": cls.electricity.value,
            "Recharge électrique débit moye": cls.electricity.value,
            "Recharge électrique faible déb": cls.electricity.value,
            "Recharge électrique débit": cls.electricity.value,
            "Recharge électrique au tr": cls.electricity.value,
            "Recharge électrique débit ultr - (vide)": cls.electricity.value,
            "recharge électrique débit rapi - (vide)": cls.electricity.value,
            "recharge électrique faible déb - (vide)": cls.electricity.value,
            "recharge électrique débit moye - (vide)": cls.electricity.value,
            # Default gaz
            "Essence": cls.default_gaz.value,
        }


@unique
class CostCategory(Enum):  # Enum inheritance is not allowed in Python
    financial_rent = RentCategory.financial_rent.value
    financial_rent_adjustment = RentCategory.financial_rent_adjustment.value
    rent_management_fees = RentCategory.rent_management_fees.value
    rent_maintenance = RentCategory.rent_maintenance.value
    rent_telematic = RentCategory.rent_telematic.value
    rent_tires = RentCategory.rent_tires.value
    rent_fuel_card = RentCategory.rent_fuel_card.value
    rent_financial_loss = RentCategory.rent_financial_loss.value
    rent_replacement_vehicle_actual = RentCategory.rent_replacement_vehicle_actual.value
    rent_replacement_vehicle_flat_fee = RentCategory.rent_replacement_vehicle_flat_fee.value
    rent_relay_vehicle_actual = RentCategory.rent_relay_vehicle_actual.value
    rent_relay_vehicle_flat_fee = RentCategory.rent_relay_vehicle_flat_fee.value
    rent_assistance = RentCategory.rent_assistance.value
    rent_others = RentCategory.rent_others.value
    rent_end_of_year = RentCategory.rent_end_of_year.value
    insurance_vehicle = InsurancePremiums.insurance_vehicle.value
    insurance_vehicle_vat = "INSURANCE_VEHICLE_VAT"
    other_insurance_costs = "OTHER_INSURANCE_COSTS"
    insurance_glass = InsurancePremiums.insurance_glass.value
    insurance_replacement_vehicle = InsurancePremiums.insurance_replacement_vehicle.value
    insurance_assistance = InsurancePremiums.insurance_assistance.value
    insurance_financial_loss = InsurancePremiums.insurance_financial_loss.value
    insurance_restitution = InsurancePremiums.insurance_restitution.value
    insurance_deductible_cost = "INSURANCE_DEDUCTIBLE_COST"
    insurance_brokerage_cost = "INSURANCE_BROKERAGE_COST"
    termination_fees = "TERMINATION_FEES"
    self_insurance = "SELF_INSURANCE"
    sp98 = FuelTypes.sp98.value
    diesel = FuelTypes.diesel.value
    b10 = FuelTypes.b10.value
    b20 = FuelTypes.b20.value
    b30 = FuelTypes.b30.value
    b50 = FuelTypes.b50.value
    b70 = FuelTypes.b70.value
    b100 = FuelTypes.b100.value
    sp95 = FuelTypes.sp95.value
    sp95e10 = FuelTypes.sp95e10.value
    sp100 = FuelTypes.sp100.value
    lpg = FuelTypes.lpg.value
    e85 = FuelTypes.e85.value
    hydrogen = FuelTypes.hydrogen.value
    diesel_premium = FuelTypes.diesel_premium.value
    default_gaz = FuelTypes.default_gaz.value
    electricity = FuelTypes.electricity.value
    sp95_premium = FuelTypes.sp95_premium.value
    sp98_premium = FuelTypes.sp98_premium.value
    b8 = FuelTypes.b8.value
    gnc = FuelTypes.gnc.value
    bio_gnc = FuelTypes.bio_gnc.value
    heating_oil = "HEATING_OIL"  # Fioul
    fuel_oil = "FUEL_OIL"  # Mazout
    charging_points_recurring = "CHARGING_POINTS_RECURRING"
    charging_point_installation = "CHARGING_POINT_INSTALLATION"
    employer_in_kind_benefits_charges = "EMPLOYER_IN_KIND_BENEFITS_CHARGES"
    employee_in_kind_benefits_charges = "EMPLOYEE_IN_KIND_BENEFITS_CHARGES"
    participation = "PARTICIPATION"
    mobility_credit = "MOBILITY_CREDIT"
    car_allowance = "CAR_ALLOWANCE"
    environmental_bonus = "ENVIRONMENTAL_BONUS"
    environmental_malus = "ENVIRONMENTAL_MALUS"
    company_car_tax = "COMPANY_CAR_TAX"
    co2_tax = "CO2_TAX"
    age_tax = "AGE_TAX"
    heavy_goods_tax = "HEAVY_GOODS_TAX"
    pollutant_tax = "POLLUTANT_TAX"
    corporate_tax_company_car_tax = "CORPORATE_TAX_COMPANY_CAR_TAX"
    corporate_tax_in_kind_benefit = "CORPORATE_TAX_IN_KIND_BENEFIT"
    fines = "FINES"
    deductible_vat = "DEDUCTIBLE_VAT"
    real_short_term_rental = "REAL_SHORT_TERM_RENTAL"
    real_replacement_vehicle_cost = "REAL_REPLACEMENT_VEHICLE_COST"
    real_medium_term_rental = "REAL_MEDIUM_TERM_RENTAL"
    real_relay_vehicle_cost = "REAL_RELAY_VEHICLE_COST"
    real_maintenance = "REAL_MAINTENANCE"
    real_telematics_fee = "REAL_TELEMATICS_FEE"
    real_telematics_install = "REAL_TELEMATICS_INSTALL"
    real_tires_summer = "REAL_TIRES_SUMMER"
    real_tires_winter = "REAL_TIRES_WINTER"
    real_tires_other = "REAL_TIRES_OTHER"
    real_glass = "REAL_GLASS"
    real_fuel_card = "REAL_FUEL_CARD"
    fuel_card_end_of_year = "FUEL_CARD_END_OF_YEAR"
    real_assistance = "REAL_ASSISTANCE"
    adblue = FuelTypes.adblue.value
    real_restitution = "REAL_RESTITUTION"
    real_others = "REAL_OTHERS"
    real_repairs = "REAL_REPAIRS"
    tolls_card = "TOLLS_CARD"
    tolls_real = "TOLLS_REAL"
    parking_card = "PARKING_CARD"
    parking_real = "PARKING_REAL"
    washing_card = "WASHING_CARD"
    washing_real = "WASHING_REAL"
    logo = "LOGO"
    management_software_fee = "MANAGEMENT_SOFTWARE_FEE"
    management_software_install = "MANAGEMENT_SOFTWARE_INSTALL"
    electricity_fees = "ELECTRICITY_FEES"
    parking_fees = "PARKING_FEES"
    toll_fees = "TOLL_FEES"
    weight_tax = "WEIGHT_TAX"
    tax_other = "TAX_OTHER"
    registration_tax = "REGISTRATION_TAX"


@unique
class CO2Categories(Enum):
    CO2_fleet_fuel = "CO2_FLEET_FUEL"
    CO2_production = "CO2_PRODUCTION"
    CO2_recycling = "CO2_recycling"
    CO2_train = "CO2_TRAIN"
    CO2_plane = "CO2_PLANE"
    CO2_rental = "CO2_RENTAL"
    CO2_taxi = "CO2_TAXI"


class mapper_factory:
    def __init__(self, enum_class: Enum) -> None:
        """Return a mapper function which uses the mapping method of the enum
        class to return a function mapping a pandas Series to this mapping.

        :param enum_class: an Enum child class with a mapping method
        """
        self.enum_class = enum_class

    def __call__(self, pd_series: pd.Series) -> pd.Series:
        """Map the original values of a pandas Series to a new set of values

        :param pd_series: a Pandas Series of original_data to map into new
            values

        :raises ValueError: if series contains value not covered by mapping
        """
        pd_series = convert_string(pd_series.fillna("")).str.lower()

        mapping_dict = {key.lower(): value for key, value in self.enum_class.mapping().items()}
        base_values = {
            enum_value.value.lower(): enum_value.value
            for enum_value in self.enum_class
            if isinstance(enum_value.value, str)
        }
        if not base_values:
            base_values = {enum_value.value.name.lower(): enum_value.value.name for enum_value in self.enum_class}
        assert base_values, "Enum values must be strings or have a name attribute"
        mapping_dict.update(base_values)
        missing_values = set(pd_series.loc[~str_is_nan(pd_series)]).difference(list(mapping_dict))
        if missing_values:
            raise ValueError(
                f"The provided mapping keys {mapping_dict.keys()} do not "
                f"cover: the following series value {missing_values}"
            )
        return pd_series.map(mapping_dict)


@unique
class AccidentTypes(Enum):
    material = "MATERIAL"
    human = "HUMAN"
    human_and_material = "HUMAN_AND_MATERIAL"

    @classmethod
    def mapping(cls):
        return {
            "Matériel": cls.material.value,
            "Corporel et Matériel": cls.human_and_material.value,
            "Corporel": cls.human.value,
            "Mixte": cls.human_and_material.value,
            "matériel et corporel": cls.human_and_material.value,
        }


@unique
class AccidentInsurerStatus(Enum):
    declared = "DECLARED"
    claim_for_survey = "CLAIM_FOR_SURVEY"
    expert_report_received = "EXPERT_REPORT_RECEIVED"
    covered = "COVERED"
    not_covered = "NOT_COVERED"
    not_declared = "NOT_DECLARED"
    reimbursed = "REIMBURSED"


@unique
class AccidentGarageStatus(Enum):
    vehicle_in_garage = "VEHICLE_IN_GARAGE"
    quote_received = "QUOTE_RECEIVED"
    repairs_in_progress = "REPAIRS_IN_PROGRESS"
    available = "AVAILABLE"
    quote_validated = "QUOTE_VALIDATED"


@unique
class AccidentContextTypes(Enum):
    collisions = "COLLISIONS"
    theft = "THEFT"
    parking = "PARKING"
    other = "OTHER"
    glass_breakage = "GLASS_BREAKAGE"
    theft_attempt = "THEFT_ATTEMPT"
    fire = "FIRE"
    natural_disaster = "NATURAL_DISASTER"
    vandalism = "VANDALISM"
    part_theft = "PART_THEFT"
    recovered_theft = "RECOVERED_THEFT"

    @classmethod
    def mapping(cls):
        return {
            "Collision": cls.collisions.value,
            "Collision VTAM": cls.collisions.value,
            "Collision Non identifié": cls.collisions.value,
            "Vol": cls.theft.value,
            "VOL": cls.theft.value,
            "VOL RETROUVE": cls.recovered_theft.value,
            "AUTO VOL": cls.theft.value,
            "AUTO Dommages tous accidents": cls.other.value,
            "AUTO Responsabilité Civile": cls.other.value,
            "Stationnement": cls.parking.value,
            "Autre": cls.other.value,
            "DOMMAGES MATERIELS": cls.other.value,
            "Bris de glace": cls.glass_breakage.value,
            "BRIS DE GLACES": cls.glass_breakage.value,
            "AUTO BRIS DE GLACE": cls.glass_breakage.value,
            "Tentative de vol": cls.theft_attempt.value,
            "TENTATIVE DE VOL": cls.theft_attempt.value,
            "Incendie": cls.fire.value,
            "INCENDIE": cls.fire.value,
            "VANDALISME": cls.vandalism.value,
            "Catastrophe naturelle": cls.natural_disaster.value,
            "FORCES DE LA NATURE": cls.natural_disaster.value,
            "AUTO EVENEMENT CLIMATIQUE": cls.natural_disaster.value,
            "VOL D'ELEMENTS DU VEHICULE": cls.part_theft.value,
            "Carrosserie": cls.collisions.value,
            "Bris de pare-brise": cls.glass_breakage.value,
            "collision animal": cls.collisions.value,
            "materiel non responsable": cls.other.value,
            "responsable sans tiers": cls.other.value,
            "tiers non identifie": cls.other.value,
            "vol partiel (effraction)": cls.part_theft.value,
            "materiel responsable 100%": cls.other.value,
            "force de la nature": cls.natural_disaster.value,
            "vol total": cls.theft.value,
            "non défini": cls.other.value,
            "tentative vol": cls.theft_attempt.value,
            "corporel responsable 100%": cls.other.value,
            "corporel non responsable": cls.other.value,
            "materiel responsable 50%": cls.other.value,
            "incendie/vol/bris de glace": cls.other.value,
            "véhicule retrouvé en": cls.collisions.value,
            "collision sans tiers": cls.collisions.value,
            "collision avec tiers": cls.collisions.value,
            "incendie/vol/bris de": cls.other.value,
            "véhicule retrouvé en l'etat": cls.collisions.value,
            "incendie/vol/bris de galce": cls.other.value,
            "véhicule retrouvé en l'état": cls.collisions.value,
            "tiers non identifié": cls.other.value,
            "collision contre animal": cls.collisions.value,
            "grêle": cls.natural_disaster.value,
            "sinistre non garantie": cls.other.value,
            "vol effets, objets accessoires": cls.part_theft.value,
            "collision en chaîne": cls.collisions.value,
            "dégradations volontaires au véhicule": cls.vandalism.value,
            "collision entre deux véhicules": cls.collisions.value,
            "mise en cause ida subi": cls.other.value,
            "véhicule retrouvé après vol": cls.part_theft.value,
            "vol total du véhicule": cls.theft.value,
            "collision contre corps fixe chose inerte": cls.collisions.value,
            "perte de contrôle par assuré - sans tiers": cls.collisions.value,
            "perte de controle : passager blessé": cls.collisions.value,
            "vol d'éléments du véhicule": cls.part_theft.value,
        }


@unique
class AccidentStatus(Enum):
    open = "OPEN"
    closed = "CLOSED"

    @classmethod
    def mapping(cls):
        return {
            "En attente": cls.open.value,
            "Cloturé": cls.closed.value,
            "O": cls.open.value,
            "C": cls.closed.value,
            "En Cours": cls.open.value,
            "Sans Suite": cls.closed.value,
            "Clos": cls.closed.value,
            "clôture provisoire": cls.closed.value,
            "gestion": cls.open.value,
        }


@unique
class ResponsibilityTypes(Enum):
    zero = "ZERO"
    fifty = "FIFTY"
    hundred = "HUNDRED"
    not_specified = "NOT_SPECIFIED"

    @classmethod
    def mapping(cls):
        return {
            "0": cls.zero.value,
            "0%": cls.zero.value,
            "50%": cls.fifty.value,
            "100%": cls.hundred.value,
            "Non renseigné": cls.not_specified.value,
            "0 %": cls.zero.value,
            "100 %": cls.hundred.value,
            "50": cls.fifty.value,
            "100": cls.hundred.value,
            "100.00%": cls.hundred.value,
            "50.00%": cls.fifty.value,
            "0.00%": cls.zero.value,
            "100.0": cls.hundred.value,
            "50.0": cls.fifty.value,
            "999.0": cls.not_specified.value,
            "0.0": cls.zero.value,
            "1.0": cls.hundred.value,
            "0.5": cls.fifty.value,
            "partiel": cls.fifty.value,
            "aucune": cls.zero.value,
            "1": cls.hundred.value,
        }


@unique
class RentalCarSegments(Enum):
    mini = "MINI"
    mini_elite = "MINI_ELITE"
    compact = "COMPACT"
    compact_elite = "COMPACT_ELITE"
    economic = "ECONOMIC"
    intermediary = "INTERMEDIARY"
    intermediary_elite = "INTERMEDIARY_ELITE"
    sedan = "SEDAN"

    @classmethod
    def mapping(cls):
        return {
            "Mini": cls.mini.value,
            "Compacte": cls.compact.value,
            "Compacte Elite": cls.compact_elite.value,
            "Intermédiaire": cls.intermediary.value,
            "Intermédiaire Elite": cls.intermediary_elite.value,
            "Economique": cls.economic.value,
            "Grande routière": cls.sedan.value,
            "Mini Elite": cls.mini_elite.value,
        }


@unique
class TravelTypes(Enum):
    air = "AIR"
    rail = "RAIL"
    rental_car = "RENTAL_CAR"
    fees = "FEES"
    hotels = "HOTELS"
    insurance = "INSURANCE"

    @classmethod
    def mapping(cls):
        return {
            "Aérien": cls.air.value,
            "Train": cls.rail.value,
            "Voiture": cls.rental_car.value,
            "Frais": cls.fees.value,
            "Hôtel": cls.hotels.value,
            "ASSURANCE": cls.insurance.value,
        }


@unique
class TicketTypes(Enum):
    one_way = "ONE_WAY"
    return_trip = "RETURN_TRIP"
    circular = "CIRCULAR"
    open_jaw = "OPEN_JAW"
    unknown = "UNKNOWN"

    @classmethod
    def mapping(cls):
        return {
            "Aller simple": cls.one_way.value,
            "Aller-retour": cls.return_trip.value,
            "Circulaire": cls.circular.value,
            "Open jaw": cls.open_jaw.value,
        }


@unique
class CabinClassTypes(Enum):
    economic = "ECONOMIC"
    second = "SECOND"
    business = "BUSINESS"
    first = "FIRST"
    premier = "PREMIER"
    premium = "PREMIUM"

    @classmethod
    def mapping(cls):
        return {
            "Economique": cls.economic.value,
            "Seconde": cls.second.value,
            "Première": cls.premier.value,
            "Business": cls.business.value,
            "First": cls.first.value,
            "Premium": cls.premium.value,
        }


@unique
class FiscalType(Enum):
    personal_car = "PERSONAL_CAR"
    utility_car = "UTILITY_CAR"
    other = "OTHER"
    two_wheel = "TWO_WHEEL"

    @classmethod
    def mapping(cls):
        return {
            "Véhicule particulier": cls.personal_car.value,
            "Véhicule utilitaire / société": cls.utility_car.value,
            "VP": cls.personal_car.value,
            "VUL": cls.utility_car.value,
            "vp": cls.personal_car.value,
            "ctte_vp": cls.personal_car.value,
            "VASP": cls.utility_car.value,
            "Véhicule spécialisé": cls.other.value,
            "VU": cls.utility_car.value,
            "VP Standard": cls.personal_car.value,
            "VU Standard": cls.utility_car.value,
            "VU taxe à l'essieu": cls.utility_car.value,
            "Véhicule industriel": cls.other.value,
            "Véhicule utilitaire": cls.utility_car.value,
            "AMBULANCE": cls.other.value,
            "BICYCLE": cls.other.value,
            "BUS": cls.other.value,
            "BUS_DOUBLE_DECK": cls.other.value,
            "CAR": cls.personal_car.value,
            "CAR_ESTATE": cls.personal_car.value,
            "CAR_SPORTS": cls.personal_car.value,
            "DIGGER": cls.other.value,
            "DIGGER_2": cls.other.value,
            "GRITTER": cls.other.value,
            "HGV": cls.other.value,
            "HORSEBOX": cls.other.value,
            "MAN": cls.other.value,
            "MINIBUS": cls.other.value,
            "MIXER": cls.other.value,
            "RIGID": cls.other.value,
            "SWEEPER_LARGE": cls.other.value,
            "SWEEPER_SMALL": cls.other.value,
            "TIPPER": cls.other.value,
            "TIPPER_2": cls.other.value,
            "TRACTOR": cls.other.value,
            "TRACTOR_TRAILER": cls.other.value,
            "TRAILER": cls.other.value,
            "VAN": None,
            "VAN_BOX": None,
            "VAN_SMALL": None,
            "WASTE_VEHICLE": cls.other.value,
            "CHERRY_PICKER_HGV": cls.other.value,
            "CHERRY_PICKER_LCV": cls.other.value,
            "VAN_LCV": cls.utility_car.value,
            "POOL_CAR": cls.other.value,
            "HEAVY_VAN_HGV": cls.other.value,
            "TIPPER_MEDIUM": cls.other.value,
            "02-VEHICULE UTILITAIRE/COMMERCIAL": cls.utility_car.value,
            "01-POIDS LOURD": cls.other.value,
            "03-VEHICULE DE TOURISME": cls.personal_car.value,
            "04-AUTRES": cls.other.value,
            "UTILITAIRE": cls.utility_car.value,
            "CTTE": cls.utility_car.value,
            "vlp": cls.personal_car.value,
            "vlu": cls.utility_car.value,
            "VT": cls.personal_car.value,
            "vp (véhicule particulier)": cls.personal_car.value,
            "camionnette": cls.utility_car.value,
            "vu (véhicule utilitaire)": cls.utility_car.value,
            "03, vp": cls.personal_car.value,
            "03. vp": cls.personal_car.value,
            "02. ctte (deriv vp)": cls.utility_car.value,
            "02. ctte (fourgon)": cls.utility_car.value,
            "fonction": cls.personal_car.value,
            "no": None,
            "tourisme": cls.personal_car.value,
            "traxter": cls.other.value,
            "scooter": cls.two_wheel.value,
            "vl": cls.personal_car.value,
            "4x4": None,
            "?": None,
            "service": None,
            "vs": None,
        }


@unique
class RegistrationType(UpperStrEnum):
    vp = "VP"
    ctte = "CTTE"
    vasp = "VASP"
    cam = "CAM"
    mtl = "MTL"
    mtt1 = "MTT1"
    mtt2 = "MTT2"
    cl = "CL"
    qm = "QM"
    tra = "TRA"
    maga = "MAGA"
    tm = "TM"
    cycl = "CYCL"
    tcp = "TCP"
    trr = "TRR"
    rem = "REM"
    srem = "SREM"
    resp = "RESP"
    miar = "MIAR"
    rea = "REA"
    srat = "SRAT"
    srea = "SREA"

    @classmethod
    def mapping(cls):
        return {
            "BERLINE VU": cls.vasp.value,
            "berline hayon": cls.vasp.value,
            "fourgon tole": cls.ctte.value,
            "fourgonnette": cls.ctte.value,
            "suv vp": cls.vp.value,
            "break": cls.vp.value,
            "berline": cls.vp.value,
            "tout-terrain": cls.vp.value,
            "monospace": cls.vp.value,
            "REM": cls.rem.value,
            "vtsu": cls.vasp.value,  # VASP previously VTSU or VTST
            "ctte (vp)": cls.ctte.value,
        }


@unique
class InKindBenefitType(Enum):
    recurring = "RECURRING"
    adjustment = "ADJUSTMENT"
    participation = "PARTICIPATION"

    @classmethod
    def mapping(cls):
        return {
            "Récurrent": cls.recurring.value,
            "Régularisation": cls.adjustment.value,
            "Régule avantage en nature voiture": cls.adjustment.value,
            "Annul. Avantage en nature voiture": cls.adjustment.value,
            "Avantage en nature véhicule": cls.recurring.value,
            "Véhicule de fonction - Participation Loyer": cls.participation.value,
            "aen": cls.recurring.value,
        }


@unique
class VehicleStatus(Enum):
    active = "ACTIVE"
    closed = "CLOSED"
    awaiting = "AWAITING"
    cancelled = "CANCELLED"
    unavailable = "UNAVAILABLE"

    @classmethod
    def mapping(cls):
        return {
            "A la route": cls.active.value,
            "Clos": cls.closed.value,
            "Sorti de parc": cls.closed.value,
            "En attente de livraison": cls.awaiting.value,
            "Annulé": cls.cancelled.value,
            "Annulée": cls.cancelled.value,
            "En parc": cls.active.value,
            "IN_CIRCULATION": cls.active.value,
            "SOLD": cls.closed.value,
            "Vehicle On Order": cls.awaiting.value,
            "Live": cls.active.value,
            "Terminé": cls.closed.value,
            "5-Véhicule à la Route": cls.active.value,
            "En cours de vente": cls.unavailable.value,
            "Indisponible": cls.unavailable.value,
            "En maintenance": cls.unavailable.value,
            "affecté": cls.active.value,
            "disponible": cls.active.value,
            'en service': cls.active.value,
        }


@unique
class EnergyTypes(Enum):
    gaz = "GAZ"
    diesel = "DIESEL"
    gaz_hybrid_no_recharge = "GAZ_HYBRID_NO_RECHARGE"
    gaz_hybrid_recharge = "GAZ_HYBRID_RECHARGE"
    electric = "ELECTRIC"
    diesel_hybrid_no_recharge = "DIESEL_HYBRID_NO_RECHARGE"
    diesel_hybrid_recharge = "DIESEL_HYBRID_RECHARGE"
    gnc = "COMPRESSED_GAZ"
    methane = "METHANE"  # GNV is methane
    bioethanol = "BIOETHANOL"
    gaz_lpg = "GAZ_LPG"  # GPL and essence
    flex_fuel = "FLEX_FUEL"  # E85 and essence
    lpg = "LPG"  # GPL
    hydrogen = "HYDROGEN"
    biodiesel = "BIODIESEL"

    @classmethod
    def mapping(cls):
        gaz_no_recharge = "Hybride essence-électricité non rechargeable (EH)"
        diez_no_recharge = "Gazole-électricité (hybride non rechargeable) [GH]"
        gaz_recharge = "Hybride Essence-électricité rechargeable (EE)"
        return {
            "Essence (ES)": cls.gaz.value,
            "Diesel (GO)": cls.diesel.value,
            gaz_no_recharge: cls.gaz_hybrid_no_recharge.value,
            gaz_recharge: cls.gaz_hybrid_recharge.value,
            diez_no_recharge: cls.diesel_hybrid_no_recharge.value,
            'Électricité (EL)': cls.electric.value,
            'Diesel': cls.diesel.value,
            'Essence': cls.gaz.value,
            'GO': cls.diesel.value,
            'ES': cls.gaz.value,
            'EE': cls.gaz_hybrid_recharge.value,
            'EH': cls.gaz_hybrid_no_recharge.value,
            'EL': cls.electric.value,
            'Mild Essence': cls.gaz_hybrid_no_recharge.value,  # SEAT
            'diesel': cls.diesel.value,
            'sans plomb 95': cls.gaz.value,
            'sans plomb 95\nélectrique': cls.gaz_hybrid_recharge.value,
            'Electrique': cls.electric.value,
            'Hybride essence rechargeable': cls.gaz_hybrid_recharge.value,
            'Hybride essence': cls.gaz_hybrid_no_recharge.value,
            'E85': cls.gaz.value,
            'GNV': cls.methane.value,
            'électrique': cls.electric.value,
            'GAZOLE': cls.diesel.value,
            'Electricité': cls.electric.value,
            'Gazole-électricité [hybride non rechargeable] (GH)': cls.diesel_hybrid_no_recharge.value,
            'ELEC - -': cls.electric.value,
            'ESS ELEC Rechargeable': cls.gaz_hybrid_recharge.value,
            'ESS ELEC Non Recharge': cls.gaz_hybrid_no_recharge.value,
            'E85 ESS Non Recharge': cls.gaz_hybrid_no_recharge.value,
            'Gazoil': cls.diesel.value,
            'Gazole': cls.diesel.value,
            'gasoil': cls.diesel.value,
            'indéfini': None,
            'es (essence)': cls.gaz.value,
            'autre': None,
            'eh (elect.-ess. nr)': cls.gaz_hybrid_no_recharge.value,
            'go (gazole)': cls.diesel.value,
            'el (electricité)': cls.electric.value,
            'ssplomb': cls.gaz.value,
            'full hybride': None,
            'hybrid diesel': None,
            'hybride mild essence': cls.gaz_hybrid_no_recharge.value,
            'ze': None,
            'hy/98': None,
            'non connu': None,
            'hybrid': None,
            'hybride rechargeable': None,
            'micro- hybride': None,
            'es/el': cls.gaz_hybrid_recharge.value,
            'hybride': None,
            'hybride non rechargeable': None,
            'hyb': None,
            'sp98': cls.gaz.value,
            'elec': cls.electric.value,
            'gnr': cls.diesel.value,
            'xtl': cls.biodiesel.value,
            'hybride plug essence': cls.gaz_hybrid_recharge.value,
            'gazole-électricité (hybride non rechargeable)': cls.diesel_hybrid_no_recharge.value,
            'essence-électricité (hybride non rechargeable)': cls.gaz_hybrid_no_recharge.value,
            'inconnue': None,
            'ess+elec hr': cls.gaz_hybrid_recharge.value,
            'essence électricité (hybride non rechargeable)': cls.gaz_hybrid_no_recharge.value,
            'thermique': None,
            'essence hybride': None,
            'fioul': None,  # TODO: add type
            'lpg(gaz)': cls.gaz_lpg.value,
            'hvo': cls.biodiesel.value,
            'tous carburants': None,
            'mhev': None,
            'hev': None,
            'phev': None,
        }


@unique
class RoomTypes(Enum):
    single = "SINGLE"
    double = "DOUBLE"
    triple = "TRIPLE"
    twin = "TWIN"
    quadruple = "QUADRUPLE"
    unknown = ""

    @classmethod
    def mapping(cls):
        return {
            "SGL": cls.single.value,
            "single": cls.single.value,
            "Single": cls.single.value,
            "CHAMBRE SINGLE": cls.single.value,
            "Simple": cls.single.value,
            "TWN": cls.twin.value,
            "Twin": cls.twin.value,
            "DBL": cls.double.value,
            "Chambre double": cls.double.value,
            "Double": cls.double.value,
            "TPL": cls.triple.value,
            "QDR": cls.quadruple.value,
            "1ROH": cls.unknown.value,
            "2roh": cls.unknown.value,
        }


@unique
class ExpenseStatus(Enum):
    approved = "APPROVED"
    denied = "DENIED"
    pending = "PENDING"

    @classmethod
    def mapping(cls):
        return {
            "Approuvée": cls.approved.value,
            "Refusée": cls.denied.value,
            "En attente": cls.pending.value,
        }


@unique
class ExpenseType(Enum):
    parking = "PARKING"
    fuel = "FUEL"
    repairs = "REPAIRS"
    maintenance = "MAINTENANCE"
    taxi = "TAXI"
    public_transportation = "PUBLIC_TRANSPORTATION"
    train = "TRAIN"
    plane = "PLANE"
    mileage_allowance = "PERSONAL_CAR"
    car_rental = "CAR_RENTAL"
    tolls = "TOLLS"
    hotel = "HOTEL"
    light_transportation_rental = "LIGHT_TRANSPORTATION_RENTAL"
    it = "IT"
    food = "FOOD"
    other = "OTHER"
    office_supplies = "OFFICE_SUPPLIES"
    phone = "PHONE"
    trade_show = "TRADE_SHOW"
    unknown = "UNKNOWN"

    @classmethod
    def mapping(cls):
        return {
            "Avion": cls.plane.value,
            "Entretien/réparations véhicule": cls.maintenance.value,
            "Essence": cls.fuel.value,
            "Kilométrage du véhicule personnel": cls.mileage_allowance.value,
            "Location de voiture": cls.car_rental.value,
            "Péages": cls.tolls.value,
            "Taxi": cls.taxi.value,
            "Train": cls.taxi.value,
            "Transports publics": cls.public_transportation.value,
            "Stationnement": cls.parking.value,
            "METRO BUS": cls.public_transportation.value,
            "LAVAGE VEHICULE": cls.maintenance.value,
            "AVION": cls.plane.value,
            "CARBURANT": cls.fuel.value,
            "HOTEL": cls.hotel.value,
            "LOCATION VEHICULE": cls.car_rental.value,
            "INDEMN KM 0.42 €": cls.mileage_allowance.value,
            "PEAGE": cls.tolls.value,
            "LOCATION TROTINETTE/VELO": cls.light_transportation_rental.value,
            "ENTRETIEN (VEH.SOCIETE)": cls.maintenance.value,
            "PARKING": cls.parking.value,
            "TRAIN": cls.train.value,
            "TAXI": cls.taxi.value,
            "INDEMN KM": cls.mileage_allowance.value,
            "MOBILE ET EQUIPEMENT": cls.it.value,
            "Location Habitation": cls.hotel.value,
            "Petit-déjeuner en déplacement": cls.food.value,
            "Déjeuner collaborateurs": cls.food.value,
            "Petit-déjeuner clients": cls.food.value,
            "Frais de Repas": cls.food.value,
            "Journaux/Magazines/Livres": cls.other.value,
            "Hôtel": cls.hotel.value,
            "Divers": cls.other.value,
            "Taxe hôtelière": cls.hotel.value,
            "Boissons Alcoolisées (20%)": cls.food.value,
            "Matériel/équipement de bureau": cls.it.value,
            "Déjeuner en déplacement": cls.food.value,
            "Minibar": cls.food.value,
            "Cadeaux - personnel": cls.other.value,
            "Impression/Photocopie/Fournitures": cls.office_supplies.value,
            "Déjeuner clients": cls.food.value,
            "Fournitures de bureau/Logiciels": cls.it.value,
            "Petit-Déjeuner collaborateurs": cls.food.value,
            "Dîner en déplacement": cls.food.value,
            "Dîner collaborateurs": cls.food.value,
            "Dîner clients": cls.food.value,
            "Repas à emporter": cls.food.value,
            "Téléphone cellulaire": cls.phone.value,
            "Courrier/Expédition/Fret": cls.other.value,
            "Salons professionnels": cls.trade_show.value,
            "non défini": cls.unknown.value,
            "apéritif": cls.food.value,
            "ik_urssaf": cls.mileage_allowance.value,
        }


@unique
class TravelServiceTypes(Enum):
    rental_car = "RENTAL_CAR"
    insurance = "INSURANCE"
    business_insurance = "BUSINESS_INSURANCE"
    luggage = "LUGGAGE"
    air_ticket = "AIR_TICKET"
    rail_card = "RAIL_CARD"
    low_cost_fees = "LOW_COST_FEES"
    train_ticket = "TRAIN_TICKET"
    hotels = "HOTELS"
    low_cost_ticket = "LOW_COST_TICKET"
    low_cost_card = "LOW_COST_CARD"
    airline_penalty = "AIRLINE_PENALTY"
    air_fee_europe = "AIR_FEE_EUROPE"
    air_fee_world = "AIR_FEE_WORLD"
    air_fee_national = "AIR_FEE_NATIONAL"
    train_fee = "TRAIN_FEE"
    hotel_fee = "HOTEL_FEE"
    rental_car_fee = "RENTAL_CAR_FEE"
    low_cost_fee_world = "LOW_COST_FEE_WORLD"
    low_cost_fee_national = "LOW_COST_FEE_NATIONAL"
    voucher_fee = "VOUCHER_FEE"
    out_of_hours_fee = "OUT_OF_HOURS_FEE"
    admin_fee = "ADMIN_FEE"

    @classmethod
    def mapping(cls):
        presta = "Prestations de service "
        return {
            "Location de voiture": cls.rental_car.value,
            "Assurance": cls.insurance.value,
            "Assurance affaires": cls.business_insurance.value,
            "Bagage": cls.luggage.value,
            "billet aérien": cls.air_ticket.value,
            "Ecard ferroviaire": cls.rail_card.value,
            "EMD LOWCOST": cls.low_cost_fees.value,
            "Ferroviaire": cls.train_ticket.value,
            "Hôtel": cls.hotels.value,
            "LOW COST": cls.low_cost_ticket.value,
            "LOW COST ECARD": cls.low_cost_card.value,
            "Pénalité compagnie": cls.airline_penalty.value,
            presta + "air europe": cls.air_fee_europe.value,
            presta + "air international": cls.air_fee_world.value,
            presta + "air national": cls.air_fee_national.value,
            presta + "ferroviaire": cls.train_fee.value,
            presta + "hôtel": cls.hotel_fee.value,
            presta + "location de voiture": cls.rental_car_fee.value,
            presta + "low cost international": cls.low_cost_fee_world.value,
            presta + "low cost national": cls.low_cost_fee_national.value,
            presta + "sur avoir": cls.voucher_fee.value,
            "Réservation Hôtel": cls.hotels.value,
            "Frais H24": cls.out_of_hours_fee.value,
            "modification de billet": cls.admin_fee.value,
            "regularisation agence": cls.admin_fee.value,
        }


@unique
class AssignmentType(Enum):
    company_vehicle = "COMPANY_CAR"
    service_vehicle = "SERVICE_VEHICLE"

    @classmethod
    def mapping(cls):
        return {
            "VEHICULE_FONCTION_SERVICE": cls.service_vehicle.value,
            "VEHICULE_FONCTION": cls.company_vehicle.value,
            "VEHICULE_SERVICE": cls.service_vehicle.value,
            "Véhicule entreprise": cls.company_vehicle.value,
            "vehicule_immobilise": None,
            "non renseigné": None,
            "véhicule de fonction": cls.company_vehicle.value,
            "véhicule de service": cls.service_vehicle.value,
            "fonction": cls.company_vehicle.value,
            "service": cls.service_vehicle.value,
        }


@unique
class BillType(Enum):
    debit = "DEBIT"
    credit = "CREDIT"

    @classmethod
    def mapping(cls):
        return {
            "FACTURE": cls.debit.value,
            "AVOIR": cls.credit.value,
        }


@unique
class MileageSourceType(Enum):
    collaborator = "COLLABORATOR"
    provider = "PROVIDER"

    @classmethod
    def mapping(cls):
        return {
            "COLLABORATEUR": cls.collaborator.value,
            "FOURNISSEUR": cls.provider.value,
        }


@unique
class ModelCategories(Enum):
    city = "CITY"
    sedan = "SEDAN"
    suv = "SUV"
    utility = "UTILITY"
    two_wheel = "TWO_WHEEL"
    van = "VAN"
    compact = "COMPACT"
    truck = "TRUCK"
    no_license = "NO_LICENSE"
    unknown = "UNKNOWN"

    @classmethod
    def mapping(cls):
        """Mapping from car models to ModelCategories
        Antipattern - we don't map model_categories directly to model categories.
        """
        return {
            Models.stelvio.value: cls.sedan.value,
            Models.a4.value: cls.sedan.value,
            Models.a5.value: cls.sedan.value,
            Models.a6.value: cls.sedan.value,
            Models.a1.value: cls.city.value,
            Models.a3.value: cls.compact.value,
            Models.q2.value: cls.suv.value,
            Models.q3.value: cls.suv.value,
            Models.q5.value: cls.suv.value,
            Models.serie3.value: cls.sedan.value,
            Models.series5.value: cls.sedan.value,
            Models.two20.value: cls.sedan.value,
            Models.three30.value: cls.sedan.value,
            Models.three20.value: cls.sedan.value,
            Models.three16.value: cls.sedan.value,
            Models.serie1.value: cls.compact.value,
            Models.serie2.value: cls.compact.value,
            Models.one18.value: cls.compact.value,
            Models.x1.value: cls.suv.value,
            Models.x3.value: cls.suv.value,
            Models.x5.value: cls.suv.value,
            Models.c4.value: cls.sedan.value,
            Models.c5.value: cls.sedan.value,
            Models.picasso.value: cls.sedan.value,
            Models.c1.value: cls.city.value,
            Models.c3.value: cls.city.value,
            Models.cactus.value: cls.compact.value,
            Models.spacetourer.value: cls.van.value,
            Models.jumpy.value: cls.utility.value,
            Models.jumper.value: cls.utility.value,
            Models.berlingo.value: cls.utility.value,
            Models.ds7.value: cls.suv.value,
            Models.fivehundred.value: cls.city.value,
            Models.tipo.value: cls.compact.value,
            Models.doblo.value: cls.utility.value,
            Models.ducato.value: cls.utility.value,
            Models.talento.value: cls.utility.value,
            Models.scudo.value: cls.utility.value,
            Models.galaxy.value: cls.sedan.value,
            Models.smax.value: cls.sedan.value,
            Models.fiesta.value: cls.city.value,
            Models.focus.value: cls.compact.value,
            Models.kuga.value: cls.suv.value,
            Models.ecosport.value: cls.suv.value,
            Models.transit.value: cls.utility.value,
            Models.i30.value: cls.compact.value,
            Models.ioniq.value: cls.compact.value,
            Models.tucson.value: cls.suv.value,
            Models.daily.value: cls.utility.value,
            Models.xe.value: cls.sedan.value,
            Models.fpace.value: cls.suv.value,
            Models.renegade.value: cls.suv.value,
            Models.picanto.value: cls.city.value,
            Models.rio.value: cls.city.value,
            Models.ceed.value: cls.compact.value,
            Models.xceed.value: cls.sedan.value,
            Models.stonic.value: cls.city.value,
            Models.niro.value: cls.city.value,
            Models.sportage.value: cls.suv.value,
            Models.ev6.value: cls.suv.value,
            Models.ct.value: cls.compact.value,
            Models.i_s.value: cls.sedan.value,
            Models.ux.value: cls.suv.value,
            Models.nx.value: cls.suv.value,
            Models.tgm.value: cls.utility.value,
            Models.tge.value: cls.utility.value,
            Models.classC.value: cls.sedan.value,
            Models.cla.value: cls.sedan.value,
            Models.classA.value: cls.compact.value,
            Models.gla.value: cls.suv.value,
            Models.glc.value: cls.suv.value,
            Models.gbl.value: cls.suv.value,
            Models.eqc.value: cls.suv.value,
            Models.eqb.value: cls.suv.value,
            Models.sprinter.value: cls.utility.value,
            Models.vito.value: cls.utility.value,
            Models.mg4.value: cls.compact.value,
            Models.cooper.value: cls.city.value,
            Models.countryman.value: cls.city.value,
            Models.clubman.value: cls.city.value,
            Models.canter.value: cls.truck.value,
            Models.micra.value: cls.city.value,
            Models.juke.value: cls.suv.value,
            Models.qashqai.value: cls.suv.value,
            Models.nv200.value: cls.utility.value,
            Models.nv300.value: cls.utility.value,
            Models.nv400.value: cls.utility.value,
            Models.nt400.value: cls.truck.value,
            Models.primastar.value: cls.utility.value,
            Models.corsa.value: cls.city.value,
            Models.insignia.value: cls.sedan.value,
            Models.grandland.value: cls.suv.value,
            Models.zafira.value: cls.sedan.value,
            Models.vivaro.value: cls.utility.value,
            Models.mokka.value: cls.suv.value,
            Models.citystar.value: cls.two_wheel.value,
            Models.five08.value: cls.sedan.value,
            Models.one08.value: cls.city.value,
            Models.two08.value: cls.city.value,
            Models.three08.value: cls.compact.value,
            Models.five008.value: cls.suv.value,
            Models.two008.value: cls.suv.value,
            Models.three008.value: cls.suv.value,
            Models.boxer.value: cls.utility.value,
            Models.expert.value: cls.utility.value,
            Models.partner.value: cls.utility.value,
            Models.d20.value: cls.two_wheel.value,
            Models.mp3.value: cls.two_wheel.value,
            Models.discovery.value: cls.suv.value,
            Models.evoque.value: cls.suv.value,
            Models.twingo.value: cls.city.value,
            Models.zoe.value: cls.city.value,
            Models.megane.value: cls.compact.value,
            Models.clio.value: cls.city.value,
            Models.captur.value: cls.suv.value,
            Models.talisman.value: cls.sedan.value,
            Models.scenic.value: cls.sedan.value,
            Models.espace.value: cls.suv.value,
            Models.austral.value: cls.sedan.value,
            Models.kangoo.value: cls.utility.value,
            Models.midlum.value: cls.truck.value,
            Models.master.value: cls.utility.value,
            Models.express_van.value: cls.utility.value,
            Models.trafic.value: cls.utility.value,
            Models.mascott.value: cls.truck.value,
            Models.leon.value: cls.compact.value,
            Models.scala.value: cls.compact.value,
            Models.kodiac.value: cls.suv.value,
            Models.octavia.value: cls.sedan.value,
            Models.enyaq.value: cls.suv.value,
            Models.fortwo.value: cls.city.value,
            Models.forfour.value: cls.city.value,
            Models.model_3.value: cls.sedan.value,
            Models.model_y.value: cls.sedan.value,
            Models.aygo.value: cls.city.value,
            Models.yaris.value: cls.city.value,
            Models.yaris_cross.value: cls.compact.value,
            Models.chr.value: cls.sedan.value,
            Models.rav4.value: cls.suv.value,
            Models.corolla.value: cls.compact.value,
            Models.proace.value: cls.utility.value,
            Models.proace_city.value: cls.utility.value,
            Models.dyna.value: cls.truck.value,
            Models.polo.value: cls.city.value,
            Models.up.value: cls.city.value,
            Models.golf.value: cls.compact.value,
            Models.id3.value: cls.compact.value,
            Models.troc.value: cls.suv.value,
            Models.tiguan.value: cls.suv.value,
            Models.id4.value: cls.suv.value,
            Models.idbuzz.value: cls.utility.value,
            Models.caravelle.value: cls.utility.value,
            Models.caddy.value: cls.utility.value,
            Models.crafter.value: cls.utility.value,
            Models.transporter.value: cls.utility.value,
            Models.s90.value: cls.sedan.value,
            Models.v60.value: cls.sedan.value,
            Models.v40.value: cls.sedan.value,
            Models.xc40.value: cls.suv.value,
            Models.xc60.value: cls.suv.value,
            Models.xc90.value: cls.suv.value,
            Models.c40.value: cls.sedan.value,
            Models.fjr1300.value: cls.two_wheel.value,
            Models.xmax.value: cls.two_wheel.value,
            Models.arona.value: cls.suv.value,
            Models.ateca.value: cls.suv.value,
            Models.auris.value: cls.compact.value,
            Models.combo.value: cls.utility.value,
            Models.fabia.value: cls.city.value,
            Models.kona.value: cls.suv.value,
            Models.unknown.value: cls.unknown.value,
            Models.serie4.value: cls.sedan.value,
            Models.serie_d.value: cls.truck.value,
            Models.burgman.value: cls.two_wheel.value,
            Models.f800.value: cls.two_wheel.value,
            Models.fly50.value: cls.two_wheel.value,
            Models.grand_cheerokee.value: cls.suv.value,
            Models.cabstar.value: cls.truck.value,
            Models.two07.value: cls.city.value,
            Models.ranger.value: cls.suv.value,
            Models.enyaq.value: cls.suv.value,
            Models.ds4.value: cls.compact.value,
            Models.r5.value: cls.city.value,
            Models.ex90.value: cls.suv.value,
            Models.karoq.value: cls.suv.value,
            Models.touareg.value: cls.suv.value,
            Models.kadjar.value: cls.compact.value,
            Models.ds5.value: cls.sedan.value,
            Models.ds3.value: cls.city.value,
            Models.q4.value: cls.suv.value,
            Models.xtrail.value: cls.suv.value,
            Models.crv.value: cls.suv.value,
            Models.dauphine.value: cls.city.value,
            Models.sixhundred.value: cls.city.value,
            Models.macan.value: cls.suv.value,
            Models.trade.value: cls.utility.value,
            Models.ludix.value: cls.two_wheel.value,
            Models.proceed.value: cls.sedan.value,
            Models.tweet.value: cls.two_wheel.value,
            Models.classE.value: cls.sedan.value,
            Models.zip.value: cls.no_license.value,
            Models.cx60.value: cls.suv.value,
            Models.tcross.value: cls.suv.value,
            Models.r4.value: cls.city.value,
            Models.sandero.value: cls.city.value,
            Models.bayon.value: cls.suv.value,
            Models.jogger.value: cls.sedan.value,
            Models.zero1.value: cls.suv.value,
            Models.arkana.value: cls.suv.value,
            Models.symbioz.value: cls.suv.value,
            Models.puma.value: cls.suv.value,
            Models.passat.value: cls.sedan.value,
            Models.one90S42.value: cls.truck.value,
            Models.tourneo.value: cls.utility.value,
            Models.mustang.value: cls.suv.value,
            Models.duster.value: cls.suv.value,
            Models.multicharger.value: cls.two_wheel.value,
            Models.runner.value: cls.two_wheel.value,
            Models.two_chevaux.value: cls.city.value,
            Models.arteon.value: cls.sedan.value,
            Models.atto.value: cls.suv.value,
            Models.mgs5.value: cls.suv.value,
            Models.nemo.value: cls.utility.value,
            Models.lf45.value: cls.truck.value,
            Models.xp560.value: cls.two_wheel.value,
            Models.touran.value: cls.sedan.value,
            Models.xsara.value: cls.compact.value,
            Models.four06.value: cls.sedan.value,
            Models.jazz.value: cls.city.value,
            Models.avenger.value: cls.suv.value,
            Models.astra.value: cls.compact.value,
            Models.gsx800.value: cls.two_wheel.value,
            Models.fazer.value: cls.two_wheel.value,
            Models.agila.value: cls.city.value,
            Models.one90s31.value: cls.truck.value,
            Models.formentor.value: cls.suv.value,
            Models.cux.value: cls.two_wheel.value,
            Models.xj600.value: cls.two_wheel.value,
            Models.v50.value: cls.sedan.value,
            Models.proace_max.value: cls.utility.value,
            Models.viano.value: cls.utility.value,
            Models.seven50.value: cls.sedan.value,
            Models.ar50.value: cls.two_wheel.value,
            Models.x_adv.value: cls.two_wheel.value,
            Models.x2.value: cls.suv.value,
            Models.rafale.value: cls.suv.value,
            Models.santa_fe.value: cls.suv.value,
            Models.id5.value: cls.suv.value,
            Models.vitara.value: cls.suv.value,
            Models.scross.value: cls.suv.value,
            Models.jimny.value: cls.suv.value,
            Models.sportsman.value: cls.unknown.value,
            Models.d_max.value: cls.utility.value,
            Models.hilux.value: cls.utility.value,
            Models.petit_forestier.value: cls.utility.value,
            Models.jimny.value: cls.suv.value,
            Models.townstar.value: cls.utility.value,
            Models.land_cruiser.value: cls.suv.value,
            Models.l200.value: cls.utility.value,
            Models.combi.value: cls.utility.value,
            Models.rifter.value: cls.utility.value,
            Models.hy420.value: cls.unknown.value,
            Models.panda.value: cls.city.value,
            Models.five075e.value: cls.unknown.value,
            Models.cx5.value: cls.suv.value,
            Models.maxxer.value: cls.unknown.value,
            Models.crossland.value: cls.suv.value,
            Models.pajero.value: cls.suv.value,
            Models.kerax.value: cls.truck.value,
            Models.sedici.value: cls.suv.value,
            Models.fiorino.value: cls.utility.value,
            Models.compass.value: cls.suv.value,
            Models.amarok.value: cls.utility.value,
            Models.traveller.value: cls.utility.value,
            Models.mondeo.value: cls.sedan.value,
            Models.outlander.value: cls.utility.value,
            Models.r395t.value: cls.unknown.value,
            Models.ranger_alpine.value: cls.unknown.value,
            Models.arocs.value: cls.truck.value,
            Models.leitwolf.value: cls.unknown.value,
            Models.yeti.value: cls.suv.value,
            Models.space_wagon.value: cls.suv.value,
            Models.multivan.value: cls.utility.value,
            Models.spring.value: cls.city.value,
            Models.g4.value: cls.utility.value,
            Models.xf.value: cls.sedan.value,
            Models.club.value: cls.utility.value,
            Models.cargo500.value: cls.utility.value,
        }


@unique
class Models(UpperStrEnum):
    # Peugeot
    one08 = "108"
    five008 = "5008"
    two07 = "207"
    two08 = "208"
    two008 = "2008"
    three08 = "308"
    three008 = "3008"
    four06 = "406"
    five08 = "508"
    boxer = "BOXER"
    citystar = "CITYSTAR"
    expert = "EXPERT"
    partner = "PARTNER"
    ludix = "LUDIX"
    tweet = "TWEET"
    rifter = "RIFTER"
    traveller = "TRAVELLER"

    # Mercedes
    classA = "CLASSE A"
    classC = "CLASSE C"
    classE = "CLASSE E"
    classSL = "CLASSE SL"
    gla = "GLA"
    cla = "CLA"
    glc = "GLC"
    gbl = "GLB"
    sprinter = "SPRINTER"
    vito = "VITO"
    eqc = "EQC"
    eqb = "EQB"
    viano = "VIANO"
    arocs = "AROCS"

    # Porsche
    macan = "MACAN"

    # Mini
    cooper = "COOPER"
    countryman = "COUNTRYMAN"
    clubman = "CLUBMAN"

    # Swappa
    zip = "ZIP"

    # Audi
    a1 = "A1"
    a3 = "A3"
    a4 = "A4"
    a5 = "A5"
    a6 = "A6"
    q2 = "Q2"
    q3 = "Q3"
    q4 = "Q4"
    q5 = "Q5"

    # Bombardier Recreative / Lynx
    ranger_alpine = "RANGER ALPINE"

    # BMW
    f800 = "F800"
    x1 = "X1"
    x2 = "X2"
    x3 = "X3"
    x5 = "X5"
    serie1 = "SERIE 1"
    serie2 = "SERIE 2"
    serie3 = "SERIE 3"
    serie4 = "SERIE 4"
    series5 = "SERIE 5"
    one18 = "118"
    two20 = "220"
    three30 = "330"
    three20 = "320"
    three16 = "316"
    seven50 = "750"

    # BYD
    atto = "ATTO"

    # Can-am
    outlander = "OUTLANDER"

    # Club car
    club = "CLUB"

    # Citroen
    c1 = "C1"
    c3 = "C3"
    cactus = "CACTUS"
    spacetourer = "SPACETOURER"
    c4 = "C4"
    c5 = "C5"
    picasso = "PICASSO"
    jumpy = "JUMPY"
    jumper = "JUMPER"
    berlingo = "BERLINGO"
    nemo = "NEMO"
    xsara = "XSARA"

    # CUPRA
    formentor = "FORMENTOR"

    # DACIA
    duster = "DUSTER"
    sandero = "SANDERO"
    jogger = "JOGGER"
    spring = "SPRING"

    # DAF
    lf45 = "LF45"

    # DS
    ds3 = "DS3"
    ds4 = "DS4"
    ds5 = "DS5"
    ds7 = "DS7"

    # Ford
    galaxy = "GALAXY"
    kuga = "KUGA"
    ecosport = "ECOSPORT"
    focus = "FOCUS"
    smax = "S-MAX"
    fiesta = "FIESTA"
    transit = "TRANSIT"
    ranger = "RANGER"
    puma = "PUMA"
    tourneo = "TOURNEO"
    mustang = "MUSTANG"
    mondeo = "MONDEO"

    # FIAT
    doblo = "DOBLO"
    tipo = "TIPO"
    fivehundred = "500"
    ducato = "DUCATO"
    talento = "TALENTO"
    scudo = "SCUDO"
    sixhundred = "600"
    panda = "PANDA"
    sedici = "SEDICI"
    fiorino = "FIORINO"

    # Goupil
    g4 = 'G4'

    # LEXUS
    i_s = "IS"
    ux = "UX"
    ct = "CT"
    nx = "NX"

    # Lynk and CO
    zero1 = "01"

    # Opel
    combo = "COMBO"
    insignia = "INSIGNIA"
    corsa = "CORSA"
    grandland = "GRANDLAND"
    zafira = "ZAFIRA"
    vivaro = "VIVARO"
    mokka = "MOKKA"
    astra = "ASTRA"
    agila = "AGILA"
    crossland = "CROSSLAND"

    # MAN
    tgm = "TGM"
    tge = "TGE"

    # MAZDA
    cx60 = "CX-60"
    cx5 = "CX-5"

    # Move eco
    cargo500 = "CARGO 500"

    # Nissan
    xtrail = "X-TRAIL"
    juke = "JUKE"
    qashqai = "QASHQAI"
    micra = "MICRA"
    nv200 = "NV200"
    nv300 = "NV300"
    nv400 = "NV400"
    nt400 = "NT400"
    primastar = "PRIMASTAR"
    cabstar = "CABSTAR"
    trade = "TRADE"
    townstar = "TOWNSTAR"

    # Prynoth
    leitwolf = "LEITWOLF"

    # Renault
    twingo = "TWINGO"
    clio = "CLIO"
    captur = "CAPTUR"
    megane = "MEGANE"
    talisman = "TALISMAN"
    scenic = "SCENIC"
    espace = "ESPACE"
    austral = "AUSTRAL"
    zoe = "ZOE"
    kangoo = "KANGOO"
    midlum = "MIDLUM"
    master = "MASTER"
    express_van = "EXPRESS VAN"
    trafic = "TRAFIC"
    mascott = "MASCOTT"
    r4 = "R4"
    r5 = "R5"
    kadjar = "KADJAR"
    dauphine = "DAUPHINE"
    arkana = "ARKANA"
    symbioz = "SYMBIOZ"
    two_chevaux = "2 CV"
    rafale = "RAFALE"

    # Renault Trucks
    serie_d = "SERIE D"
    kerax = "KERAX"

    # Volkswagen
    passat = "PASSAT"
    polo = "POLO"
    golf = "GOLF"
    tiguan = "TIGUAN"
    troc = "T-ROC"
    tcross = "T-CROSS"
    up = "UP"
    id3 = "ID 3"
    id4 = "ID 4"
    id5 = "ID 5"
    idbuzz = "ID BUZZ"
    caravelle = "CARAVELLE"
    caddy = "CADDY"
    crafter = "CRAFTER"
    transporter = "TRANSPORTER (T6)"
    touareg = "TOUAREG"
    arteon = "ARTEON"
    touran = "TOURAN"
    combi = "COMBI"
    amarok = "AMAROK"
    multivan = "MULTIVAN"

    # Skoda
    fabia = "FABIA"
    scala = 'SCALA'
    kodiac = 'KODIAQ'
    octavia = 'OCTAVIA'
    enyaq = 'ENYAQ'
    karoq = 'KAROQ'
    elroq = 'ELROQ'
    yeti = "YETI"

    # SMART
    fortwo = "FORTWO"
    forfour = "FORFOUR"

    # SEAT
    leon = "LEON"
    ateca = "ATECA"
    arona = "ARONA"

    # Super Soco
    cux = "CUX"

    # SUZUKI
    burgman = "BURGMAN"
    swift = "SWIFT"
    gsx800 = "GSX 800"
    vitara = "VITARA"
    scross = "S-CROSS"
    jimny = "JIMNY"

    # Tesla
    model_3 = "MODEL 3"
    model_y = "MODEL Y"

    # Toyota
    aygo = "AYGO"
    yaris = "YARIS"
    yaris_cross = "YARIS CROSS"
    chr = "C-HR"
    rav4 = "RAV4"
    corolla = "COROLLA"
    auris = "AURIS"
    proace = "PROACE"
    proace_city = "PROACE CITY"
    proace_max = "PROACE MAX"
    dyna = "DYNA"
    hilux = "HILUX"
    land_cruiser = "LAND CRUISER"

    # Honda
    crv = "CR-V"
    jazz = "JAZZ"
    x_adv = "X-ADV"

    # Hytrack
    hy420 = "hy420"

    # Jaguar
    xe = "XE"
    xf = "XF"
    fpace = "F-PACE"

    # KIA
    proceed = "PROCEED"
    picanto = "PICANTO"
    ceed = "CEED"
    rio = "RIO"
    xceed = "XCEED"
    stonic = "STONIC"
    niro = "NIRO"
    sportage = "SPORTAGE"
    ev6 = "EV6"

    # Volvo
    ex90 = "EX90"
    s90 = "S90"
    v60 = "V60"
    v50 = "V50"
    v40 = "V40"
    xc40 = "XC40"
    xc60 = "XC60"
    xc90 = "XC90"
    c40 = "C40"

    # Land Rover / range rover
    discovery = "DISCOVERY"
    evoque = "EVOQUE"

    # Alfa Romeo
    stelvio = "STELVIO"

    # Kymco
    maxxer = "MAXXER"

    # Lamborghini
    r395t = "R395T"

    # Jeep
    grand_cheerokee = "GRAND_CHEROKEE"
    renegade = "RENEGADE"
    avenger = "AVENGER"
    compass = "COMPASS"

    # John Deere
    five075e = "5075E"

    # MG
    mgs5 = "MGS5"
    mg4 = "MG4"

    # Unknown
    unknown = "UNKNOWN"

    # Yamaha
    fjr1300 = "FJR 1300"
    xmax = "X-MAX"
    xj600 = "XJ 600"
    fazer = "FAZER"

    # Hyundai
    i30 = "I30"
    ioniq = "IONIQ"
    kona = "KONA"
    tucson = "TUCSON"
    bayon = "BAYON"
    santa_fe = "SANTA FE"

    # Piaggio
    fly50 = "FLY_50"
    d20 = "D20"
    mp3 = "MP3"

    # Polaris
    sportsman = "SPORTSMAN"

    # Mitsubishi
    canter = "CANTER"
    pajero = "PAJERO"
    l200 = "L200"
    space_wagon = 'space wagon'

    # Iveco
    daily = "DAILY"
    one90S42 = "190S42"
    one90s31 = "190S31"
    three5s14 = "35S14"
    petit_forestier = "PETIT FORESTIER"

    # Isuzu
    d_max = "D-MAX"

    # Fleximodal
    runner = "RUNNER"

    # En cargo Simone
    multicharger = "MULTICHARGER"

    # Scootterre
    ar50 = "AR50"

    # XP
    xp560 = "XP560"

    @classmethod
    def n_word_multiple_word_models(cls, word_number: int) -> typing.List[str]:
        base_lst = ["ID."] if word_number == 0 else []
        return base_lst + [model.value.split(" ")[word_number] for model in cls if " " in model.value]

    @classmethod
    def mapping(cls):
        return {
            "C3 AIRCROSS": cls.c3.value,
            "C5 AIRCROSS": cls.c5.value,
            "DS 7 CROSSBACK": cls.ds7.value,
            "DS7 CROSSBACK": cls.ds7.value,
            "COOPER S": cls.cooper.value,
            "TIPO": cls.tipo.value,
            "INSIGNIA SPORTS TOURER": cls.insignia.value,
            "X5 XDRIVE45E": cls.x5.value,
            "CUPRA LEON SP E-HYBRID180": cls.leon.value,
            "GLA 250 E": cls.gla.value,
            "A1 SPORTBACK": cls.a1.value,
            "GOLF GTE": cls.golf.value,
            "SEAT ATECA": cls.ateca.value,
            "TOYOTA AYGO": cls.aygo.value,
            "UP": cls.up.value,
            "Q3": cls.q3.value,
            "CLIO": cls.clio.value,
            "SEAT LEON": cls.leon.value,
            "UP!": cls.up.value,
            "C 300 E": cls.classC.value,
            "COUNTRYMAN COOPER SE ALL4": cls.countryman.value,
            "PEUGEOT 5008 1.2 PURETECH 130 S&S GT LINE": cls.five008.value,
            "SKODA FABIA 1.0 TSI 95 DRIVE 125ANS": cls.fabia.value,
            "PEUGEOT 208 1.5 BLUEHDI 100 S&S ALLURE": cls.two08.value,
            "SEAT LEON 2.0 TDI 115 S&S STYLE BUSINESS": cls.leon.value,
            "PEUGEOT 208 1.2 PT 100 S&S AUTO ALLURE": cls.two08.value,
            "MINI COUNTRYMAN 1.5 COOPER SE ALL4 BUSI DESIGN HYBRID A": cls.countryman.value,
            '.': None,
            "SERIE 2 GRAN TOURER": cls.serie2.value,
            "SERIE 3 TOURING": cls.serie3.value,
            "IS 300H": cls.i_s.value,
            "CLA COUPE": cls.cla.value,
            "COROLLA": cls.corolla.value,
            "LEXUS UX250H": cls.ux.value,
            "SERIE 3 BERLINE": cls.serie3.value,
            "SÉRIE 3 BERLINE": cls.serie3.value,
            "C4 CACTUS": cls.cactus.value,
            "CLASSE C BREAK": cls.classC.value,
            "CLA": cls.cla.value,
            "308 SW": cls.three08.value,
            "SERIE 2 ACTIVE TOURER": cls.serie2.value,
            "508 SW": cls.five08.value,
            "GRAND C4 PICASSO": cls.picasso.value,
            "GRAND SCÉNIC": cls.scenic.value,
            "CT 200H": cls.ct.value,
            "DS 7": cls.ds7.value,
            "MINI": cls.cooper.value,
            "KODIAC": cls.kodiac.value,
            "A5": cls.a5.value,
            "GRAND SCENIC": cls.scenic.value,
            "SÉRIE 3 TOURING": cls.serie3.value,
            "CLASSE A COMPACT": cls.classA.value,
            "SÉRIE 1": cls.serie1.value,
            "GRAND C4 SPACETOURER": cls.spacetourer.value,
            "RENEGADE": cls.renegade.value,
            "FIESTA": cls.fiesta.value,
            "C4 SPACETOURER": cls.spacetourer.value,
            "500X": cls.fivehundred.value,
            "OCTAVIA COMBI": cls.octavia.value,
            "Q3 SPORTBACK": cls.q3.value,
            "VOLKSWAGEN POLO": cls.polo.value,
            "VOLKSWAGEN T-ROC": cls.troc.value,
            "X3(3) FL 20IBUSDES4MBAJ19": cls.x3.value,
            "A3(3) FL 5P E150 BUSL BA": cls.a3.value,
            "GLA FL 220D BUSED 2M BA": cls.gla.value,
            "3008(2) FL E130 ACT PK BA": cls.three008.value,
            "DISCOVERY SPT TD150 EXEBA": cls.discovery.value,
            "MEGANE D110 BUSINESS EDC": cls.megane.value,
            "SPORTAGE5 H230 DESG 2M": cls.sportage.value,
            "330E(7) BK BUSDES": cls.three30.value,
            "GLC 250 FASC 4M BA": cls.glc.value,
            "308 D120 ACTIVE BUSINESS": cls.three08.value,
            "*MODEL 3 PERF 4M*BP": cls.model_3.value,
            "tesla modele 3": cls.model_3.value,
            "3008(2) E130 ALLBUSBAGRIP": cls.three008.value,
            "320I(7) BUSDES BA": cls.three20.value,
            "DS7 CRSBK BD130 BUS BA": cls.ds7.value,
            "X1 18D BUSINESS A 2M": cls.x1.value,
            "5008(2) E130 ALLBUS 7PJ19": cls.five008.value,
            "TIGUAN2 E150 CARA 2M BA5P": cls.tiguan.value,
            "5008(2) E130 ALL BUS 7PBA": cls.five008.value,
            "308(2) FL E130 ALL BUS BA": cls.three08.value,
            "508(2) BK E130 ALL PK BA": cls.five08.value,
            "A5 SPORTBACK D190": cls.a5.value,
            "RAV4 D143 DESIGN": cls.rav4.value,
            "X3 20D M SPORT A 4M": cls.x3.value,
            "308(2) FL BK E130ALLBUSBA": cls.three08.value,
            "220D M SPORT A GRAN TOURE": cls.two20.value,
            "TIGUAN2 D150 CFTBUS 2M BA": cls.tiguan.value,
            "A4(4) BK D150U SLIN BA": cls.a4.value,
            "308(2) FL BD120 ALL BUSBA": cls.three08.value,
            "220D SPORT A ACTIVE TOURE": cls.two20.value,
            "5008(2) E130ALLBUS7PBAJ19": cls.five008.value,
            "GRAND D120 BUSINESS + GRA": cls.d20.value,
            "A5 D190 S LINE QUATTRO S": cls.a5.value,
            "308(3) E130 ACT PK BA": cls.three08.value,
            "Q2 D116 SLIN 2M BA": cls.q2.value,
            "316D(6) FL BUSDES BA": cls.three20.value,
            "TIGUAN2 D190 CAREX 4MBA5P": cls.tiguan.value,
            "308 D150 FÉLINE": cls.three08.value,
            "330XI(7) BK LUX BA": cls.three30.value,
            "IS(3) FL 300H PK BUS": cls.i_s.value,
            "3008 D180 GT": cls.three008.value,
            "STELVIO D150 LUS 2M BAJ19": cls.stelvio.value,
            "V40 FL CC D2 [S] OVERSTA": cls.v40.value,
            "RAV4(5) H218 DYN BUS 2M": cls.rav4.value,
            "508(2) E180 ALL BUS BA": cls.five08.value,
            "508 D180 FÉLINE": cls.five08.value,
            "3008 BUSINESS NOUVEAU ALL": cls.three008.value,
            "Q3(2) E150 SLIN 2M BA": cls.q3.value,
            "Q3(2) E150 DESLUX 2M BA": cls.q3.value,
            "118D BUSINESS A": cls.one18.value,
            "SCENIC4 GDE160INITPARBA5P": cls.scenic.value,
            "DS7 CRSBK E180 PERFL BA": cls.ds7.value,
            "DS7 CRSBK BD130 EXE BA": cls.ds7.value,
            "C4 D120 MILLENIUM BUSINES": cls.c4.value,
            "DS7 CRSBK E225 GD CHIC BA": cls.ds7.value,
            "A(4) 180 BUSL BA": cls.a4.value,
            "3008(2) BD180 GTL BA": cls.three008.value,
            "Q2 E150 SPORT": cls.q2.value,
            "Q2 E150 BUSL 2M BA": cls.q2.value,
            "DS7 CRSBK E180 BUS BA": cls.ds7.value,
            "C(4) FL BK 300E BUSL": cls.c4.value,
            "308(2) FLBKE130BCACTBUSBA": cls.three08.value,
            "YARIS3 FL 100H FRANCE BUS": cls.yaris.value,
            "3008 D120 ALLURE BUSINESS": cls.three008.value,
            "208 FL E110 ALL BUS BA": cls.two08.value,
            "GLA2 200 AMGL 2M BA J20": cls.gla.value,
            "2008(2) E130 ACT PK BA": cls.two008.value,
            "308(2) FL BD130 ACTBUS BA": cls.three08.value,
            "MEGANE4 D110E BUS BA": cls.megane.value,
            "MEGANE4 E130E INT BA": cls.megane.value,
            "XC60 D220 SUMMUM GEARTRON": cls.xc60.value,
            "NIRO EV": cls.niro.value,
            "CLA SHOOTING BRAKE": cls.cla.value,
            "ENYAQ": cls.enyaq.value,
            "CLASSE C BERLINE": cls.classC.value,
            "DIVERS VI": cls.unknown.value,
            "KANGOO EXPRESS": cls.kangoo.value,
            "YARIS CROSS": cls.yaris_cross.value,
            "JUMPY": cls.jumpy.value,
            "COROLLA SW": cls.corolla.value,
            "GRAND KANGOO": cls.kangoo.value,
            "DIVERS RENAULT VU": cls.unknown.value,
            "RAV 4": cls.rav4.value,
            "IONIQ 5": cls.ioniq.value,
            "MÉGANE E-TECH": cls.megane.value,
            "E": cls.unknown.value,
            "MÉGANE": cls.megane.value,
            "KANGOO": cls.kangoo.value,
            "JUMPER": cls.jumper.value,
            "FIAT TIPO": cls.tipo.value,
            "SCÉNIC E-TECH": cls.scenic.value,
            "SCÉNIC": cls.scenic.value,
            "DIVERS PEUGEOT": cls.unknown.value,
            "CANTER CHASSIS CABINE": cls.canter.value,
            "ZAFIRA TOURER": cls.zafira.value,
            "DIVERS": cls.unknown.value,
            "BENNE": cls.unknown.value,
            "YARIS HYBRIDE": cls.yaris.value,
            "ID.BUZZ": cls.idbuzz.value,
            "TRANSIT": cls.transit.value,
            "Enyaq iV": cls.enyaq.value,
            "Kangoo": cls.kangoo.value,
            "NX 300h": cls.nx.value,
            "Proace City Electric": cls.proace_city.value,
            "MOKKA X": cls.mokka.value,
            "CARAVELLE (T6)": cls.caravelle.value,
            "COOPER SE": cls.cooper.value,
            "DAILY (EURO 6) NGV": cls.daily.value,
            "CADDY": cls.caddy.value,
            "NT400 CABSTAR (KM)": cls.nt400.value,
            "UX 250H": cls.ux.value,
            "TRANSIT 2T": cls.transit.value,
            "E-NV200 EVALIA": cls.nv200.value,
            "TRANSPORTER (T6)": cls.transporter.value,
            "PROACE CITY ELECTRIC": cls.proace_city.value,
            "E-208": cls.two08.value,
            "ID.3": cls.id3.value,
            "NV200 EVALIA": cls.nv200.value,
            "NX 300H": cls.nx.value,
            "E-NV200 EVALIA (KM)": cls.nv200.value,
            "ID. BUZZ": cls.idbuzz.value,
            "ASSET OR OTHER VEHICLE": cls.unknown.value,
            "PROACE VERSO": cls.proace.value,
            "C40 ELECTRIC": cls.c40.value,
            "ec40": cls.c40.value,
            "E-NIRO": cls.niro.value,
            "E-TRANSIT 2T": cls.transit.value,
            "TRANSIT/TOURNEO CUSTOM": cls.transit.value,
            "XC40 ELECTRIC": cls.xc40.value,
            "PROACE CITY": cls.proace_city.value,
            "AURIS TOURING SPORTS HYBRID (KM)": cls.auris.value,
            "FIESTA (MK7)": cls.fiesta.value,
            "LF - SÉRIE 3 (EURO 6)": cls.unknown.value,
            "C40 RECHARGE": cls.c40.value,
            "RELAY": cls.unknown.value,
            "ENYAQ IV": cls.enyaq.value,
            "IX1 (U11)": cls.x1.value,
            "D": cls.serie_d.value,
            "DEAUVILLE": cls.unknown.value,
            "CUPRA": cls.unknown.value,
            "EXPRESS": cls.express_van.value,
            "YARIS IV": cls.yaris.value,
            "COROLLA X": cls.corolla.value,
            "MASTER III": cls.master.value,
            "BOXER*": cls.boxer.value,
            "CLIO IV": cls.clio.value,
            "EXPRESS II": cls.express_van.value,
            "TUCSON IV": cls.tucson.value,
            "CLIO V": cls.clio.value,
            "KANGOO EXPRESS II": cls.kangoo.value,
            "JUMPER VU 4P FOURGON": cls.jumper.value,
            "C3 SOCIÉTÉ VU 5P BERLINE": cls.c3.value,
            "JUMPY VU 4P FOURGON": cls.jumpy.value,
            "TUCSON / 2020 / 5P / SUV": cls.tucson.value,
            "ENYAQ / 2020 / 5P / SUV": cls.enyaq.value,
            "MINI / 2014 / 3P / BERLINE": cls.unknown.value,
            "BURGMAN 650": cls.burgman.value,
            "F800 GS": cls.f800.value,
            "FLY 50": cls.fly50.value,
            "TRANSPORTER": cls.transporter.value,
            "GRAND CHEROKEE": cls.grand_cheerokee.value,
            "CABSTAR": cls.cabstar.value,
            "AF7311": cls.unknown.value,
            "207": cls.two07.value,
            "RANGER": cls.ranger.value,
            "ENYAQ COUPE coupe": cls.enyaq.value,
            "COROLLA TOURING SPORTS break": cls.corolla.value,
            "MEGANE E-TECH": cls.megane.value,
            "XC90 HYB": cls.xc90.value,
            "TRANSIT CUSTOM Business HYB": cls.transit.value,
            "JUMPER BENNE SC plancher cabine": cls.jumper.value,
            "Q5 HYB": cls.q5.value,
            "C3 SOCIETE societe": cls.c3.value,
            "X3 HYB": cls.x3.value,
            "TRANSIT Business": cls.transit.value,
            "ENYAQ IV ELECTRIC": cls.enyaq.value,
            "UX250H": cls.ux.value,
            "MEGANE-E": cls.megane.value,
            "Enyaq": cls.enyaq.value,
            "enyaq": cls.enyaq.value,
            "Tucson": cls.tucson.value,
            "RAV4(5)": cls.rav4.value,
            "YARIS4": cls.yaris.value,
            "EXPRESS CONFORT": cls.express_van.value,
            "PROACE TOLE": cls.proace.value,
            "ID.4": cls.id4.value,
            "PROACE FT": cls.proace.value,
            "MASTER PROPULSION": cls.master.value,
            "YARIS HYBRID": cls.yaris.value,
            "COROLLA TS": cls.corolla.value,
            "RAV4 HSD": cls.rav4.value,
            "partners": cls.partner.value,
            "i4 (g26)": cls.serie4.value,
            "ds 4": cls.ds4.value,
            "swift4": cls.swift.value,
            "gla2": cls.gla.value,
            "5008(2)": cls.five008.value,
            "308(2)": cls.three08.value,
            "sportage5": cls.sportage.value,
            "330xi(7)": cls.three30.value,
            "corolla12": cls.corolla.value,
            "tiguan2": cls.tiguan.value,
            "i30(3)": cls.i30.value,
            "330xi": cls.serie3.value,  # Type of Series 3
            "c(4)": cls.c4.value,
            "espace6": cls.espace.value,
            "mini4": cls.cooper.value,
            "golf8": cls.golf.value,
            "x3(3)": cls.x3.value,
            "3008(2)": cls.three008.value,
            "scenic4": cls.scenic.value,
            "308(3)": cls.three08.value,
            "508(2)": cls.five08.value,
            "x1(3)": cls.x1.value,
            "320i(7)": cls.three20.value,
            "yaris3": cls.yaris.value,
            "2008(2)": cls.two008.value,
            "330e(7)": cls.three30.value,
            "clubman3": cls.clubman.value,
            "c4(3)": cls.c4.value,
            "q3(2)": cls.q3.value,
            "octavia4": cls.octavia.value,
            "c3 iii": cls.c3.value,
            "kadjar": cls.kadjar.value,
            "touareg": cls.touareg.value,
            "megane iv": cls.megane.value,
            "308 rs": cls.three08.value,
            "e-3008": cls.three008.value,
            "karoq": cls.karoq.value,
            "serie 1 ii": cls.serie1.value,
            "e-5008": cls.five008.value,
            "peugeot e-5008 bev 97kwh allure suv vp": cls.five008.value,
            "zoé": cls.zoe.value,
            "308sw": cls.three08.value,
            "ex90": cls.ex90.value,
            "ds4 ii": cls.ds4.value,
            "ex 90": cls.ex90.value,
            "xc 90": cls.xc90.value,
            "ds5": cls.ds5.value,
            "2008 ii": cls.two008.value,
            "ds3 cross": cls.ds3.value,
            "x-trail": cls.xtrail.value,
            "touareg ii": cls.touareg.value,
            "5008 iii": cls.five008.value,
            "classe gla": cls.gla.value,
            "q4 e-tron": cls.q4.value,
            "sportage v": cls.sportage.value,
            "scenic iv": cls.scenic.value,
            "308 iii": cls.three08.value,
            "ds3 ii": cls.ds3.value,
            "3008 iii": cls.three008.value,
            "c3 societe": cls.c3.value,
            "rav4 hybride": cls.rav4.value,
            "corolla touring sports": cls.corolla.value,
            "c40 elec": cls.c40.value,
            "boxer tole": cls.boxer.value,
            "transit custom tole business hyb": cls.transit.value,
            "jumper tole": cls.jumper.value,
            "kona elec": cls.kona.value,
            "e-niro elec": cls.niro.value,
            "id. buzz tole": cls.idbuzz.value,
            "ev6 elec": cls.ev6.value,
            "proace tole elec": cls.proace.value,
            "transit tole business elec": cls.transit.value,
            "master tole": cls.master.value,
            "ioniq 5 elec": cls.ioniq.value,
            "yaris cross hybride": cls.yaris_cross.value,
            "jumpy tole": cls.jumpy.value,
            "xc40 elec": cls.xc40.value,
            "megane e-tech elec": cls.megane.value,
            "niro ev elec": cls.niro.value,
            "208 ii": cls.two08.value,
            "serie 1 iii": cls.serie1.value,
            "classe gla ii": cls.gla.value,
            "508 ii": cls.five08.value,
            "a4 v": cls.a4.value,
            "touareg iii": cls.touareg.value,
            "crv v": cls.crv.value,
            "discovery sport": cls.discovery.value,
            "a3 iv": cls.a3.value,
            "clio societe": cls.clio.value,
            "clio 2": cls.clio.value,
            "fiat 6oo": cls.sixhundred.value,
            "megane 2": cls.megane.value,
            "clio 4": cls.clio.value,
            "clio 5": cls.clio.value,
            "clio 3": cls.clio.value,
            "nissan nt400": cls.nt400.value,
            "trade": cls.trade.value,
            "600 iii": cls.sixhundred.value,
            "partner iii": cls.partner.value,
            "captur ii": cls.captur.value,
            "captur zen": cls.captur.value,
            "master iv": cls.master.value,
            "nv400": cls.nv400.value,
            "berlingo ii": cls.berlingo.value,
            "x1 iii": cls.x1.value,
            "macan ii": cls.macan.value,
            "kangoo iii": cls.kangoo.value,
            "ludix": cls.ludix.value,
            "clio iii": cls.clio.value,
            "rav4 v": cls.rav4.value,
            "x5 iv": cls.x5.value,
            "trafic iii": cls.trafic.value,
            "berlingo iii": cls.berlingo.value,
            "citroen berlingo taillempuretech 110 s&s bvm6 feelminims boitemanuelle": cls.berlingo.value,
            "tweet 50": cls.tweet.value,
            "c3 ii": cls.c3.value,
            "focus sw": cls.focus.value,
            "talisman estate": cls.talisman.value,
            "megane societe": cls.megane.value,
            ".": None,
            "serie 1 f20 lci": cls.serie1.value,
            "proceed": cls.proceed.value,
            "megane berline": cls.megane.value,
            "a4 avant": cls.a4.value,
            "ux mc": cls.ux.value,
            "classe e iv": cls.classE.value,
            "twingo iii": cls.twingo.value,
            "scenic v": cls.scenic.value,
            "aygo x": cls.aygo.value,
            "zip": cls.zip.value,
            "enyak": cls.enyaq.value,
            "scenic e-": cls.scenic.value,
            "t-cross": cls.troc.value,
            "ds 3": cls.ds3.value,
            "ioniq 5 electric": cls.ioniq.value,
            "c4 iii": cls.c4.value,
            "yaris cro": cls.yaris_cross.value,
            "sandero 3": cls.sandero.value,
            "c-hr ii": cls.chr.value,
            "berlingo3": cls.berlingo.value,
            "c3 aircr.": cls.c3.value,
            "bayon": cls.bayon.value,
            "jogger": cls.jogger.value,
            "id. buzz cargo": cls.idbuzz.value,
            "5": cls.r5.value,
            "arkana techno": cls.arkana.value,
            "lynk & co 01": cls.zero1.value,
            "puma gen-e": cls.puma.value,
            "symbioz": cls.symbioz.value,
            "passat": cls.passat.value,
            "208 ii (ub_, up_, uw_, uj_)": cls.two08.value,
            "serie 4 ii": cls.serie4.value,
            "espace vi": cls.espace.value,
            "tourneo connect": cls.tourneo.value,
            "megane v": cls.megane.value,
            "kuga iii": cls.kuga.value,
            "190s42": cls.one90S42.value,
            "3008 ii suv (mc_, mr_, mj_, m4_)": cls.three008.value,
            "peugeot e-3008 bev 97kwh allure": cls.three008.value,
            "puma ii": cls.puma.value,
            "kona ii": cls.kona.value,
            "sandero iii": cls.sandero.value,
            "c4 iii (ba_, bb_, bc_)": cls.c4.value,
            "bayon (bc3)": cls.bayon.value,
            "c3 aircross ii (2r_, 2c_)": cls.c3.value,
            "c3 / c3 origin iii (sx)": cls.c3.value,
            "mustang mach-e": cls.mustang.value,
            "yaris 5p": cls.yaris.value,
            "yaris affair.5p": cls.yaris.value,
            "ix1 electric": cls.x1.value,
            "2 cv": cls.two_chevaux.value,
            "arteon": cls.arteon.value,
            "qashqai iii": cls.qashqai.value,
            "500 iii": cls.fivehundred.value,
            "combo iii": cls.combo.value,
            "atto 3": cls.atto.value,
            "mgs5": cls.mgs5.value,
            "nemo": cls.nemo.value,
            "tge": cls.tge.value,
            "model 3 (5yj3)": cls.model_3.value,
            "nemo camionnette/monospace (aa_)": cls.nemo.value,
            "berlingo camionnette/monospace (k9)": cls.berlingo.value,
            "berlingo camionnette/monospace (b9)": cls.berlingo.value,
            "xc60 ii (246)": cls.xc60.value,
            "expert fourgon (v_)": cls.expert.value,
            "aygo x (_b7_)": cls.aygo.value,
            "trafic iii fourgon (fg_)": cls.trafic.value,
            "ex90 (356)": cls.ex90.value,
            "xc40 (536)": cls.xc40.value,
            "a4 b9 avant (8w5, 8wd)": cls.a4.value,
            "5008 ii (mc_, mj_, mr_, m4_)": cls.five008.value,
            "xp560d": cls.xp560.value,
            "308 sw ii (lc_, lj_, lr_, lx_, l4_)": cls.three08.value,
            "id.buzz electric": cls.idbuzz.value,
            "proace fourgon (mdz_)": cls.proace.value,
            "id. buzz cargo (eba)": cls.idbuzz.value,
            "touran (1t1, 1t2)": cls.touran.value,
            "eqb electric": cls.eqb.value,
            "c5 aircross (a_)": cls.c5.value,
            "twingo ii (cn0_)": cls.twingo.value,
            "scenic iii": cls.scenic.value,
            "xsara (n1)": cls.xsara.value,
            "406": cls.four06.value,
            "clio iii estate": cls.clio.value,
            "jazz iii (ge_, gg_, gp_, za_)": cls.jazz.value,
            "kangoo express (fc0/1_)": cls.kangoo.value,
            "2008 ii (ud_, us_, uy_, uj_, ur_, uc_)": cls.two008.value,
            "avenger (j2)": cls.avenger.value,
            "serie 2 ii": cls.serie2.value,
            "astra": cls.astra.value,
            "proace city camionnette/monospace (bpz_)": cls.proace.value,
            "jumper ii fourgon": cls.jumper.value,
            "kangoo express (fw0/1_)": cls.kangoo.value,
            "vivaro iii": cls.vivaro.value,
            "vivaro électrique": cls.vivaro.value,
            "gsx800u": cls.gsx800.value,
            "focus iv": cls.focus.value,
            "yaris (_p21_, _pa1_, _ph1_)": cls.yaris.value,
            "fazer 600": cls.fazer.value,
            "agila": cls.agila.value,
            "c3 iii (sx)": cls.c3.value,
            "190s31": cls.one90s31,
            "formentor": cls.formentor.value,
            "aygo (_b1_)": cls.aygo.value,
            "cux": cls.cux.value,
            "fjr1300a": cls.fjr1300.value,
            "primastar ii": cls.primastar.value,
            "xj600": cls.xj600.value,
            "clio ii (bb_, cb_)": cls.clio.value,
            "grandland x": cls.grandland.value,
            "v50": cls.v50.value,
            "c3 ii (sc_)": cls.c3.value,
            "proace max": cls.proace_max.value,
            "PROACE MAX": cls.proace_max.value,
            "light vehicle diesel": cls.unknown.value,
            "megane e-": cls.megane.value,
            "renault 5": cls.r5.value,
            "nv200 fourgon": cls.nv200.value,
            "207/207+ (wa_, wc_)": cls.two07.value,
            "fjr1300": cls.fjr1300.value,
            "electric": cls.unknown.value,
            "niro ii": cls.niro.value,
            "sprinter 3,5-t fourgon (b906)": cls.sprinter.value,
            "classe a iv": cls.classA.value,
            "kangoo / grand kangoo ii (kw0/1_)": cls.kangoo.value,
            "0750e": cls.seven50.value,
            "viano": cls.viano.value,
            "octavia iv": cls.octavia.value,
            "x1 (u11)": cls.x1.value,
            "c4 ii": cls.c4.value,
            "mp3 500lt": cls.mp3.value,
            "id.4 (e21)": cls.id4.value,
            "scudo fourgon": cls.scudo.value,
            "classe sl": cls.classSL.value,
            "ar 50": cls.ar50.value,
            "transit connect": cls.transit.value,
            "elroq": cls.elroq.value,
            "ev6 (cv)": cls.ev6.value,
            "arocs": cls.arocs.value,
            "transit connect v408 camionnette/monospace": cls.transit.value,
            "sprinter iii": cls.sprinter.value,
            "308 iii (fb_, fh_, fp_, f3_, fm_)": cls.three08.value,
            "35s14n": cls.three5s14.value,
            "boxer fourgon": cls.boxer.value,
            "ioniq 5 (ne)": cls.ioniq.value,
            "kona (os, ose, osi)": cls.kona.value,
            "jumpy iii fourgon (v_)": cls.jumpy.value,
            "c40 (539)": cls.c40.value,
            "rav 4 v (_a5_, _h5_)": cls.rav4.value,
            "partner ii": cls.partner.value,
            "x-adv750": cls.x_adv.value,
            "vivaro b fourgon (x82)": cls.vivaro.value,
            "transit vi": cls.transit.value,
            "ar50": cls.ar50.value,
            "enyaq iv suv (5az)": cls.enyaq.value,
            "yaris iii": cls.yaris.value,
            "aygo (_b4_)": cls.aygo.value,
            "niro ii (sg2)": cls.niro.value,
            "c-hr (_x1_)": cls.chr.value,
            "partner camionnette/monospace": cls.partner.value,
            "a-class": cls.classA.value,
            "master iii van": cls.master.value,
            "3008 ii suv": cls.three008.value,
            "vivaro a van": cls.vivaro.value,
            "transit v363 van": cls.transit.value,
            "corolla hatchback": cls.corolla.value,
            "jumper ii platform/chassis": cls.jumper.value,
            "niro i": cls.niro.value,
            "dyna platform/chassis": cls.dyna.value,
            "scudo van": cls.scudo.value,
            "vito mixto": cls.vito.value,
            "ducato van": cls.ducato.value,
            "xc90 ii": cls.xc90.value,
            "express box body/mpv": cls.express_van.value,
            "jumper ii van": cls.jumper.value,
            "nv200 van": cls.nv200.value,
            "kangoo rapid": cls.kangoo.value,
            "focus ii saloon": cls.focus.value,
            "207/207+": cls.two07.value,
            "partner box body/mpv": cls.partner.value,
            "enyaq iv coupe": cls.enyaq.value,
            "sprinter 3,5-t van": cls.sprinter.value,
            "sprinter 5-t platform/chassis": cls.sprinter.value,
            "enyaq iv suv": cls.enyaq.value,
            "i4": cls.serie4.value,
            "boxer van": cls.boxer.value,
            "proace van": cls.proace.value,
            "jumpy iii van": cls.jumpy.value,
            "transit connect v408 box body/mpv": cls.transit.value,
            "nv300 van": cls.nv300.value,
            "vivaro b van": cls.vivaro.value,
            "talento van": cls.talento.value,
            "master iii platform/chassis": cls.master.value,
            "daily vi van": cls.daily.value,
            "kangoo / grand kangoo ii": cls.kangoo.value,
            "scenic e-tech phase i": cls.scenic.value,
            "trafic iii van": cls.trafic.value,
            "megane e-tech suv": cls.megane.value,
            "208 i": cls.two08.value,
            "trafic ii van": cls.trafic.value,
            "berlingo box body/mpv": cls.berlingo.value,
            "4n-berlingo-rad": cls.berlingo.value,
            "proace city box body/mpv": cls.proace.value,
            "doblo cargo": cls.doblo.value,
            "transit van": cls.transit.value,
            "rav 4 v": cls.rav4.value,
            "308 ii": cls.three08.value,
            "proace max van": cls.proace_max.value,
            "rav-4": cls.rav4.value,
            "x2": cls.x2.value,
            "volvo xc40 b4 197 dct 7 plus vp boite auto (volvo)": cls.xc40.value,
            "1 4x4": cls.unknown.value,
            "q3 e-tron": cls.q3.value,
            "renault espace finition esprit alpine  - 5 places (somelac)": cls.espace.value,
            "vw t roc": cls.troc.value,
            "eqb250": cls.eqb.value,
            "id4 gtx": cls.id4.value,
            "cupra leon": cls.leon.value,
            "enyak 85 x": cls.enyaq.value,
            "rafale": cls.rafale.value,
            "1 voiture (je n'ai pas le détail)": cls.unknown.value,
            "espace esprit alpine e-tech full hybrid 200 - 7 pl (sacoa)": cls.espace.value,
            "ds7 crossback e-tense 4x4 300": cls.ds7.value,
            "renault espace": cls.espace.value,
            "y3": cls.unknown.value,
            "mp3 350 lt": cls.mp3.value,
            "volkswagen passat": cls.passat.value,
            "santa fe": cls.santa_fe.value,
            "id4": cls.id4.value,
            "renault austral finition evolution (somelac)": cls.austral.value,
            "renault megane tech ze - techno (somelac)": cls.megane.value,
            "renault espace finition esprit alpine (somelac)": cls.espace.value,
            "audi a3 sportback": cls.a3.value,
            "vitara": cls.vitara.value,
            "octavia sw": cls.octavia.value,
            "225e xdrive active tourer": cls.serie2.value,
            "225xe active tourer": cls.serie2.value,
            "id4 4r motrices": cls.id4.value,
            "peugeot suv 3008 gt plug-in hybrid 225 e-eat8 - (peugeot)": cls.three008.value,
            "id.4 77 kwh pro 4motion 286": cls.id4.value,
            "transorter": cls.transporter.value,
            "stronic fl": cls.unknown.value,
            "id.4 4 motion": cls.id4.value,
            "niro 1.6 gdi 129 hev premium busines dct6 berline hayon boite automatique": cls.niro.value,
            "e300": cls.classE.value,
            "renault megane": cls.megane.value,
            "citroen ds7": cls.ds7.value,
            "volkswagen id 3": cls.id3.value,
            "nx 350h": cls.nx.value,
            "skoda": cls.unknown.value,
            "renault captur": cls.captur.value,
            "opel corsa": cls.corsa.value,
            "toyota yaris": cls.yaris.value,
            "renaultsymbioz e-tech fukk hybrid 145 techno (somelac)": cls.symbioz.value,
            "renault austral hybrid  (sacoa)": cls.austral.value,
            "3008 - hybrid 300 e-eatt8 gt pack": cls.three008.value,
            "octavia combi 1,5 tsi bvm6 business": cls.octavia.value,
            "hyundai kona": cls.kona.value,
            "renault scenic e-tech": cls.scenic.value,
            "enyaq 4r motrices": cls.enyaq.value,
            "5008  suv  1.6l  puretech  180  gt line eat8  10cv": cls.five008.value,
            "renault scenic": cls.scenic.value,
            "crossland": cls.crossland.value,
            "opel crossland": cls.crossland.value,
            "e-5008 bev 97kwh allure suv vp": cls.five008.value,
            "tiguan allspace": cls.tiguan.value,
            "t roc": cls.troc.value,
            "megane estate": cls.megane.value,
            "sportage -- 1.6": cls.sportage.value,
            "sportage - 4wd": cls.sportage.value,
            "kona - 65kwh": cls.kona.value,
            "kia sportage": cls.sportage.value,
            "mp3 400 hpe": cls.mp3.value,
            "vitara 1.5 dualjet hyb privilege allg": cls.vitara.value,
            "e-3008 bev 97kwh allure": cls.three008.value,
            "jeep renegade": cls.renegade.value,
            'peugeot 208 hybrid "commercial"(peugeot-leasys)': cls.two08.value,
            'skoda octavia': cls.octavia.value,
            'skoda octovia': cls.octavia.value,
            'skoda yeti': cls.yeti.value,
            '1': None,
            '3': None,  # Probably BMW series 3 but not confirmed
            "id,4 4 motion": cls.id4.value,
            "x1 xdrive": cls.x1.value,
            "peugeot suv 3008 gt plug-in hybrid 225 e-eat8 (peugeot)": cls.three008.value,
            "id4 4m": cls.id4.value,
            "vw golf": cls.golf.value,
            "id5 gtx": cls.id5.value,
            "tiguan carat 1.5 tsi 150 cv dsg7": cls.tiguan.value,
            "jeep compass": cls.compass.value,
            "opel astra": cls.astra.value,
            "serie x": cls.unknown.value,
            "volkswagen touran": cls.touran.value,
            "suzuki s cross sx4": cls.scross.value,
            "mazda cx-5": cls.cx5.value,
            "renault scenic business blue dci 120": cls.scenic.value,
            "id.4 gtx": cls.id4.value,
            "model y grande autonomie": cls.model_y.value,
            "tesla model y grande autonomie": cls.model_y.value,
            "x3 xdrive30e": cls.x3.value,
            "volkswagen golf": cls.golf.value,
            "skoda octavia rs": cls.octavia.value,
            "toyota proace electrique (partenariat) somelac": cls.proace.value,
            "jimny": cls.jimny.value,
            "rangers": cls.ranger.value,
            "kangoo ze grand confort (sacoa)": cls.kangoo.value,
            "kangoo ze confort (electrique)  (sacoa)": cls.kangoo.value,
            "5075e": cls.five075e.value,
            "peugeot": cls.unknown.value,
            "toyota proace city electric (coffre)(electrique)(toyota)": cls.proace_city.value,
            "bus 50 places": cls.unknown.value,
            "skoda karoq": cls.karoq.value,
            "hilux": cls.hilux.value,
            "renault austral techno full hybrid e-tech 200ch (somelac)": cls.austral.value,
            "land cruiser": cls.land_cruiser.value,
            "fiat panda": cls.panda.value,
            "vpi fiat ducato avec remorque (incendie) sdis de la vienne 86": cls.ducato.value,
            "sedici": cls.sedici.value,
            "pajero": cls.pajero.value,
            "peugeot 308": cls.three08.value,
            "nissan townstar": cls.townstar.value,
            "renault master e-tech elec fourgon (ambulance) (sacoa)": cls.master.value,
            "jimmy": cls.jimny.value,
            "d max": cls.d_max.value,
            "kangoo ze maxi": cls.kangoo.value,
            "club": cls.club.value,
            "citroen berlingo taille m puretech 110 s&s bvm6": cls.berlingo.value,
            "iveco petit forestier": cls.petit_forestier.value,
            "kangoo ze grand confort": cls.kangoo.value,
            "peugeot 207": cls.two07.value,
            "jeep renage": cls.renegade.value,
            "hilux hard top": cls.hilux.value,
            "suzuki vitara 1.5  dualjet": cls.vitara.value,
            "suzuki vitara 1.5 dualjet hyb privilege allg": cls.vitara.value,
            "hilux plateau": cls.hilux.value,
            "peugeot e-partner fourgon taille m - (peugeot)": cls.partner.value,
            "polaris sportsman": cls.sportsman.value,
            "dmax": cls.d_max.value,
            "volkswagen caddy": cls.caddy.value,
            "suzuki vitara 1.4 boosterjet hybrid privlieg": cls.vitara.value,
            "kangoo ze confort (electrique)": cls.kangoo.value,
            "kia ev6 bev 77.4 kwh 4wd": cls.ev6.value,
            "landcruiser pzj75": cls.land_cruiser.value,
            "golf sportsvan": cls.golf.value,
            "kombi": cls.combi.value,
            "trafic fourgon nv fg g": cls.trafic.value,
            "renault kangoo maxi ze gd volume (sacoa)": cls.kangoo.value,
            "yaris cross hyb": cls.yaris.value,
            "3 bus de 50 places": cls.unknown.value,
            "mp3 300 hpe": cls.mp3.value,
            "john deer": cls.unknown.value,
            "l200": cls.l200.value,
            "fiorino": cls.fiorino.value,
            "citroen berlingo": cls.berlingo.value,
            "peugeot e-rifter taille m - moteur elec 136ch": cls.rifter.value,
            "volvo v60": cls.v60.value,
            "kerax": cls.kerax.value,
            "e-expert combi taille xl (peugeot)": cls.expert.value,
            "opel vivaro": cls.vivaro.value,
            "renault kangoo ze  grand confort": cls.kangoo.value,
            "dacia duster": cls.duster.value,
            "iveco": cls.unknown.value,
            "kangoo van e-tech": cls.kangoo.value,
            "merlo": cls.unknown.value,
            "skoda enyaq electrique 85x": cls.enyaq.value,
            "citroen berlingo taillempuretech 110 s&s bvm6": cls.berlingo.value,
            "move eco cargo 500": cls.cargo500.value,
            "minibus 9 places": cls.unknown.value,
            "kangoo express maxi": cls.kangoo.value,
            "renault kangoo ze confort (sacoa)": cls.kangoo.value,
            "kangoo van e tech electric": cls.kangoo.value,
            "peugeot e-partner (peugeot)": cls.partner.value,
            "quad polaris  ranger": cls.ranger.value,
            "transporter rehaussé": cls.transporter.value,
            "peugeot 2008": cls.two008.value,
            "amarok": cls.amarok.value,
            "6 minibus 9 places": cls.unknown.value,
            "hi-lux": cls.hilux.value,
            "renault  kangoo van  extra blue dci 95 (sacoa)": cls.kangoo.value,
            "id3": cls.id3.value,
            "hy400/420": cls.hy420.value,
            "landcruiser": cls.land_cruiser.value,
            "renault kangoo": cls.kangoo.value,
            "toyota rav4": cls.rav4.value,
            "transporter-fourgon": cls.transporter.value,
            "maxxer 30": cls.maxxer.value,
            "peugeot e-expert": cls.expert.value,
            "fiat panda 4x4": cls.panda.value,
            "octavia iii combi": cls.octavia.value,
            "grand scénic iv": cls.scenic.value,
            "passat b8 variant": cls.passat.value,
            "i3": cls.serie3.value,
            "e-class all-terrain": cls.classE.value,
            "octavia iv combi": cls.octavia.value,
            "5008 ii": cls.five008.value,
            "id.5": cls.id5.value,
            "hilux vii pickup": cls.hilux.value,
            "astra l sports tourer": cls.astra.value,
            "508 sw ii": cls.five08.value,
            "glc coupe": cls.glc.value,
            "expert bus": cls.expert.value,
            "boxer platform/chassis": cls.boxer.value,
            "v60 ii": cls.v60.value,
            "caddy v box body/mpv": cls.caddy.value,
            "vw caddy 4m 3m3 122ch": cls.caddy.value,
            "hilux vi pickup": cls.hilux.value,
            "308 sw iii": cls.three08.value,
            "clio ii": cls.clio.value,
            "polo vi": cls.polo.value,
            "vivaro c van": cls.vivaro.value,
            "kangoo iii rapid": cls.kangoo.value,
            "daily iv van": cls.daily.value,
            "a3 limousine": cls.a3.value,
            "traveller bus": cls.traveller.value,
            "peugeot e-traveller bev 75kwh 136 ps xl business monospace": cls.traveller.value,
            "spacetourer bus": cls.spacetourer.value,
            "tge platform/chassis": cls.tge.value,
            "mini cooper": None,
            "crafter van": cls.crafter.value,
            "golf vii": cls.golf.value,
            "megane iii grandtour": cls.megane.value,
            "scénic iv": cls.scenic.value,
            "308 sw ii": cls.three08.value,
            "sx4 s-cross": cls.scross.value,
            "kodiaq ii": cls.kodiac.value,
            "arkana i": cls.arkana.value,
            "nx ii": cls.nx.value,
            "2 active tourer": cls.serie2.value,
            "l200 / triton": cls.l200.value,
            "megane iv hatchback": cls.megane.value,
            "rafale coupe": cls.rafale.value,
            "crossland x / crossland": cls.crossland.value,
            "caddy iv box body/mpv": cls.caddy.value,
            "d-max i": cls.d_max.value,
            "pajero iv": cls.pajero.value,
            "caddy iv mpv": cls.caddy.value,
            "proace bus": cls.proace.value,
            "proace city verso mpv": cls.proace_city.value,
            "jimny closed off-road vehicle": cls.jimny.value,
            "golf viii": cls.golf.value,
            "transit custom v710 van": cls.transit.value,
            "vivaro b bus": cls.vivaro.value,
            "land cruiser 80": cls.land_cruiser.value,
            "qashqai ii": cls.qashqai.value,
            "1": None,
            "kodiaq i": cls.kodiac.value,
            "3 touring": cls.serie3.value,
            "ducato platform/chassis": cls.ducato.value,
            "hilux viii pickup": cls.hilux.value,
            "nt400 cabstar": cls.nt400.value,
            "boxer bus": cls.boxer.value,
            "a4 b9 avant": cls.a4.value,
            "sprinter 5-t van": cls.sprinter.value,
            "renegade suv": cls.renegade.value,
            "megane iv grandtour": cls.megane.value,
            "transporter t5 van": cls.transporter.value,
            "ceed sportswagon": cls.ceed.value,
            "corolla estate": cls.corolla.value,
            "rav 4 iv": cls.rav4.value,
            "transporter t6 / caravelle t6 bus": cls.transporter.value,
            "leon sportstourer": cls.leon.value,
            "land cruiser hardtop": cls.land_cruiser.value,
            "townstar box body/mpv": cls.townstar.value,
            "golf sportsvan vii": cls.golf.value,
            "megane iii hatchback": cls.megane.value,
            "corsa f": cls.corsa.value,
            "transporter t6 van": cls.transporter.value,
            "expert van": cls.expert.value,
            "d-max ii": cls.d_max.value,
            "land cruiser prado": cls.land_cruiser.value,
            "scenic e-tech": cls.scenic.value,
            "transit custom kombi": cls.transit.value,
            "rav4 plug in": cls.rav4.value,
            "e-jumpy": cls.jumpy.value,
            "serie 2 active toure": cls.serie2.value,
            "ix1": cls.x1.value,
            "daily ii van": cls.daily.value,
            "xc60 ii": cls.xc60.value,
            "master i van": cls.master.value,
            "master ii bus": cls.master.value,
            "mondeo v hatchback": cls.mondeo.value,
            "trafic van": cls.trafic.value,
            "trafic 9 places": cls.trafic.value,
            "santa fe v": cls.santa_fe.value,
            "ds 3 / ds 3 crossback": cls.ds3.value,
            "santa fe iv": cls.santa_fe.value,
            "5 touring": cls.series5.value,
            "mini countryman": cls.countryman.value,
            "fiorino box body/mpv": cls.fiorino.value,
            "vito tourer": cls.vito.value,
            "mini clubman": cls.clubman.value,
            "x-trail iv": cls.xtrail.value,
            "ds 4 ii": cls.ds4.value,
            "3": None,  # Probably BMW series 3 but not confirmed
            "c-class t-model": cls.classC.value,
            "passat b9 variant": cls.passat.value,
            "c3 aircross i": cls.c3.value,
            "jumper iii van": cls.jumper.value,
            "id.4 electric": cls.id4.value,
            "id-4": cls.id4.value,
            "duster dci 110": cls.duster.value,
            "id-4 4 motion 210kw": cls.id4.value,
            "sportsman 1000 touring": cls.sportsman.value,
            "x1drive 25e(elec)": cls.x1.value,
            "tp11ssx": cls.unknown.value,
            "id.4 gtx 220kw": cls.id4.value,
            "ranger 1000 xp": cls.ranger.value,
            "sportman x": cls.sportsman.value,
            "duster hybride": cls.duster.value,
            "outlander 1000 max 6x6": cls.outlander.value,
            "alpine": cls.unknown.value,
            "7000": cls.unknown.value,
            "7000xt": cls.unknown.value,
            "icat pro 13 vin": cls.unknown.value,
            "remorque": cls.unknown.value,
            "ltp": cls.unknown.value,
            "bearc": cls.unknown.value,
            "motoneige": cls.unknown.value,
            "husky": cls.unknown.value,
            "ranger alpine m": cls.ranger_alpine.value,
            "5000xt": cls.unknown.value,
            "nacelle": cls.unknown.value,
            "motoneige adven": cls.unknown.value,
            "ts35100sl": cls.unknown.value,
            "leitwolf": cls.leitwolf.value,
            "arocs (3348)": cls.arocs.value,
            "volkswagen id.4 77 kwh pro 4motion 286": cls.id4.value,
            'ds 3 / 2022 / 5p / suv': cls.ds3.value,
            'c4 spacetourer / 2016 / 5p / monospace': cls.c4.value,
            'golf / 2020 / 5p / berline': cls.golf.value,
            'master / 2019 / 4p / fourgon tôlé': cls.master.value,
            'c-hr / 2016 / 5p / suv': cls.chr.value,
            'kangoo / 2021 / 4p / fourgonnette': cls.kangoo.value,
            'espace / 2023 / 5p / crossover': cls.espace.value,
            '3008 / 2016 / 5p / suv': cls.three008.value,
            'corolla touring sports / 2022 / 5p / break': cls.corolla.value,
            'ds 7 crossback / 2017 / 5p / suv': cls.ds7.value,
            '5008 / 2016 / 5p / suv': cls.five008.value,
            'hors': None,
            'austral / 2022 / 5p / crossover': cls.austral.value,
            'jumper châssis cabine sc vu 2p châssis cabine': cls.jumper.value,
            'jumper / 2014 / 4p / fourgon tôlé': cls.jumper.value,
            'trafic / 2021 / 4p / fourgon tôlé': cls.trafic.value,
            'clio / 2023 / 5p / berline': cls.clio.value,
            't-roc / 2017 / 5p / suv': cls.troc.value,
            't-roc / 2021 / 5p / suv': cls.troc.value,
            '2008 / 2019 / 5p / crossover': cls.two008.value,
            'boxerchassiscabine sc / 2014 / 2p / chassis cabine': cls.boxer.value,
            'berlingo vu 4p fourgonnette': cls.berlingo.value,
            'berlingo vu 3p fourgonnette': cls.berlingo.value,
            'jumper plateau ridelles sc vu 2p plateau': cls.jumper.value,
            'boxer / 2014 / 4p / combi': cls.boxer.value,
            'mégane berline / 2020 / 5p / berline': cls.megane.value,
            'berlingo cabine approfondie vu 4p fourgonnette': cls.berlingo.value,
            'model y / 2021 / 5p / suv': cls.model_y.value,
            'c3 aircross / 2017 / 5p / suv': cls.c3.value,
            'trafic / 2021 / 4p / combi': cls.trafic.value,
            'tiguan / 2020 / 5p / suv': cls.tiguan.value,
            'tiguan allspace / 2021 / 5p / suv': cls.tiguan.value,
            'q3 sportback / 2019 / 5p / suv': cls.q3.value,
            'captur / 2019 / 5p / suv': cls.captur.value,
            'q3 / 2018 / 5p / suv': cls.q3.value,
            'jumpy 4p combi': cls.jumpy.value,
            'ds 7 / 2022 / 5p / suv': cls.ds7.value,
            '5008 / 2020 / 5p / suv': cls.five008.value,
            'e-jumpy / 2016 / 4p / combi': cls.jumpy.value,
            "opel mokka": cls.mokka.value,
            "yeti": cls.yeti.value,
            'r500': cls.unknown.value,
            'opel mokka': cls.mokka.value,
            'tourneo custom v362 bus': cls.tourneo.value,
            'zafira life bus': cls.zafira.value,
            'xf ii': cls.xf.value,
            'fabia iv': cls.fabia.value,
            'talento bus': cls.talento.value,
            'transit custom v362 bus': cls.transit.value,
            'spring': cls.spring,
            'ranger extended cab pickup': cls.ranger.value,
            'berlingo / berlingo first mpv': cls.berlingo.value,
            'range rover evoque': cls.evoque.value,
            'd-max iii': cls.d_max.value,
            'multivan t6': cls.multivan.value,
            'g4 platform/chassis': cls.g4.value,
            'space wagon': cls.space_wagon.value,
            'across': None,
            'mokka / mokka x': cls.mokka.value,
            'cargo 500': cls.cargo500.value,
        }


@dataclass
class ModelVersion:
    model: Models
    version_regex: str
    name: str


@unique
class ModelVersions(Enum):
    jumper_l1h1 = ModelVersion(
        model=Models.jumper,
        version_regex=r"(?:\W|^|$)L1H1(?:\W|^|$)",
        name="L1H1",
    )
    jumper_l2h1 = ModelVersion(model=Models.jumper, version_regex=r"(?:\W|^|$)L2H1(?:\W|^|$)", name="L2H1")
    jumper_l2h2 = ModelVersion(model=Models.jumper, version_regex=r"(?:\W|^|$)L2H2(?:\W|^|$)", name="L2H2")
    jumper_l4h2 = ModelVersion(model=Models.jumper, version_regex=r"(?:\W|^|$)L4H2(?:\W|^|$)", name="L4H2")
    two08_allure_business = ModelVersion(
        model=Models.two08, version_regex=r"(?:\W|^|$)ALLURE BUSINESS(?:\W|^|$)", name="Business"
    )
    five008_active_business = ModelVersion(
        model=Models.five008, version_regex=r"(?:\W|^|$)ACTIVE BUSINESS(?:\W|^|$)", name="Active Business"
    )
    auris18 = ModelVersion(model=Models.auris, version_regex=r"(?:\W|^|$)1.8(?:\W|^|$)", name="1.8")
    boxer_l1h1 = ModelVersion(model=Models.boxer, version_regex=r"(?:\W|^|$)L1H1(?:\W|^|$)", name="L1H1")
    boxer_l2h1 = ModelVersion(model=Models.boxer, version_regex=r"(?:\W|^|$)L2H1(?:\W|^|$)", name="L2H1")
    boxer_l2h2 = ModelVersion(model=Models.boxer, version_regex=r"(?:\W|^|$)L2H2(?:\W|^|$)", name="L2H2")
    boxer_l4h2 = ModelVersion(model=Models.boxer, version_regex=r"(?:\W|^|$)L4H2(?:\W|^|$)", name="L4H2")
    boxer_l3h3 = ModelVersion(model=Models.boxer, version_regex=r"(?:\W|^|$)L3H3(?:\W|^|$)", name="L3H3")
    boxer_l3h2 = ModelVersion(model=Models.boxer, version_regex=r"(?:\W|^|$)L3H2(?:\W|^|$)", name="L3H2")
    chr_dynamic = ModelVersion(model=Models.chr, version_regex=r"(?:\W|^|$)DYNAMIC(?:\W|^|$)", name="Dynamic")
    c3_live = ModelVersion(model=Models.c3, version_regex=r"(?:\W|^|$)LIVE(?:\W|^|$)", name="Live")
    c3_feel = ModelVersion(model=Models.c3, version_regex=r"(?:\W|^|$)FEEL(?:\W|^|$)", name="Feel")
    c3_shine = ModelVersion(model=Models.c3, version_regex=r"(?:\W|^|$)SHINE(?:\W|^|$)", name="Shine")
    c4_live = ModelVersion(model=Models.c4, version_regex=r"(?:\W|^|$)LIVE(?:\W|^|$)", name="Live")
    c4_feel = ModelVersion(model=Models.c4, version_regex=r"(?:\W|^|$)FEEL(?:\W|^|$)", name="Feel")
    c4_shine = ModelVersion(model=Models.c4, version_regex=r"(?:\W|^|$)SHINE(?:\W|^|$)", name="Shine")
    captur_equilibre = ModelVersion(
        model=Models.captur, version_regex=r"(?:\W|^|$)EQUILIBRE(?:\W|^|$)", name="Equilibre"
    )
    captur_evolution = ModelVersion(
        model=Models.captur, version_regex=r"(?:\W|^|$)EVOLUTION(?:\W|^|$)", name="Evolution"
    )
    captur_techno = ModelVersion(model=Models.captur, version_regex=r"(?:\W|^|$)TECHNO(?:\W|^|$)", name="Techno")
    captur_iconic = ModelVersion(model=Models.captur, version_regex=r"(?:\W|^|$)ICONIC(?:\W|^|$)", name="Iconic")
    clio_life = ModelVersion(model=Models.clio, version_regex=r"(?:\W|^|$)LIFE(?:\W|^|$)", name="Life")
    clio_zen = ModelVersion(model=Models.clio, version_regex=r"(?:\W|^|$)ZEN(?:\W|^|$)", name="Zen")
    clio_intens = ModelVersion(model=Models.clio, version_regex=r"(?:\W|^|$)INTENS(?:\W|^|$)", name="Intens")
    corolla_active = ModelVersion(model=Models.corolla, version_regex=r"(?:\W|^|$)ACTIVE(?:\W|^|$)", name="Active")
    corolla_dynamic = ModelVersion(model=Models.corolla, version_regex=r"(?:\W|^|$)DYNAMIC(?:\W|^|$)", name="Dynamic")
    corolla_design = ModelVersion(model=Models.corolla, version_regex=r"(?:\W|^|$)DESIGN(?:\W|^|$)", name="Design")
    corolla_lounge = ModelVersion(model=Models.corolla, version_regex=r"(?:\W|^|$)LOUNGE(?:\W|^|$)", name="Lounge")
    ducato_xl = ModelVersion(model=Models.ducato, version_regex=r"(?:\W|^|$)XL(?:\W|^|$)", name="XL")
    enyaq_iv = ModelVersion(model=Models.enyaq, version_regex=r"(?:\W|^|$)IV(?:\W|^|$)", name="IV")
    ev6_active = ModelVersion(model=Models.ev6, version_regex=r"(?:\W|^|$)ACTIVE(?:\W|^|$)", name="Active")
    ev6_design = ModelVersion(model=Models.ev6, version_regex=r"(?:\W|^|$)DESIGN(?:\W|^|$)", name="Design")
    ix1_business = ModelVersion(
        model=Models.x1,
        version_regex=r"(?:\W|^|$)BUSINESS(?:\W|^|$)",
        name="Business",
    )
    ix1_sport = ModelVersion(
        model=Models.x1,
        version_regex=r"(?:\W|^|$)SPORT(?:\W|^|$)",
        name="Sport",
    )
    ix1_xline = ModelVersion(
        model=Models.x1,
        version_regex=r"(?:\W|^|$)xLine(?:\W|^|$)",
        name="xLine",
    )
    ioniq_5 = ModelVersion(
        model=Models.ioniq,
        version_regex=r"(?:\W|^|$)5(?:\W|^|$)",
        name="5",
    )
    jumpy_m = ModelVersion(
        model=Models.jumpy,
        version_regex=r"(?:\W|^|$)M(?:\W|^|$)",
        name="M",
    )
    jumpy_xl = ModelVersion(
        model=Models.jumpy,
        version_regex=r"(?:\W|^|$)XL(?:\W|^|$)",
        name="XL",
    )
    jumpy_xs = ModelVersion(
        model=Models.jumpy,
        version_regex=r"(?:\W|^|$)XS(?:\W|^|$)",
        name="XS",
    )
    kangoo_maxi = ModelVersion(
        model=Models.kangoo,
        version_regex=r"(?:\W|^|$)MAXI(?:\W|^|$)",
        name="Maxi",
    )
    kona_intuitive = ModelVersion(
        model=Models.kona,
        version_regex=r"(?:\W|^|$)INTUITIVE(?:\W|^|$)",
        name="Intuitive",
    )
    kona_business = ModelVersion(
        model=Models.kona,
        version_regex=r"(?:\W|^|$)BUSINESS(?:\W|^|$)",
        name="Business",
    )
    master_l1h1 = ModelVersion(
        model=Models.master,
        version_regex=r"(?:\W|^|$)L1H1(?:\W|^|$)",
        name="L1H1",
    )
    master_l2h2 = ModelVersion(
        model=Models.master,
        version_regex=r"(?:\W|^|$)L2H2(?:\W|^|$)",
        name="L2H2",
    )
    megane_evolution = ModelVersion(
        model=Models.megane,
        version_regex=r"(?:\W|^|$)EVOLUTION(?:\W|^|$)",
        name="Evolution",
    )
    megane_equilibre = ModelVersion(
        model=Models.megane,
        version_regex=r"(?:\W|^|$)EQUILIBRE(?:\W|^|$)",
        name="Equilibre",
    )
    megane_techno = ModelVersion(
        model=Models.megane,
        version_regex=r"(?:\W|^|$)TECHNO(?:\W|^|$)",
        name="Techno",
    )
    modely_grande_autonomie = ModelVersion(
        model=Models.model_y,
        version_regex=r"(?:\W|^|$)GRANDE AUTONOMIE(?:\W|^|$)",
        name="Grande Autonomie",
    )
    niro_motion = ModelVersion(
        model=Models.niro,
        version_regex=r"(?:\W|^|$)MOTION(?:\W|^|$)",
        name="Motion",
    )
    niro_active = ModelVersion(
        model=Models.niro,
        version_regex=r"(?:\W|^|$)ACTIVE(?:\W|^|$)",
        name="Active",
    )
    niro_premium = ModelVersion(
        model=Models.niro,
        version_regex=r"(?:\W|^|$)PREMIUM(?:\W|^|$)",
        name="Premium",
    )
    proace_xl = ModelVersion(
        model=Models.proace,
        version_regex=r"(?:\W|^|$)XL(?:\W|^|$)",
        name="XL",
    )
    proace_m = ModelVersion(
        model=Models.proace,
        version_regex=r"(?:\W|^|$)(?:M|MEDIUM)(?:\W|^|$)",
        name="M",
    )
    proace_long = ModelVersion(
        model=Models.proace,
        version_regex=r"(?:\W|^|$)LONG(?:\W|^|$)",
        name="Long",
    )
    proace_city_m = ModelVersion(
        model=Models.proace_city,
        version_regex=r"(?:\W|^|$)(?:M|MEDIUM)(?:\W|^|$)",
        name="M",
    )
    proace_city_long = ModelVersion(
        model=Models.proace_city,
        version_regex=r"(?:\W|^|$)LONG(?:\W|^|$)",
        name="Long",
    )
    scenic_alpine = ModelVersion(
        model=Models.scenic,
        version_regex=r"(?:\W|^|$)ALPINE(?:\W|^|$)",
        name="Alpine",
    )
    scenic_iconic = ModelVersion(
        model=Models.scenic,
        version_regex=r"(?:\W|^|$)ICONIC(?:\W|^|$)",
        name="Iconic",
    )
    scenic_evolution = ModelVersion(
        model=Models.scenic,
        version_regex=r"(?:\W|^|$)EVOLUTION(?:\W|^|$)",
        name="Evolution",
    )
    scenic_grande_autonomie = ModelVersion(
        model=Models.scenic,
        version_regex=r"(?:\W|^|$)GRANDE AUTONOMIE(?:\W|^|$)",
        name="Grande Autonomie",
    )
    trafic_l1h1 = ModelVersion(
        model=Models.trafic,
        version_regex=r"(?:\W|^|$)L1H1(?:\W|^|$)",
        name="L1H1",
    )
    trafic_l1h2 = ModelVersion(
        model=Models.trafic,
        version_regex=r"(?:\W|^|$)L1H2(?:\W|^|$)",
        name="L1H2",
    )
    transit_l1h1 = ModelVersion(
        model=Models.transit,
        version_regex=r"(?:\W|^|$)L1H1(?:\W|^|$)",
        name="L1H1",
    )
    transporter_l1h1 = ModelVersion(
        model=Models.transporter,
        version_regex=r"(?:\W|^|$)L1H1(?:\W|^|$)",
        name="L1H1",
    )
    transporter_l2h1 = ModelVersion(
        model=Models.transporter,
        version_regex=r"(?:\W|^|$)L2H1(?:\W|^|$)",
        name="L2H1",
    )
    yaris_dynamic = ModelVersion(
        model=Models.yaris,
        version_regex=r"(?:\W|^|$)DYNAMIC(?:\W|^|$)",
        name="Dynamic",
    )
    yaris_design = ModelVersion(
        model=Models.yaris,
        version_regex=r"(?:\W|^|$)DESIGN(?:\W|^|$)",
        name="Design",
    )


class Makes(Enum):
    audi = "AUDI"
    bmw = "BMW"
    cupra = "CUPRA"
    citroen = "CITROEN"
    ds = "DS"
    fiat = "FIAT"
    mercedes = "MERCEDES"
    mini = "MINI"
    opel = "OPEL"
    peugeot = "PEUGEOT"
    renault = "RENAULT"
    seat = "SEAT"
    smart = "SMART"
    skoda = "SKODA"
    toyota = "TOYOTA"
    volkswagen = "VOLKSWAGEN"
    land_rover = "LAND ROVER"
    lexus = "LEXUS"
    nissan = "NISSAN"
    alfa_romeo = "ALFA ROMEO"
    kia = "KIA"
    jaguar = "JAGUAR"
    jeep = "JEEP"
    tesla = "TESLA"
    volvo = "VOLVO"
    ford = "FORD"
    mg = "MG"
    piaggio = "PIAGGIO"
    mitsubishi = "MITSUBISHI"
    yamaha = "YAMAHA"
    hyundai = "HYUNDAI"
    daf = "DAF"
    honda = "HONDA"
    unknown = "UNKNOWN"
    man = "MAN"
    iveco = "IVECO"
    renault_trucks = "RENAULT TRUCKS"
    suzuki = "SUZUKI"
    porsche = "PORSCHE"
    swapa = "SWAPA"
    mazda = "MAZDA"
    dacia = "DACIA"
    scania = "SCANIA"
    lynk_co = "LYNK_CO"
    riese_muller = "RIESE_MULLER"
    fleximodal = "FLEXIMODAL"
    byd = "BYD"
    super_soco = "SUPER_SOCO"
    bodard = "BODARD"
    bw_trailers = "BW_TRAILERS"
    polaris = "POLARIS"
    isuzu = "ISUZU"
    move_eco = "MOVE_ECO"
    john_deere = "JOHN_DEERE"
    club_car = "CLUB_CAR"
    kymco = "KYMCO"
    hytrack = "HYTRACK"
    merlo = "MERLO"
    ligier = "LIGIER"
    linhai = "LINHAI"
    claas = "CLAAS"
    ktm = "KTM"
    ecim = "ECIM"
    tema = "TEMA"
    tr_ax = "TR_AX"
    sorel = "SOREL"
    can_am = "CAN_AM"
    manitou = "MANITOU"
    bombardier = "BOMBARDIER"
    artic_cat = "ARTIC_CAT"
    goupil = "GOUPIL"
    lamborghini = "LAMBORGHINI"
    prinoth = "PRINOTH"
    bobcat = "BOBCAT"
    cm_dupon = "CM_DUPON"
    kubota = "KUBOTA"
    aebi = "AEBI"
    corvus = "CORVUS"
    moiroud = "MOIROUD"
    humbaur = "HUMBAUR"
    quaddy = "QUADDY"
    kaeser = "KAESER"
    triumph = "TRIUMPH"
    cf_moto = "CF_MOTO"

    @classmethod
    def mapping(cls):
        return {
            "CITROËN": cls.citroen.value,
            "DS AUTOMOBILES": cls.ds.value,
            "MERCEDES BENZ": cls.mercedes.value,
            "SEAT LEON": cls.seat.value,
            "VOLKSWAGEN POLO": cls.volkswagen.value,
            "VOLKSWAGEN T-ROC": cls.volkswagen.value,
            "DIVERS": cls.unknown.value,
            "OPEL / VAUXHALL": cls.opel.value,
            "DAF TRUCKS": cls.daf.value,
            "MERCEDES-BENZ": cls.mercedes.value,
            "STANDARD": cls.unknown.value,
            "B.M.W.": cls.bmw.value,
            "*TOYOTA": cls.toyota.value,
            "volkwasgen": cls.volkswagen.value,
            "volkwagen": cls.volkswagen.value,
            "volkshagen": cls.volkswagen.value,
            "volvos": cls.volvo.value,
            "scania": cls.scania.value,
            "lynk & co": cls.lynk_co.value,
            "Riese & Müller": cls.riese_muller.value,
            "TOY": cls.toyota.value,
            "super soco": cls.super_soco.value,
            "courant": cls.unknown.value,
            "bwtrailers": cls.bw_trailers.value,
            "lexux": cls.lexus.value,
            "polaris": cls.polaris.value,
            "isuzu": cls.isuzu.value,
            "vw": cls.volkswagen.value,
            "mitshubishi": cls.mitsubishi.value,
            "move eco": cls.move_eco.value,
            "quad": None,
            "izuzu": cls.isuzu.value,
            "john deer": cls.john_deere.value,
            "club car": cls.club_car.value,
            "kymco": cls.kymco.value,
            "iveco     achat": cls.iveco.value,
            "hytrack": cls.hytrack.value,
            "merlo": cls.merlo.value,
            "volkswagen (vw)": cls.volkswagen.value,
            "k.t.m.": cls.ktm.value,
            "ecim": cls.ecim.value,
            "tema": cls.tema.value,
            "fort": None,
            "tr ax": cls.tr_ax.value,
            "sorel": cls.sorel.value,
            "lynk&co": cls.lynk_co.value,
            "can-am": cls.can_am.value,
            "brp": cls.bombardier.value,  # Bombardier recreative products
            "deroubaix": cls.unknown.value,
            "arti cat": cls.artic_cat.value,
            "articcat": cls.artic_cat.value,
            "brp lynx": cls.bombardier.value,
            "gourdon": None,
            "articat": cls.artic_cat.value,
            "lamborghini": cls.lamborghini.value,
            "prinoth": cls.prinoth.value,
            "brp  lynx": cls.bombardier.value,
            "remorque": None,
            "wolswagen": cls.volkswagen.value,
            "bobcat": cls.bobcat.value,
            "cm dupon": cls.cm_dupon.value,
            'hors parc': None,
            'chauveau': None,
            'kl': None, 
            'lamborghin': cls.lamborghini.value,
            'abde': None,
            'arctic cat': cls.artic_cat.value,
            'cf moto': cls.cf_moto.value,
        }


@unique
class GazStationType(Enum):
    company_operated = "COMPANY_OPERATED"
    dealer_operated = "DEALER_OPERATED"  # And company owned
    dealer_owned = "DEALER_OWNED"

    @classmethod
    def mapping(cls):
        return {
            "CoDo": cls.dealer_operated,
        }


@unique
class SynchronizationTypes(Enum):
    manual = "MANUAL"
    csv_upload = "CSV_UPLOAD"
    edi = "EDI"
    api = "API"


@unique
class SynchronizationStatus(Enum):
    error = "ERROR"
    ok = "OK"
    ongoing = "ONGOING"


@unique
class EquipmentCategories(Enum):
    fuel_card = "FUEL"
    toll_card = "TOLL"
    parking_card = "PARKING"
    eletric_station = "ELECTRIC_TERMINAL"
    washing_card = "WASHING"

    @classmethod
    def mapping(cls) -> dict:
        return {
            "Télébadge": cls.toll_card.value,
        }


@unique
class EquipmentStatus(Enum):
    active = "ACTIVE"
    blocked = "BLOCKED"
    closed = "CLOSED"
    in_order = "IN_ORDER"
    unknown = "UNKNOWN"

    @classmethod
    def mapping(cls):
        return {
            "En fabrication": cls.in_order.value,
            "En livraison": cls.in_order.value,
            "Actif": cls.active.value,
            "Non renouvelé": cls.closed.value,
            "Opposé": cls.blocked.value,
            "Annulé": cls.closed.value,
            "Clôturé": cls.closed.value,
        }


@unique
class EquipmentTypes(Enum):
    card = "CARD"
    badge = "BADGE"
    terminal = "TERMINAL"

    @classmethod
    def mapping(cls):
        return {
            "Télébadge": cls.badge.value,
        }


@unique
class APIPaginationType(Enum):
    """Enum to define the pagination type of the API"""

    page = "PAGE"
    offset = "OFFSET"
    cursor = "CURSOR"
    key = "KEY"


@unique
class SuppliersType(Enum):
    """Enum to define types of travel services suppliers"""

    fuel = "FUEL"
    insurance = "INSURANCE"
    maintenance = "MAINTENANCE"
    lld = "LLD"
    telematics = "TELEMATICS"
    other = "OTHER"
    manufacturer = "MANUFACTURER"
    parking = "PARKING"
    car_dealer = "CAR_DEALER"
    charging_points = "CHARGING_POINTS"
    finance = "FINANCE"


class Supplier:
    def __init__(self: typing.Self, name: str, type: SuppliersType):
        self.name = name
        self.type = type

    def __hash__(self):
        return hash(self.name)


@unique
class Suppliers(Enum):
    """ Enum to define the travel services suppliers"""
    alphabet = Supplier('ALPHABET', SuppliersType.lld)
    arval = Supplier('ARVAL', SuppliersType.lld)
    athlon = Supplier('ATHLON', SuppliersType.lld)
    ayvens = Supplier('AYVENS', SuppliersType.lld)
    backliz = Supplier('BACKLIZ', SuppliersType.lld)
    bpce = Supplier('BPCE', SuppliersType.lld)
    dentmaster = Supplier('DENTMASTER', SuppliersType.maintenance)
    euromaster = Supplier('EUROMASTER', SuppliersType.maintenance)
    fraikin = Supplier('FRAIKIN', SuppliersType.lld)
    masternaut = Supplier('MASTERNAUT', SuppliersType.telematics)
    mon_petit_carrossier = Supplier('MON_PETIT_CARROSSIER', SuppliersType.maintenance)
    smabtp = Supplier('SMABTP', SuppliersType.insurance)
    audi = Supplier('AUDI', SuppliersType.manufacturer)
    free2move = Supplier('FREE2MOVE', SuppliersType.lld)
    total = Supplier('TOTAL', SuppliersType.fuel)
    ad_carrosserie = Supplier('AD_CARROSSERIE', SuppliersType.maintenance)
    sas_auto_sprinter = Supplier('SAS_AUTO_SPRINTER', SuppliersType.maintenance)
    speedy = Supplier('SPEEDY', SuppliersType.maintenance)
    parcours = Supplier('PARCOURS', SuppliersType.lld)
    pay_by_phone = Supplier('PAY_BY_PHONE', SuppliersType.parking)
    q_park = Supplier('Q-PARK', SuppliersType.parking)
    theoreme = Supplier('THEOREME', SuppliersType.insurance)
    garage_de_la_justice = Supplier('GARAGE_DE_LA_JUSTICE', SuppliersType.maintenance)
    sambms = Supplier('SAMBMS', SuppliersType.lld)
    leasygo = Supplier('LEASYGO', SuppliersType.lld)
    gca = Supplier('GCA', SuppliersType.car_dealer)
    leaseplan = Supplier('LEASEPLAN', SuppliersType.lld)
    norauto = Supplier('NORAUTO', SuppliersType.maintenance)
    car_center_services = Supplier('CAR CENTER SERVICES', SuppliersType.maintenance)
    atelier_ets = Supplier('ATELIER_ETS', SuppliersType.maintenance)
    zeplug = Supplier('ZEPLUG', SuppliersType.charging_points)
    unknown_finance = Supplier('UNKNOWN_FINANCE', SuppliersType.finance)
    unknown_lld = Supplier('UNKNOWN_LLD', SuppliersType.lld)
    banque_populaire = Supplier('BANQUE_POPULAIRE', SuppliersType.finance)
    cic = Supplier('CIC', SuppliersType.finance)
    cofica = Supplier('COFICA', SuppliersType.finance)
    lixxbail = Supplier('LIXXBAIL', SuppliersType.finance)
    toyota_lease = Supplier('TOYOTA_LEASE', SuppliersType.lld)
    edenred = Supplier('EDENRED', SuppliersType.fuel)
    flease = Supplier('FLEASE', SuppliersType.lld)
    yooliz = Supplier('YOOLIZ', SuppliersType.lld)
    volkswagen_bank = Supplier('VOLKSWAGEN BANK', SuppliersType.finance)
    p_lease = Supplier('P LEASE', SuppliersType.lld)
    automobile_leman = Supplier('AUTOMOBILE DU LEMAN', SuppliersType.car_dealer)
    auto_guadeloup = Supplier('AUTO-GUADELOUP Pointe à Pitre', SuppliersType.car_dealer)
    diac = Supplier('DIAC Location', SuppliersType.lld)
    leasys = Supplier('LEASYS', SuppliersType.lld)
    by_my_car = Supplier('BYmyCAR', SuppliersType.car_dealer)
    volkswagen = Supplier('VOLKSWAGEN', SuppliersType.manufacturer)
    satec = Supplier('SATEC', SuppliersType.insurance)
    quartus = Supplier('QUARTUS', SuppliersType.other)
    sogelease = Supplier('SOGELEASE', SuppliersType.finance)
    alliance_esdb = Supplier('ALLIANCE_ESDB', SuppliersType.car_dealer)
    sofinco = Supplier('SOFINCO', SuppliersType.finance)
    leasecar = Supplier('LEASECAR', SuppliersType.lld)
    volvo = Supplier('VOLVO', SuppliersType.manufacturer)
    pcaservices = Supplier('PCA_SERVICES', SuppliersType.lld)
    hyundai = Supplier('HYUNDAI', SuppliersType.manufacturer)
    flexilease = Supplier('FLEXILEASE', SuppliersType.lld)
    leaseway = Supplier('LEASEWAY', SuppliersType.lld)
    shell = Supplier('SHELL', SuppliersType.fuel)
    first_stop = Supplier('FIRST_STOP', SuppliersType.maintenance)
    viasso = Supplier('VIASSO', SuppliersType.maintenance)
    autosphere = Supplier('AUTOSPHERE', SuppliersType.lld)
    nge = Supplier('NGE', SuppliersType.parking)
    en_cargo_simone = Supplier('EN_CARGO_SIMONE', SuppliersType.parking)
    credipar = Supplier('CREDIPAR', SuppliersType.finance)
    meia = Supplier('MEIA', SuppliersType.finance)
    jugand = Supplier('JUGAND LOCATION', SuppliersType.car_dealer)
    kinto = Supplier('KINTO', SuppliersType.lld)
    jean_lain = Supplier('JEAN LAIN', SuppliersType.car_dealer)
    cgi = Supplier('CGI', SuppliersType.other)
    ford = Supplier('FORD', SuppliersType.manufacturer)
    dlm = Supplier('DLM', SuppliersType.lld)
    smelvi = Supplier('SMELVI', SuppliersType.lld)
    cargo = Supplier('CARGO', SuppliersType.lld)
    john_deere = Supplier('JOHN DEERE', SuppliersType.manufacturer)
    hopper = Supplier('HOPPER', SuppliersType.lld)
    somelac = Supplier('SOMELAC', SuppliersType.lld)
    petit_forestier = Supplier('PETIT FORESTIER', SuppliersType.lld)
    peugeot = Supplier('PEUGEOT', SuppliersType.manufacturer)
    toyota = Supplier('TOYOTA', SuppliersType.manufacturer)
    renault = Supplier('RENAULT', SuppliersType.manufacturer)
    kia = Supplier('KIA', SuppliersType.manufacturer)

    @classmethod
    def mapping(cls):
        return {
            "NATIXIS": cls.bpce.value.name,
            "Audi Bauer PARIS": cls.audi.value.name,
            "Free2Move": cls.free2move.value.name,
            "Speedy": cls.speedy.value.name,
            "Parcours": cls.parcours.value.name,
            "ALD Automotive": cls.ayvens.value.name,
            "ALD AUTOMOTIVE": cls.ayvens.value.name,
            "GCA NANTES": cls.gca.value.name,
            "Norauto": cls.norauto.value.name,
            "Atelier ET&S Grenoble": cls.atelier_ets.value.name,
            "Arval": cls.arval.value.name,
            "Athlon": cls.athlon.value.name,
            "Autres Financeurs LOA": cls.unknown_finance.value.name,
            "Autres LLD": cls.unknown_lld.value.name,
            "BANQUE POPULAIRE": cls.banque_populaire.value.name,
            "CM CIC BAIL": cls.cic.value.name,
            "COFICA Bail": cls.cofica.value.name,
            "LeasePlan": cls.leaseplan.value.name,
            "LixxBail": cls.lixxbail.value.name,
            "Loc-Action": cls.leaseplan.value.name,
            "Toyota lease": cls.toyota_lease.value.name,
            "PAY BY PHONE": cls.pay_by_phone.value.name,
            "SMA BTP": cls.smabtp.value.name,
            "ARVAL LLD": cls.arval.value.name,
            "ATHLON CAR LEASE": cls.athlon.value.name,
            "Edenred": cls.edenred.value.name,
            "FLEASE": cls.flease.value.name,
            "YOOLIZ": cls.yooliz.value.name,
            "VOLKSWAGEN BANK": cls.volkswagen_bank.value.name,
            "P LEASE": cls.p_lease.value.name,
            "AUTOMOBILE DU LEMAN": cls.automobile_leman.value.name,
            "AUTO-GUADELOUP Pointe à Pitre": cls.auto_guadeloup.name,
            "DIAC Location": cls.diac.value.name,
            "LEASYS": cls.leasys.value.name,
            "BYmyCAR": cls.by_my_car.value.name,
            "GARAGE DE LA JUSTICE": cls.garage_de_la_justice.value.name,
            "AD CARROSSERIE": cls.ad_carrosserie.value.name,
            "SAS Auto Sprinter": cls.sas_auto_sprinter.value.name,
            "DIAC": cls.diac.value.name,
            "NC": cls.unknown_lld.value.name,
            "VW group fleet solutions": cls.volkswagen.value.name,
            "ARVAL FLEET SERVICES": cls.arval.value.name,
            "Autres LCD": cls.unknown_lld.value.name,
            "VW BANK": cls.volkswagen_bank.value.name,
            "SATEC": cls.satec.value.name,
            "alliance esdb saint-germain-en-laye": cls.alliance_esdb.value.name,
            "leaseplan / temsys": cls.leaseplan.value.name,
            "tesla / viaxel (ca consumer finance) / sofinco": cls.sofinco.value.name,
            "leasecar": cls.leasecar.value.name,
            "pcaservices": cls.pcaservices.value.name,
            "flexi lease": cls.flexilease.value.name,
            "first stop": cls.first_stop.value.name,
            "viasso": cls.viasso.value.name,
            "free2move lease": cls.free2move.value.name,
            "arval uk": cls.arval.value.name,
            "ayvens (myleasing)": cls.ayvens.value.name,
            "diac location/lease&co": cls.diac.value.name,
            "free2movelease (peugeot)": cls.free2move.value.name,
            "autosphere lease": cls.autosphere.value.name,
            "CREDIPAR / FREE2MOVE": cls.free2move.value.name,
            "BPCE CAR LEASE": cls.bpce.value.name,
            "LEASYS France": cls.leasys.value.name,
            "CREDIPAR": cls.credipar.value.name,
            "VOLVO CAR FLEET": cls.volvo.value.name,
            "meia/cofinance (vw)": cls.meia.value.name,
            "jugand location": cls.jugand.value.name,
            "vw bank - jean - lain": cls.volkswagen_bank.value.name,
            "fmd": None,
            "ayvens ( ald)": cls.ayvens.value.name,
            "kinto one": cls.kinto.value.name,
            "kinto": cls.kinto.value.name,
            "jean lain": cls.jean_lain.value.name,
            "bp aura": cls.banque_populaire.value.name,
            "jean lain rent": cls.jean_lain.value.name,
            "cgi": cls.cgi.value.name,
            "ald": cls.ayvens.value.name,
            "ayvens - flex": cls.ayvens.value.name,
            "arval - public": cls.arval.value.name,
            "toyota financement": cls.toyota_lease.value.name,
            "wolkswagen bank": cls.volkswagen_bank.value.name,
            "avens (ald)": cls.ayvens.value.name,
            "ald flex": cls.ayvens.value.name,
            "ayvens flex": cls.ayvens.value.name,
            "societe du parc du futuroscope": None,
            "toyota financial services": cls.toyota_lease.value.name,
            "ayvens (ald)": cls.ayvens.value.name,
            "temsys": cls.ayvens.value.name,
            "cm-cic bail": cls.cic.value.name,
            "volksagen bank": cls.volkswagen_bank.value.name,
            "free 2 move lease": cls.free2move.value.name,
            "kinto france": cls.kinto.value.name,
            "bremany": cls.ford.value.name,
            "arval flex": cls.arval.value.name,
            "hyundai leasing": cls.hyundai.value.name,
            "ayvensflex": cls.ayvens.value.name,
            "dlm": cls.dlm.value.name,
            "smelvi": cls.smelvi.value.name,
            "cargo": cls.cargo.value.name,
            "viaxel": cls.sofinco.value.name,
            "cic leasing": cls.cic.value.name,
            "mobilize lease &co": cls.diac.value.name,
            "john deer financial": cls.john_deere.value.name,
            "jugand": cls.jugand.value.name,
            "hopper": cls.hopper.value.name,
            "toyota financial et services": cls.toyota_lease.value.name,
            "créditpar (citroën)": cls.credipar.value.name,
            "407": None,
            "free move": cls.free2move.value.name,
            "arval phh (bnp)": cls.arval.value.name,
            "kia lease": cls.kia.value.name,
            "bpce lease": cls.bpce.value.name,
            "prioris": cls.bpce.value.name,
            'arval service lease': cls.arval.value.name,
        }

    @classmethod
    def map_type(cls):
        return {
            "NATIXIS": cls.bpce.value.type,
            "Audi Bauer PARIS": cls.audi.value.type,
            "Free2Move": cls.free2move.value.type,
            "Speedy": cls.speedy.value.type,
            "Parcours": cls.parcours.value.type,
            "ALD Automotive": cls.ayvens.value.type,
            "ALD AUTOMOTIVE": cls.ayvens.value.type,
            "GCA NANTES": cls.gca.value.type,
            "Norauto": cls.norauto.value.type,
            "Atelier ET&S Grenoble": cls.atelier_ets.value.type,
            "Arval": cls.arval.value.type,
            "Athlon": cls.athlon.value.type,
            "Autres Financeurs LOA": cls.unknown_finance.value.type,
            "Autres LLD": cls.unknown_lld.value.type,
            "BANQUE POPULAIRE": cls.banque_populaire.value.type,
            "CM CIC BAIL": cls.cic.value.type,
            "COFICA Bail": cls.cofica.value.type,
            "LeasePlan": cls.leaseplan.value.type,
            "LixxBail": cls.lixxbail.value.type,
            "Loc-Action": cls.leaseplan.value.type,
            "Toyota lease": cls.toyota_lease.value.type,
        }


class TransmissionTypes(Enum):
    manual = "MANUAL"
    automatic = "AUTOMATIC"
    sequential = "SEQUENTIAL"
    continuous = "CONTINUOUS"
    manual_automated = "MANUAL_AUTOMATED"

    @classmethod
    def mapping(cls):
        return {
            "Manuelle": cls.manual.value,
            "Automatique": cls.automatic.value,
            "automatique": cls.automatic.value,
            "manuel": cls.manual.value,
            "auto": cls.automatic.value,
            "M": cls.manual.value,
            "A": cls.automatic.value,
            "S": cls.sequential.value,
            'cvt': cls.continuous.value,
        }


class Civility(Enum):
    mr = "Mr"
    ms = "Ms"

    @classmethod
    def mapping(cls):
        return {
            "M.": cls.mr.value,
            "Mme": cls.ms.value,
            "Ms": cls.ms.value,
            "Mr": cls.mr.value,
            "m": cls.mr.value,
            "mlle": cls.ms.value,
        }


class MaintenanceType(Enum):
    oil_change = "OIL_CHANGE"
    tire_change = "TIRE_CHANGE"
    brake_change = "BRAKE_CHANGE"
    battery_change = "BATTERY_CHANGE"
    periodic_technical_inspection = "PERIODIC_TECHNICAL_INSPECTION"
    technical_inspection = "TECHNICAL_INSPECTION"
    pollution_control = "POLLUTION_CONTROL"

    @classmethod
    def mapping(cls):
        return {
            "VIDANGE": cls.oil_change.value,
            "Changement de pneus": cls.tire_change.value,
            "Changement de freins": cls.brake_change.value,
            "Changement de batterie": cls.battery_change.value,
            "contrôle technique": cls.technical_inspection.value,
        }


class FrenchLicencePlace(Enum):
    ain = "Bourg en Bresse"
    aisne = "Laon"
    allier = "Moulins"
    alpes_de_ht_provence = "Digne les Bains"
    hautes_alptes = "Gap"
    alpes_maritime = "Nice"
    ardeche = "Privas"
    ardennes = "Charleville Mezières"
    ariege = "Foix"
    aube = "Troyes"
    aude = "Carcassonne"
    aveyron = "Rodez"
    bouche_du_rhone = "Marseille"
    calvados = "Caen"
    cantal = "Aurillac"
    charente = "Angoulême"
    charente_maritime = "La Rochelle"
    cher = "Bourges"
    correze = "Tulle"
    corse_du_sud = "Ajaccio"
    haute_corse = "Bastia"
    cote_or = "Dijon"
    cote_armor = "Saint Brieuc"
    creuse = "Gueret"
    dordogne = "Perigueux"
    doubs = "Besançon"
    drome = "Valence"
    eure = "Evreux"
    eure_loire = "Chartres"
    finistere = "Quimper"
    gard = "Nîmes"
    ht_garonne = "Toulouse"
    gers = "Auch"
    gironde = "Bordeaux"
    herault = "Montpellier"
    ille_vilaine = "Rennes"
    indre = "Châteauroux"
    indre_loire = "Tours"
    isere = "Grenoble"
    jura = "Lons le Saunier"
    landes = "Mont de Marsan"
    loire_cher = "Blois"
    loire = "Saint Etienne"
    ht_loire = "Le Puy en Velay"
    loire_atlantique = "Nantes"
    loiret = "Orleans"
    lot = "Cahors"
    lot_garonne = "Agen"
    lozere = "Mende"
    maine_loire = "Angers"
    manche = "Saint Lô"
    marne = "Châlons en Champagne"
    ht_marne = "Chaumont"
    mayenne = "Laval"
    meurthe = "Nancy"
    meuse = "Bar le Duc"
    morbihan = "Vannes"
    moselle = "Metz"
    nievre = "Nevers"
    nord = "Lille"
    oise = "Beauvais"
    orne = "Alençon"
    pas_calais = "Arras"
    puy_dome = "Clermont Ferrand"
    pyrenee_atlantique = "Pau"
    ht_pyrenee = "Tarbes"
    pyrenee_orientale = "Perpignan"
    bas_rhin = "Strasbourg"
    ht_rhin = "Colmar"
    rhone = "Lyon"
    ht_saone = "Vesoul"
    saone_loire = "Mâcon"
    sartre = "Le Mans"
    savoie = "Chambery"
    ht_savoie = "Annecy"
    paris = "Paris"
    seine_maritime = "Rouen"
    seine_marne = "Melun"
    yvelines = "Versailles"
    deux_sevres = "Niort"
    somme = "Amiens"
    tarn = "Albi"
    tarn_garonne = "Montauban"
    var = "Toulon"
    vaucluse = "Avignon"
    vendee = "La Roche sur Yon"
    vienne = "Poitiers"
    ht_vienne = "Limoges"
    vosges = "Epinal"
    yonne = "Auxerre"
    territoire_belfort = "Belfort"
    essonne = "Evry Courcouronnes"
    ht_seine = "Nanterre"
    seine_st_denis = "Bobigny"
    val_marne = "Creteil"
    val_oise = "Cergy"
    guadeloupe = "Basse Terre"
    martinique = "Fort de France"
    guyane = "Cayenne"
    reunion = "Saint Denis"
    mayotte = "Mamoudzou"

    @classmethod
    def mapping(cls):
        return {
            "01": cls.ain.value,
            "02": cls.aisne.value,
            "03": cls.allier.value,
            "04": cls.alpes_de_ht_provence.value,
            "05": cls.hautes_alptes.value,
            "06": cls.alpes_maritime.value,
            "07": cls.ardeche.value,
            "08": cls.ardennes.value,
            "09": cls.ariege.value,
            "10": cls.aube.value,
            "11": cls.aude.value,
            "12": cls.aveyron.value,
            "13": cls.bouche_du_rhone.value,
            "14": cls.calvados.value,
            "15": cls.cantal.value,
            "16": cls.charente.value,
            "17": cls.charente_maritime.value,
            "18": cls.cher.value,
            "19": cls.correze.value,
            "2A": cls.corse_du_sud.value,
            "2B": cls.haute_corse.value,
            "21": cls.cote_or.value,
            "22": cls.cote_armor.value,
            "23": cls.creuse.value,
            "24": cls.dordogne.value,
            "25": cls.doubs.value,
            "26": cls.drome.value,
            "27": cls.eure.value,
            "28": cls.eure_loire.value,
            "29": cls.finistere.value,
            "30": cls.gard.value,
            "31": cls.ht_garonne.value,
            "32": cls.gers.value,
            "33": cls.gironde.value,
            "34": cls.herault.value,
            "35": cls.ille_vilaine.value,
            "36": cls.indre.value,
            "37": cls.indre_loire.value,
            "38": cls.isere.value,
            "39": cls.jura.value,
            "40": cls.landes.value,
            "41": cls.loire_cher.value,
            "42": cls.loire.value,
            "43": cls.ht_loire.value,
            "44": cls.loire_atlantique.value,
            "45": cls.loiret.value,
            "46": cls.lot.value,
            "47": cls.lot_garonne.value,
            "48": cls.lozere.value,
            "49": cls.maine_loire.value,
            "50": cls.manche.value,
            "51": cls.marne.value,
            "52": cls.ht_marne.value,
            "53": cls.mayenne.value,
            "54": cls.meurthe.value,
            "55": cls.meuse.value,
            "56": cls.morbihan.value,
            "57": cls.moselle.value,
            "58": cls.nievre.value,
            "59": cls.nord.value,
            "60": cls.oise.value,
            "61": cls.orne.value,
            "62": cls.pas_calais.value,
            "63": cls.puy_dome.value,
            "64": cls.pyrenee_atlantique.value,
            "65": cls.ht_pyrenee.value,
            "66": cls.pyrenee_orientale.value,
            "67": cls.bas_rhin.value,
            "68": cls.ht_rhin.value,
            "69": cls.rhone.value,
            "70": cls.ht_saone.value,
            "71": cls.saone_loire.value,
            "72": cls.sartre.value,
            "73": cls.savoie.value,
            "74": cls.ht_savoie.value,
            "75": cls.paris.value,
            "76": cls.seine_maritime.value,
            "77": cls.seine_marne.value,
            "78": cls.yvelines.value,
            "79": cls.deux_sevres.value,
            "80": cls.somme.value,
            "81": cls.tarn.value,
            "82": cls.tarn_garonne.value,
            "83": cls.var.value,
            "84": cls.vaucluse.value,
            "85": cls.vendee.value,
            "86": cls.vienne.value,
            "87": cls.ht_vienne.value,
            "88": cls.vosges.value,
            "89": cls.yonne.value,
            "90": cls.territoire_belfort.value,
            "91": cls.essonne.value,
            "92": cls.ht_seine.value,
            "93": cls.seine_st_denis.value,
            "94": cls.val_marne.value,
            "95": cls.val_oise.value,
            "971": cls.guadeloupe.value,
            "972": cls.martinique.value,
            "973": cls.guyane.value,
            "974": cls.reunion.value,
            "976": cls.mayotte.value,
            "Ain": cls.ain.value,
            "Aisne": cls.aisne.value,
            "Allier": cls.allier.value,
            "Alpes de Haute Provence": cls.alpes_de_ht_provence.value,
            "Hautes Alpes": cls.hautes_alptes.value,
            "Alpes Maritimes": cls.alpes_maritime.value,
            "Ardèche": cls.ardeche.value,
            "Ardennes": cls.ardennes.value,
            "Ariège": cls.ariege.value,
            "Aube": cls.aube.value,
            "Aude": cls.aude.value,
            "Aveyron": cls.aveyron.value,
            "Bouches du Rhône": cls.bouche_du_rhone.value,
            "Calvados": cls.calvados.value,
            "Cantal": cls.cantal.value,
            "Charente": cls.charente.value,
            "Charente Maritime": cls.charente_maritime.value,
            "Cher": cls.cher.value,
            "Corrèze": cls.correze.value,
            "Corse du Sud": cls.corse_du_sud.value,
            "Haute Corse": cls.haute_corse.value,
            "Côte d'Or": cls.cote_or.value,
            "Côtes d'Armor": cls.cote_armor.value,
            "Creuse": cls.creuse.value,
            "Dordogne": cls.dordogne.value,
            "Doubs": cls.doubs.value,
            "Drôme": cls.drome.value,
            "Eure": cls.eure.value,
            "Eure et Loir": cls.eure_loire.value,
            "Finistère": cls.finistere.value,
            "Gard": cls.gard.value,
            "Haute Garonne": cls.ht_garonne.value,
            "Gers": cls.gers.value,
            "Gironde": cls.gironde.value,
            "Hérault": cls.herault.value,
            "Ille et Vilaine": cls.ille_vilaine.value,
            "Indre": cls.indre.value,
            "Indre et Loire": cls.indre_loire.value,
            "Isère": cls.isere.value,
            "Jura": cls.jura.value,
            "Landes": cls.landes.value,
            "Loir et Cher": cls.loire_cher.value,
            "Loire": cls.loire.value,
            "Haute Loire": cls.ht_loire.value,
            "Loire Atlantique": cls.loire_atlantique.value,
            "Loiret": cls.loiret.value,
            "Lot": cls.lot.value,
            "Lot et Garonne": cls.lot_garonne.value,
            "Lozère": cls.lozere.value,
            "Maine et Loire": cls.maine_loire.value,
            "Manche": cls.manche.value,
            "Marne": cls.marne.value,
            "Haute Marne": cls.ht_marne.value,
            "Mayenne": cls.mayenne.value,
            "Meurthe et Moselle": cls.meurthe.value,
            "Meuse": cls.meuse.value,
            "Morbihan": cls.morbihan.value,
            "Moselle": cls.moselle.value,
            "Nièvre": cls.nievre.value,
            "Nord": cls.nord.value,
            "Oise": cls.oise.value,
            "Orne": cls.orne.value,
            "Pas de Calais": cls.pas_calais.value,
            "Puy de Dôme": cls.puy_dome.value,
            "Pyrénées Atlantiques": cls.pyrenee_atlantique.value,
            "Hautes Pyrénées": cls.ht_pyrenee.value,
            "Pyrénées Orientales": cls.pyrenee_orientale.value,
            "Bas Rhin": cls.bas_rhin.value,
            "Haut Rhin": cls.ht_rhin.value,
            "Rhône": cls.rhone.value,
            "Haute Saône": cls.ht_saone.value,
            "Saône et Loire": cls.saone_loire.value,
            "Sarthe": cls.sartre.value,
            "Savoie": cls.savoie.value,
            "Haute Savoie": cls.ht_savoie.value,
            "Paris": cls.paris.value,
            "Seine Maritime": cls.seine_maritime.value,
            "Seine et Marne": cls.seine_marne.value,
            "Yvelines": cls.yvelines.value,
            "Deux Sèvres": cls.deux_sevres.value,
            "Somme": cls.somme.value,
            "Tarn": cls.tarn.value,
            "Tarn et Garonne": cls.tarn_garonne.value,
            "Var": cls.var.value,
            "Vaucluse": cls.vaucluse.value,
            "Vendée": cls.vendee.value,
            "Vienne": cls.vienne.value,
            "Haute Vienne": cls.ht_vienne.value,
            "Vosges": cls.vosges.value,
            "Yonne": cls.yonne.value,
            "Territoire de Belfort": cls.territoire_belfort.value,
            "Essonne": cls.essonne.value,
            "Hauts de Seine": cls.ht_seine.value,
            "Seine Saint Denis": cls.seine_st_denis.value,
            "Val de Marne": cls.val_marne.value,
            "Val d'Oise": cls.val_oise.value,
            "Guadeloupe": cls.guadeloupe.value,
            "Martinique": cls.martinique.value,
            "Guyane": cls.guyane.value,
            "La Réunion": cls.reunion.value,
            "Mayotte": cls.mayotte.value,
        }

    @classmethod
    def match_place(cls, logger: logging.Logger, place_series: pd.Series) -> pd.Series:
        place_series = (
            place_series.str.replace(
                "-",
                " ",
                case=False,
            )
            .str.replace(
                "é",
                "e",
            )
            .str.replace(
                r"c?\.?l?e? ?(?:sous ?)?(?:pref|pre?fe?tu?r?e?) ?\.?(?: ?de ?)?(?:la?e?\'? ?)?",
                "",
                case=False,
                regex=True,
            )
            .str.strip()
        )
        was_matched = pd.Series(False, index=place_series.index)
        for value in cls:
            criterion = place_series.str.contains(
                value.value,
                case=False,
                regex=False,
            ).fillna(False)
            was_matched |= criterion
            place_series = place_series.mask(criterion, value.value)
        for key, value in cls.mapping().items():
            criterion = place_series.str.match(
                r"(?:.*\b|^)" + key + r"(?:\b.*|$)",
                case=False,
            ).fillna(False)
            was_matched |= criterion
            place_series = place_series.mask(criterion, value)
        places_not_matched = place_series[~was_matched].unique()
        logger.info(f"{len(places_not_matched)} Places not matched: {places_not_matched}")

        return place_series.where(was_matched, pd.NA)


@unique
class ScoreType(UpperStrEnum):
    SMOOTH = auto()
    SAFE = auto()
    CLEAN = auto()

    @classmethod
    def mapping(cls):
        return {
            "smooth": cls.SMOOTH.value,
            "safe": cls.SAFE.value,
            "clean": cls.CLEAN.value,
        }


@unique
class DocumentType(UpperStrEnum):
    CAR_REGISTRATION_DOCUMENT = auto()
    CERTIFICATE_OF_INSURANCE = auto()
    CONTROL_BILL = auto()
    DELIVERY_INSPECTION_REPORT = auto()
    DRIVER_CHARTER = auto()
    DRIVING_LICENCE = auto()
    EXPERTISE_REPORT = auto()
    ID_CARD = auto()
    INSPECTION_REPORT = auto()
    ORDER_FORM = auto()
    OTHER_COLLABORATOR = auto()
    OTHER_VEHICLE = auto()
    PHOTO = auto()
    PURCHASE_INVOICE = auto()
    QUOTE = auto()
    RENTAL_CONTRACT = auto()
    REPORT = auto()
    RETURN_REPORT = auto()
    TRANSFER_CONTRACT = auto()
    VEHICLE_PICTURE = auto()

    @classmethod
    def mapping(cls):
        return {
            "report": cls.RETURN_REPORT.value,
        }
