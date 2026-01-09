""" Generate KPIs

Script to generate KPIs, as a list of json, to insert into the WebApp.
First list kpi names, units, descriptions, and expense category
Then generate jsons
"""
import json
import os
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import List, Optional, Self, Type, Union

from utils.enums import CostCategory, ExpenseType, TravelTypes

SOCIAL_SECURITY_TAX_RATE = 0.48
CORPORATE_TAX_RATE = 0.25
IKB_METRIC = 'ikb_calculated_final'
NDA_METRIC = 'calculated_non_deduc_amortization'

NAME_DICT = {
    'TCO': 'TCO',
    'TCM': 'TCM',
    'energy_total': 'Total dépenses énergies',
    CostCategory.financial_rent.value: 'Loyer financier',
    CostCategory.rent_management_fees.value: 'Loyer frais de gestion',
    CostCategory.rent_maintenance.value: 'Loyer maintenance',
    CostCategory.rent_telematic.value: 'Loyer télématique',
    CostCategory.rent_insurance.value: 'Loyer assurance',
    CostCategory.rent_fuel_card.value: 'Loyer carte carburant',
    CostCategory.rent_financial_loss.value: 'Loyer perte financière',
    CostCategory.rent_replacement_vehicle_actual.value: (
        'Loyer véhicule de remplacement au réel'
    ),
    CostCategory.rent_replacement_vehicle_flat_fee.value: (
        'Loyer forfait véhicule de remplacement'
    ),
    CostCategory.rent_others.value: 'Loyer autres',
    CostCategory.insurance_vehicle.value: 'Assurance véhicule',
    CostCategory.insurance_replacement_vehicle.value: (
        'Assurance véhicule de remplacement'
    ),
    CostCategory.insurance_assistance.value: 'Assurance assistance',
    CostCategory.insurance_financial_loss.value: 'Assurance perte financière',
    CostCategory.insurance_glass.value: 'Assurance bris de glace',
    CostCategory.insurance_brokerage_cost.value: 'Assurance frais de courtage',
    CostCategory.insurance_deductible_cost.value: 'Frais de franchise',
    'SELF_INSURANCE': 'Auto-assurance',
    'INSURER_COST': 'Coût assureur',
    CostCategory.fuel_cost.value: 'Coût carburant',
    CostCategory.real_fuel_card.value: 'Coût abonnement carte carburant',
    CostCategory.electricity_cost.value: 'Coût électricité',
    CostCategory.real_adblue.value: 'Coût Adblue',
    CostCategory.fines.value: 'Amendes',
    CostCategory.environmental_bonus.value: 'Bonus environnemental',
    CostCategory.environmental_malus.value: 'Malus environmental',
    'ikb_no_fuel_purchase_based': (
        "Avantage en nature - essence non incluse, base prix d'achat"
    ),
    'ikb_inc_fuel_purchase_based': (
        "Avantage en nature - essence comprise, base prix d'achat"
    ),
    'ikb_no_fuel_expense_based': (
        "Avantage en nature - essence non incluse, base dépenses"
    ),
    'ikb_inc_fuel_expense_based': (
        "Avantage en nature - essence comprise, base dépenses"
    ),
    'ikb_calculated_final': 'Avantage en nature calculé',
    'ikb_no_fuel_purchase_based_taxes': (
        "Taxes avantage en nature - essence non incluses, base prix d'achat"
    ),
    'ikb_inc_fuel_purchase_based_taxes': (
        "Taxes avantage en nature - essence comprise, base prix d'achat"
    ),
    'ikb_no_fuel_expense_based_taxes': (
        "Taxes avantage en nature - essence non incluses, base dépenses"
    ),
    'ikb_inc_fuel_expense_based_taxes': (
        "Taxes avantage en nature - essence comprise, base dépenses"
    ),
    'ikb_calculated_final_taxes': 'Taxes avantage en nature calculé',
    'participation': 'Participation',
    'declared_non_deduc_amortization': 'Amortissement non déductible déclaré',
    'calculated_non_deduc_amortization': (
        'Amortissement non déductible calculé'
    ),
    'calculated_non_deduc_amortization_taxes': (
        'Taxes amortissement non déductible calculées'
    ),
    'taxes_total': 'Fiscalité - totale',
    CostCategory.real_replacement_vehicle_cost.value: (
        'Coût au réel véhicule de remplacement'
    ),
    CostCategory.real_short_term_rental.value: 'Coût location à court terme',
    CostCategory.real_relay_vehicle_cost.value: 'Coût au réel voiture relais',
    CostCategory.real_medium_term_rental.value: 'Coût location à moyen terme',
    CostCategory.rent_end_of_year.value: "Coût remise de fin d'année",
    CostCategory.real_maintenance.value: 'Coût de maintenance au réel',
    CostCategory.real_telematics_fee.value: 'Coût de télématique au réel',
    CostCategory.real_telematics_install.value: (
        "Coût d'installation de télématique au réel"
    ),
    CostCategory.real_tires_summer.value: 'Coûts pneus été',
    CostCategory.real_tires_winter.value: 'Coûts pneus hiver',
    CostCategory.real_tires_other.value: 'Coûts pneus autres',
    CostCategory.real_glass.value: 'Coûts bris de glace',
    CostCategory.real_assistance.value: 'Coût assistance au réel',
    CostCategory.real_restitution.value: 'Coût de restitution',
    CostCategory.real_others.value: "Autres frais à l'acte",
    CostCategory.tolls_card.value: 'Coût cartes de péages',
    CostCategory.tolls_real.value: 'Coût péages au réel',
    CostCategory.parking_card.value: 'Coût abonnement carte parking',
    CostCategory.parking_real.value: 'Coût parking au réel',
    CostCategory.washing_card.value: 'Coût carte de lavage',
    CostCategory.washing_real.value: 'Coût carte de lavage au réel',
    CostCategory.logo.value: 'Coût floccage',
    CostCategory.real_repairs.value: 'Réparations au réel',
    CostCategory.charging_point_installation.value: (
        'Installation de bornes électriques'
    ),
    CostCategory.charging_points_recurring.value: (
        'Coûts abonnement bornes électiques'
    ),
    'claims_' + ExpenseType.fuel.value: 'Note de frais essence',
    'claims_' + ExpenseType.tolls.value: 'Note de frais péage',
    'claims_' + ExpenseType.parking.value: 'Note de frais parking',
    'claims_' + ExpenseType.maintenance.value: 'Note de frais maintenance',
    'claims_' + ExpenseType.mileage_allowance.value: (
        'Note de frais indemnités kilométriques'
    ),
    'claims_' + ExpenseType.taxi.value: 'Note de frais taxi',
    'claims_' + ExpenseType.train.value: 'Note de frais train',
    'claims_' + ExpenseType.plane.value: 'Note de frais avion',
    'travel_' + TravelTypes.air.value + '_distance': (
        'Distance parcourue par avion'
    ),
    'travel_' + TravelTypes.rail.value + '_distance': (
        'Distance parcourue par train'
    ),
    'travel_' + TravelTypes.air.value + '_occurences': 'Nombre de vols',
    'travel_' + TravelTypes.rail.value + '_occurences': (
        'Nombre de trajet en train'
    ),
    'travel_' + 'RENTAL_CARS' + '_occurences': (
        'Nombre de location de voitures'
    ),
    'travel_' + 'HOTELS' + '_occurences': "Nombre de réservations d'hotels",
    'travel_spend' + TravelTypes.air.value: 'Dépense voyages avion',
    'travel_spend' + TravelTypes.rail.value: 'Dépense voyages train',
    'travel_spend' + 'RENTAL_CARS': 'Dépense location de voiture',
    'travel_spend' + 'HOTELS': 'Dépense hotels',
    'travel_' + TravelTypes.air.value + '_anticipation': (
        'Anticipation réservation avion'
    ),
    'travel_' + TravelTypes.rail.value + '_anticipation': (
        'Anticipation réservation train'
    ),
    'travel_' + 'RENTAL_CARS' + '_anticipation': (
        'Anticipation réservation voiture de location'
    ),
    'travel_' + 'HOTELS' + '_anticipation': (
        'Anticipation réservation hôtels'
    ),
    'mileage_driven': 'Kilométres parcourus',
    'total_mileage': 'Kilomètrage total véhicuke',
    'lease_mileage': 'Kilométrage contrat de location',
    'lease_months': 'Nombre de mois contrat de location',
    'CO2_usage': 'CO2 utilisation voiture',
    'CO2_production': 'CO2 production voiture',
    'CO2_recycling': 'CO2 recyclage voiture',
    'CO2_trains': 'CO2 voyages trains',
    'CO2_planes': 'CO2 voyages avions',
    'CO2_rental_cars': 'CO2 voyages voiture de location',
    'CO2_taxi': 'CO2 voyages en taxi',
    'TCO_per_vehicle': 'TCO par véhicule',
    'TCO_per_driver': 'TCO par conducteur',
    'Cost_per_km': 'Prix de revient kilométrique',
    'TCM_collaborators': 'TCM par collaborateur',
    'TCM_users': 'TCM par utilisateur',
    'rent_total': 'Coût total loyer',
    'insurance_total': 'Coût total assurance',
    'travel_total': 'Coût total voyages',
    'travel_cost_per_travel': 'Coût total voyages par voyage',
    'travel_cost_per_travellers': 'Coût total voyages par voyageur',
    'total_CO2_fleet': 'CO2 total flotte',
    'total_CO2_travel': 'CO2 total voyages',
    'total_CO2': 'CO2 total',
    'CO2_per_collaborator': 'CO2 par collaborateur',
    'CO2_fleet_per_driver': 'CO2 flotte par conducteur',
    'CO2_usage_per_driver': "CO2 d'utilisation par conducteur",
    'CO2_production_per_driver': 'CO2 de production par conducteur',
    'CO2_recycling_per_driver': 'CO2 de recyclage par conducteur',
    'CO2_per_km': 'CO2 par kilomètre',
    'CO2_fleet_per_vehicles': 'CO2 de flotte par véhicule',
    'CO2_usage_per_vehicles': "CO2 d'utilisation par véhicule",
    'CO2_production_per_vehicles': "CO2 de production par véhicule",
    'CO2_recycling_per_vehicles': "CO2 de recyclage par véhicule",
    'CO2_travel_per_travellers': "CO2 de voyages par voyageur",
    'CO2_trains_per_travellers': "CO2 de train par voyageur",
    'CO2_planes_per_travellers': "CO2 d'avion par voyageur",
    'CO2_rental_cars_per_travellers': (
        "CO2 de location de voiture par voyageur"
    ),
    'CO2_taxi_per_travellers': "CO2 de taxi par voyageur",
    'CO2_travel_per_travel': "CO2 de voyages par voyage",
    'CO2_trains_per_travel': "CO2 de train par voyage",
    'CO2_planes_per_travel': "CO2 d'avion par vol",
    'CO2_rental_cars_per_travel': "CO2 de location de voiture par location",
}


@unique
class Units(Enum):
    EUR = 'EUR'
    KM = 'KM'
    CO2 = 'kg_CO2'
    CO2_PER_PERSON = 'kg_CO2_PER_PERSON'
    CO2_PER_EVENT = 'kg_CO2_PER_EVENT'
    DAYS = 'DAYS'
    NB_EVENTS = 'NB_EVENTS'
    EUR_PER_PERSON = 'EUR_PER_PERSON'
    EUR_PER_VEHICLE = 'EUR_PER_VEHICLE'
    EUR_PER_KM = 'EUR_PER_KM'
    EUR_PER_EVENT = 'EUR_PER_EVENT'


@unique
class ElementTypes(Enum):
    constant = "constant-primitive"
    CO2_production = "CO2-production-primitive"
    CO2_recycling = "CO2-recycling-primitive"
    CO2_usage = "CO2-usage-primitive"
    expense = "expense-primitive"
    mileage = 'total-mileage-primitive'
    vehicles = 'total-vehicles-primitive'
    drivers = 'total-drivers-primitive'
    collaborators = 'total-collaborators-primitive'
    users = 'total-users-primitive'
    travellers = 'total-travellers-primitive'
    insurance = 'insurance-primitive'
    expense_claims = 'expense-claims-primitive'
    vehicle_price = 'vehicle-price-primitive'
    participation = 'participation-primitive'
    declared_non_deduc_amortization = (
        'declared-non-deduc-amortization-primitive'
    )
    calculated_non_deduc_amortization = (
        'calculated-non-deduc-amortization-primitive'
    )
    ikb_no_fuel_purchase_based = 'ikb_no_fuel_purchase_based-primitive'
    ikb_no_fuel_expense_based = 'ikb_no_fuel_expense_based-primitive'
    ikb_inc_fuel_purchase_based = 'ikb_inc_fuel_purchase_based-primitive'
    ikb_inc_fuel_expense_based = 'ikb_inc_fuel_expense_based-primitive'
    ikb_calculated_final = 'ikb_calculated_final'
    travel_distance = 'travel-distance-primitive'
    travel_expenses = 'travel-expenses-primitive'
    travel_anticipation = 'travel-anticipation-primitive'
    travel_occurences = 'travel-occurences-primitive'
    current_mileage = 'current-mileage-primitive'
    lease_mileage = 'lease-mileage-primitive'
    lease_months = 'lease-months-primitive'
    CO2_trains = 'CO2-trains-primitive'
    CO2_planes = 'CO2-planes-primitive'
    rental_cars_days = 'rental-cars-days-primitive'


@unique
class OperatorTypes(Enum):
    PLUS = '+'
    MINUS = '-'
    MULTIPLY = 'x'
    DIVIDE = '/'


@unique
class KPITypes(Enum):
    TAX_EXC = 'tax_exc'
    DEDUC_VAT = 'deduc_vat'
    NET = 'net'


KPI_CAT_DICT = {
    KPITypes.TAX_EXC.value: 'hors taxes',
    KPITypes.DEDUC_VAT.value: 'TVA déductible',
    KPITypes.NET.value: 'net',
}


@dataclass(kw_only=True)
class Element:
    type: ElementTypes
    value: float = 1

    @property
    def json(self):
        return {
            'type': self.type,
            'value': self.value,
        }


@dataclass(kw_only=True)
class ExpenseElement(Element):
    type: str = field(default=ElementTypes.expense.value, init=False)
    kpi_type: str
    categories: List[CostCategory]

    @property
    def json(self):
        return {
            'type': self.type,
            'value': self.value,
            'kpiType': self.kpi_type,
            'soongoCategories': self.categories,
        }


@dataclass(kw_only=True)
class ExpenseClaimElement(Element):
    type: str = field(default=ElementTypes.expense_claims.value, init=False)
    kpi_type: str
    categories: List[ExpenseType]

    @property
    def json(self):
        return {
            'type': self.type,
            'value': self.value,
            'kpiType': self.kpi_type,
            'soongoCategories': self.categories,
        }


@dataclass(kw_only=True)
class TravelElement(Element):
    type: str
    categories: List[str]

    @property
    def json(self):
        return {
            'type': self.type,
            'value': self.value,
            'travel_category': self.categories,
        }


@dataclass(kw_only=True)
class TravelExpenses(TravelElement):
    kpi_type: str

    @property
    def json(self):
        return {
            'type': self.type,
            'value': self.value,
            'travel_category': self.categories,
            'kpiType': self.kpi_type
        }


@dataclass(kw_only=True)
class InsuranceElement(Element):
    type: str = field(default=ElementTypes.insurance.value, init=False)
    kpi_type: str
    categories: List[str]  # Some not SoonGo Categories

    @property
    def json(self):
        return {
            'type': self.type,
            'value': self.value,
            'kpiType': self.kpi_type,
            'soongoCategories': self.categories,
        }


@dataclass
class Block:
    left: Union[Self, Element]
    right: Optional[Union[Self, Element]] = None
    operator: Optional[OperatorTypes] = None

    @staticmethod
    def get_elem_dict(elem):
        if isinstance(elem, Block):
            elem_dict = {
                'type': 'block',
                'value': elem.json
            }
        else:
            elem_dict = elem.json
        return elem_dict

    @property
    def json(self):
        return_dict = {
            'left': self.get_elem_dict(self.left),
        }

        if self.right:
            return_dict['right'] = {
                'operator': self.operator,
                'element': self.get_elem_dict(self.right),
            }

        return return_dict


kpi_formula_dict = {}


@dataclass
class KPI:
    name: str
    unit: Units
    formula: Block
    kpi_category: str
    description: str = ''

    def __post_init__(self):
        if self.name in kpi_formula_dict:
            raise ValueError(f'KPI with name {self.name} already exists')

        kpi_formula_dict[self.name] = self.formula

    @staticmethod
    def translate_name(name: str) -> str:
        """ Translate name from English to French using NAME_DICT"""
        for kpi_type_name, translated_kpi_type in KPI_CAT_DICT.items():
            if name.endswith(kpi_type_name):
                base_name = name[:len(name)-len(kpi_type_name)-1]
                return NAME_DICT[base_name] + ' ' + translated_kpi_type

        if name.endswith('_taxes'):
            return 'Taxes - ' + NAME_DICT[name[:len(name)-len('_taxes')]]

        return NAME_DICT[name]

    @property
    def json(self):
        return {
            'name': self.translate_name(self.name),
            'unit': self.unit,
            'description': self.description,
            'formula': self.formula.json,
            'kpi_category': self.kpi_category,
        }


def build_kpi_json(
    cost_category_lst: List[CostCategory],
    kpi_category: str,
    prefix: str = '',
    suffix: str = '',
    unit: Units = Units.EUR.value,
    element_class: Type[Element] = ExpenseElement,
    kpi_types: KPITypes = KPITypes,
    **add_elem_kwargs,
) -> List[KPI]:
    if kpi_types:
        return [
            KPI(
                name=prefix + expense_kpi + '_' + kpi_type.value + suffix,
                unit=unit,
                formula=Block(
                    left=element_class(
                        kpi_type=kpi_type.value,
                        categories=[expense_kpi],
                        **add_elem_kwargs,
                    ),
                ),
                kpi_category=kpi_category + ' ' + KPI_CAT_DICT[kpi_type.value],
            ).json
            for expense_kpi in cost_category_lst
            for kpi_type in kpi_types
        ]
    else:
        return [
            KPI(
                name=prefix + expense_kpi + suffix,
                unit=unit,
                formula=Block(
                    left=element_class(
                        categories=[expense_kpi],
                        **add_elem_kwargs,
                    ),
                ),
                kpi_category=kpi_category,
            ).json
            for expense_kpi in cost_category_lst
        ]


if __name__ == '__main__':
    kpi_lst = []

    kpi_lst += build_kpi_json(
        cost_category_lst=[
            CostCategory.financial_rent.value,
            CostCategory.rent_management_fees.value,
            CostCategory.rent_maintenance.value,
            CostCategory.rent_telematic.value,
            CostCategory.rent_insurance.value,
            CostCategory.rent_fuel_card.value,
            CostCategory.rent_financial_loss.value,
            CostCategory.rent_replacement_vehicle_actual.value,
            CostCategory.rent_replacement_vehicle_flat_fee.value,
            CostCategory.rent_others.value,
        ],
        kpi_category='Coût > Flotte > Loyers',
    )

    kpi_lst += build_kpi_json(
        cost_category_lst=[
            CostCategory.insurance_vehicle.value,
            CostCategory.insurance_replacement_vehicle.value,
            CostCategory.insurance_assistance.value,
            CostCategory.insurance_financial_loss.value,
            CostCategory.insurance_glass.value,
            CostCategory.insurance_brokerage_cost.value,
            CostCategory.insurance_deductible_cost.value,
        ],
        kpi_category='Coût > Flotte > Assurances',
    )

    kpi_lst += build_kpi_json(
        cost_category_lst=[
            'SELF_INSURANCE',
            'INSURER_COST'
        ],
        kpi_category='Coût > Flotte > Assurances',
        element_class=InsuranceElement,
    )

    kpi_lst += build_kpi_json(
        cost_category_lst=[
            CostCategory.fuel_cost.value,
            CostCategory.real_fuel_card.value,
            CostCategory.electricity_cost.value,
            CostCategory.real_adblue.value,
        ],
        kpi_category='Coût > Flotte > Energies',
    )

    list_tax_cat = [
        CostCategory.fines.value,
        CostCategory.environmental_bonus.value,
        CostCategory.environmental_malus.value,
    ]
    kpi_lst += [
        KPI(
            name=cost_category,
            unit=Units.EUR.value,
            formula=Block(
                left=ExpenseElement(
                    kpi_type=KPITypes.NET.value,
                    categories=[cost_category],
                ),
            ),
            kpi_category='Coût > Flotte > Fiscalité',
        ).json
        for cost_category in list_tax_cat
    ]

    kpi_lst += [
        KPI(
            name='ikb_no_fuel_purchase_based',
            unit=Units.EUR.value,
            formula=Element(
                type=ElementTypes.ikb_no_fuel_purchase_based.value
            ),
            kpi_category='Coût > Flotte > Fiscalité',
        ).json,
        KPI(
            name='ikb_inc_fuel_purchase_based',
            unit=Units.EUR.value,
            formula=Element(
                type=ElementTypes.ikb_inc_fuel_purchase_based.value
            ),
            kpi_category='Coût > Flotte > Fiscalité',
        ).json,
        KPI(
            name='ikb_no_fuel_expense_based',
            unit=Units.EUR.value,
            formula=Element(type=ElementTypes.ikb_no_fuel_expense_based.value),
            kpi_category='Coût > Flotte > Fiscalité',
        ).json,
        KPI(
            name='ikb_inc_fuel_expense_based',
            unit=Units.EUR.value,
            formula=Element(
                type=ElementTypes.ikb_inc_fuel_expense_based.value
            ),
            kpi_category='Coût > Flotte > Fiscalité',
        ).json,
        KPI(
            name='ikb_calculated_final',
            unit=Units.EUR.value,
            formula=Element(type=ElementTypes.ikb_calculated_final.value),
            kpi_category='Coût > Flotte > Fiscalité',
        ).json,
        KPI(
            name='participation',
            unit=Units.EUR.value,
            formula=Block(
                left=Element(
                    type=ElementTypes.participation.value,
                )
            ),
            kpi_category='Coût > Flotte > Fiscalité',
        ).json,
        KPI(
            name='declared_non_deduc_amortization',
            unit=Units.EUR.value,
            formula=Block(
                left=Element(
                    type=ElementTypes.declared_non_deduc_amortization.value,
                )
            ),
            kpi_category='Coût > Flotte > Fiscalité',
        ).json,
        KPI(
            name='calculated_non_deduc_amortization',
            unit=Units.EUR.value,
            formula=Block(
                left=Element(
                    type=ElementTypes.calculated_non_deduc_amortization.value,
                ),
            ),
            kpi_category='Coût > Flotte > Fiscalité',
        ).json,
    ]
    kpi_lst += [
        KPI(
            name=aen_var + '_taxes',
            unit=Units.EUR.value,
            formula=Block(
                left=Element(
                    type=ElementTypes.constant.value,
                    value=SOCIAL_SECURITY_TAX_RATE,
                ),
                right=kpi_formula_dict[aen_var],
            ),
            kpi_category='Coût > Flotte > Fiscalité',
        ).json
        for aen_var in [
            'ikb_no_fuel_purchase_based',
            'ikb_no_fuel_expense_based',
            'ikb_inc_fuel_purchase_based',
            'ikb_inc_fuel_expense_based',
            'ikb_calculated_final',
        ]
    ]

    kpi_lst += [
        KPI(
            name=nda_var + '_taxes',
            unit=Units.EUR.value,
            formula=Block(
                left=Element(
                    type=ElementTypes.constant.value,
                    value=CORPORATE_TAX_RATE,
                ),
                right=kpi_formula_dict[nda_var],
            ),
            kpi_category='Coût > Flotte > Fiscalité',
        ).json
        for nda_var in [
            'declared_non_deduc_amortization',
            'calculated_non_deduc_amortization',
        ]
    ]

    kpi_lst += [
        KPI(
            name='taxes_total',
            unit=Units.EUR.value,
            formula=Block(
                left=kpi_formula_dict[NDA_METRIC + '_taxes'],
                operator=OperatorTypes.PLUS.value,
                right=Block(
                    left=(
                        kpi_formula_dict[IKB_METRIC + '_taxes']
                    ),
                    operator=OperatorTypes.PLUS.value,
                    right=Block(
                        left=ExpenseElement(
                            kpi_type=KPITypes.NET.value,
                            categories=[
                                CostCategory.fines.value,
                                CostCategory.environmental_bonus.value,
                                CostCategory.environmental_malus.value,
                            ],
                        ),
                    ),
                ),
            ),
            kpi_category='Coût > Flotte > Fiscalité',
        ).json,
    ]

    kpi_lst += build_kpi_json(
        cost_category_lst=[
            CostCategory.real_replacement_vehicle_cost.value,
            CostCategory.real_short_term_rental.value,
            CostCategory.real_relay_vehicle_cost.value,
            CostCategory.real_medium_term_rental.value,
            CostCategory.rent_end_of_year.value,
            CostCategory.real_maintenance.value,
            CostCategory.real_telematics_fee.value,
            CostCategory.real_telematics_install.value,
            CostCategory.real_tires_summer.value,
            CostCategory.real_tires_winter.value,
            CostCategory.real_tires_other.value,
            CostCategory.real_glass.value,
            CostCategory.real_assistance.value,
            CostCategory.real_restitution.value,
            CostCategory.real_others.value,
            CostCategory.tolls_card.value,
            CostCategory.tolls_real.value,
            CostCategory.parking_card.value,
            CostCategory.parking_real.value,
            CostCategory.washing_card.value,
            CostCategory.washing_real.value,
            CostCategory.logo.value,
            CostCategory.real_repairs.value,
            CostCategory.charging_point_installation.value,
            CostCategory.charging_points_recurring.value,
        ],
        kpi_category='Coût > Flotte > Autres',
    )

    kpi_lst += build_kpi_json(
        prefix='claims_',
        cost_category_lst=[
            ExpenseType.fuel.value,
            ExpenseType.tolls.value,
            ExpenseType.parking.value,
            ExpenseType.maintenance.value,
            ExpenseType.mileage_allowance.value,
            ExpenseType.taxi.value,
            ExpenseType.train.value,
            ExpenseType.plane.value,
        ],
        element_class=ExpenseElement,
        kpi_category='Coût > Notes de frais > dépenses',
    )

    kpi_lst += build_kpi_json(
        prefix='travel_',
        suffix='_distance',
        unit=Units.KM.value,
        cost_category_lst=[
            TravelTypes.air.value,
            TravelTypes.rail.value,
        ],
        element_class=TravelElement,
        kpi_types=None,
        type=ElementTypes.travel_distance.value,
        kpi_category="Usage > Voyages d'affaires > Distance",
    )

    kpi_lst += build_kpi_json(
        prefix='travel_',
        suffix='_occurences',
        cost_category_lst=[
            TravelTypes.air.value,
            TravelTypes.rail.value,
            'RENTAL_CARS',
            'HOTELS',
        ],
        element_class=TravelElement,
        kpi_types=None,
        type=ElementTypes.travel_occurences.value,
        kpi_category="Usage > Voyages d'affaires > Occurences",
    )

    kpi_lst += build_kpi_json(
        prefix='travel_spend',
        unit=Units.NB_EVENTS.value,
        cost_category_lst=[
            TravelTypes.air.value,
            TravelTypes.rail.value,
            'RENTAL_CARS',
            'HOTELS',
        ],
        element_class=TravelExpenses,
        type=ElementTypes.travel_expenses.value,
        kpi_category="Coût > Voyages d'affaires > dépenses",
    )

    kpi_lst += build_kpi_json(
        prefix='travel_',
        suffix='_anticipation',
        unit=Units.DAYS.value,
        cost_category_lst=[
            TravelTypes.air.value,
            TravelTypes.rail.value,
            'RENTAL_CARS',
            'HOTELS',
        ],
        element_class=TravelElement,
        type=ElementTypes.travel_anticipation.value,
        kpi_types=None,
        kpi_category="Usage > Voyages d'affaires > Anticipation",
    )

    kpi_lst += [
        KPI(
            name='mileage_driven',
            unit=Units.KM.value,
            formula=Block(
                left=Element(type=ElementTypes.mileage.value)
            ),
            kpi_category='Usage > Flotte',
        ).json,
        KPI(
            name='total_mileage',
            unit=Units.KM.value,
            formula=Block(
                left=Element(type=ElementTypes.current_mileage.value)
            ),
            kpi_category='Usage > Flotte',
        ).json,
        KPI(
            name='lease_mileage',
            unit=Units.KM.value,
            formula=Block(
                left=Element(type=ElementTypes.lease_mileage.value)
            ),
            kpi_category='Usage > Flotte',
        ).json,
        KPI(
            name='lease_months',
            unit=Units.KM.value,
            formula=Block(
                left=Element(type=ElementTypes.lease_months.value)
            ),
            kpi_category='Usage > Flotte',
        ).json,
    ]

    kpi_lst += [
        KPI(
            name='CO2_usage',
            unit=Units.CO2.value,
            formula=Block(
                left=Element(type=ElementTypes.CO2_usage.value)
            ),
            kpi_category='CO2 > Flotte',
        ).json,
        KPI(
            name='CO2_production',
            unit=Units.CO2.value,
            formula=Block(
                left=Element(type=ElementTypes.CO2_production.value),
            ),
            kpi_category='CO2 > Flotte',
        ).json,
        KPI(
            name='CO2_recycling',
            unit=Units.CO2.value,
            formula=Block(
                left=Element(type=ElementTypes.CO2_recycling.value),
            ),
            kpi_category='CO2 > Flotte',
        ).json,
        KPI(
            name='CO2_trains',
            unit=Units.CO2.value,
            formula=Block(
                left=Element(type=ElementTypes.CO2_trains.value),
            ),
            kpi_category="CO2 > Voyages d'affaires",
        ).json,
        KPI(
            name='CO2_planes',
            unit=Units.CO2.value,
            formula=Block(
                left=Element(type=ElementTypes.CO2_planes.value),
            ),
            kpi_category="CO2 > Voyages d'affaires",
        ).json,
        KPI(
            name='CO2_rental_cars',
            unit=Units.CO2.value,
            formula=Block(
                left=Element(type=ElementTypes.rental_cars_days.value),
                operator=OperatorTypes.MULTIPLY.value,
                right=Element(
                    type=ElementTypes.constant.value,
                    value=50 * 0.1175,  # 50 km per day and 117.5g per km
                )
            ),
            kpi_category="CO2 > Voyages d'affaires",
        ).json,
        KPI(
            name='CO2_taxi',
            unit=Units.CO2.value,
            formula=Block(
                left=Block(
                    left=Block(
                        left=ExpenseClaimElement(
                            kpi_type=KPITypes.NET.value,
                            categories=ExpenseType.taxi.value,
                        ),
                        operator=OperatorTypes.PLUS.value,
                        right=ExpenseClaimElement(
                            kpi_type=KPITypes.DEDUC_VAT.value,
                            categories=ExpenseType.taxi.value,
                        ),
                    ),
                    operator=OperatorTypes.MINUS.value,
                    right=Element(
                        type=ElementTypes.constant.value,
                        value=-4.4,  # the base value of the fare
                    ),
                ),
                operator=OperatorTypes.MULTIPLY.value,
                right=Element(
                    type=ElementTypes.constant.value,
                    value=0.1755/1.27,  # 175.5g of CO2 per km and €1.27 per km
                )
            ),
            kpi_category="CO2 > Voyages d'affaires",
        ).json,
    ]

    TCO_cat = [
        CostCategory.financial_rent.value,
        CostCategory.rent_management_fees.value,
        CostCategory.rent_maintenance.value,
        CostCategory.rent_telematic.value,
        CostCategory.rent_tires.value,
        CostCategory.rent_insurance.value,
        CostCategory.rent_fuel_card.value,
        CostCategory.rent_financial_loss.value,
        CostCategory.rent_replacement_vehicle_actual.value,
        CostCategory.rent_replacement_vehicle_flat_fee.value,
        CostCategory.rent_assistance.value,
        CostCategory.rent_others.value,
        CostCategory.rent_end_of_year.value,
        CostCategory.insurance_vehicle.value,
        CostCategory.insurance_glass.value,
        CostCategory.insurance_replacement_vehicle.value,
        CostCategory.insurance_assistance.value,
        CostCategory.insurance_financial_loss.value,
        CostCategory.insurance_deductible_cost.value,
        CostCategory.insurance_brokerage_cost.value,
        CostCategory.self_insurance.value,
        CostCategory.fuel_cost.value,
        CostCategory.electricity_cost.value,
        CostCategory.charging_points_recurring.value,
        CostCategory.charging_point_installation.value,
        CostCategory.participation.value,
        CostCategory.environmental_bonus.value,
        CostCategory.environmental_malus.value,
        CostCategory.company_car_tax.value,
        CostCategory.corporate_tax_company_car_tax.value,
        CostCategory.fines.value,
        CostCategory.real_short_term_rental.value,
        CostCategory.real_replacement_vehicle_cost.value,
        CostCategory.real_medium_term_rental.value,
        CostCategory.real_relay_vehicle_cost.value,
        CostCategory.real_maintenance.value,
        CostCategory.real_telematics_fee.value,
        CostCategory.real_telematics_install.value,
        CostCategory.real_tires_summer.value,
        CostCategory.real_tires_winter.value,
        CostCategory.real_tires_other.value,
        CostCategory.real_glass.value,
        CostCategory.real_fuel_card.value,
        CostCategory.real_assistance.value,
        CostCategory.real_adblue.value,
        CostCategory.real_restitution.value,
        CostCategory.real_others.value,
        CostCategory.real_repairs.value,
        CostCategory.tolls_card.value,
        CostCategory.tolls_real.value,
        CostCategory.parking_card.value,
        CostCategory.parking_real.value,
        CostCategory.washing_card.value,
        CostCategory.washing_real.value,
        CostCategory.logo.value,
        CostCategory.management_software_fee.value,
        CostCategory.management_software_install.value,
    ]
    kpi_lst += [
        KPI(
            name='TCO',
            unit=Units.EUR.value,
            formula=Block(
                left=Block(
                    left=Block(
                        left=Block(
                            left=ExpenseElement(
                                kpi_type=KPITypes.NET.value,
                                categories=TCO_cat,
                            ),
                            operator=OperatorTypes.PLUS.value,
                            right=kpi_formula_dict[IKB_METRIC + '_taxes'],
                        ),
                        operator=OperatorTypes.PLUS.value,
                        right=kpi_formula_dict[NDA_METRIC + '_taxes'],
                    ),
                    operator=OperatorTypes.PLUS.value,
                    right=ExpenseClaimElement(
                        kpi_type=KPITypes.NET.value,
                        categories=[
                            ExpenseType.fuel.value,
                            ExpenseType.tolls.value,
                            ExpenseType.parking.value,
                            ExpenseType.maintenance.value,
                            ExpenseType.repairs.value,
                        ],
                    ),
                ),
                operator=OperatorTypes.MINUS.value,
                right=Element(type=ElementTypes.participation.value),
            ),
            kpi_category='Coût > Flotte > TCO',
        ).json,
        KPI(
            name='TCO_per_vehicle',
            unit=Units.EUR_PER_VEHICLE.value,
            formula=Block(
                left=kpi_formula_dict['TCO'],
                operator=OperatorTypes.DIVIDE.value,
                right=Element(type=ElementTypes.vehicles.value),
            ),
            kpi_category='Coût > Flotte > TCO',
        ).json,
        KPI(
            name='TCO_per_driver',
            unit=Units.EUR_PER_VEHICLE.value,
            formula=Block(
                left=kpi_formula_dict['TCO'],
                operator=OperatorTypes.DIVIDE.value,
                right=Element(type=ElementTypes.drivers.value),
            ),
            kpi_category='Coût > Flotte > TCO',
        ).json,
        KPI(
            name='Cost_per_km',
            unit=Units.EUR_PER_VEHICLE.value,
            formula=Block(
                left=kpi_formula_dict['TCO'],
                operator=OperatorTypes.DIVIDE.value,
                right=Element(type=ElementTypes.mileage.value),
            ),
            kpi_category='Coût > Flotte > TCO',
        ).json,
    ]

    kpi_lst += [
        KPI(
            name='TCM',
            unit=Units.EUR.value,
            formula=Block(
                left=Block(
                    left=kpi_formula_dict['TCO'],
                    operator=OperatorTypes.PLUS.value,
                    right=ExpenseClaimElement(
                        kpi_type=KPITypes.NET.value,
                        categories=[
                            ExpenseType.mileage_allowance.value,
                            ExpenseType.train.value,
                            ExpenseType.plane.value,
                            ExpenseType.car_rental.value,
                        ],
                    ),
                ),
                operator=OperatorTypes.PLUS.name,
                right=TravelExpenses(
                    type=ElementTypes.travel_expenses.value,
                    categories=[
                        TravelTypes.air.value,
                        TravelTypes.rail.value,
                        'RENTAL_CARS',
                        'HOTELS',
                    ],
                    kpi_type=KPITypes.NET.value,
                )
            ),
            kpi_category='Coût > Tous',
        ).json,
        KPI(
            name='TCM_collaborators',
            unit=Units.EUR_PER_PERSON.value,
            formula=Block(
                left=kpi_formula_dict['TCM'],
                operator=OperatorTypes.DIVIDE.value,
                right=Element(type=ElementTypes.collaborators.value),
            ),
            kpi_category='Coût > Tous',
        ).json,
        KPI(
            name='TCM_users',
            unit=Units.EUR_PER_PERSON.value,
            formula=Block(
                left=kpi_formula_dict['TCM'],
                operator=OperatorTypes.DIVIDE.value,
                right=Element(type=ElementTypes.users.value),
            ),
            kpi_category='Coût > Tous',
        ).json,
    ]

    kpi_lst += [
        KPI(
            name='rent_total_' + kpi_type.value,
            unit=Units.EUR.value,
            formula=Block(
                left=ExpenseElement(
                    kpi_type=kpi_type.value,
                    categories=[
                        CostCategory.financial_rent.value,
                        CostCategory.rent_management_fees.value,
                        CostCategory.rent_telematic.value,
                        CostCategory.rent_tires.value,
                        CostCategory.rent_insurance.value,
                        CostCategory.rent_financial_loss.value,
                        CostCategory.rent_fuel_card.value,
                        CostCategory.rent_replacement_vehicle_flat_fee.value,
                        CostCategory.rent_replacement_vehicle_actual.value,
                        CostCategory.rent_assistance.value,
                        CostCategory.rent_others.value,
                    ],
                ),
            ),
            kpi_category=(
                f'Coût > Flotte > Loyers {KPI_CAT_DICT[kpi_type.value]}'
            ),
        ).json
        for kpi_type in KPITypes
    ]

    kpi_lst += [
        KPI(
            name='energy_total_' + kpi_type.value,
            unit=Units.EUR.value,
            formula=Block(
                left=ExpenseElement(
                    kpi_type=kpi_type.value,
                    categories=[
                        CostCategory.fuel_cost.value,
                        CostCategory.real_fuel_card.value,
                        CostCategory.electricity_cost.value,
                        CostCategory.real_adblue.value,
                    ],
                ),
                operator=OperatorTypes.PLUS.value,
                right=ExpenseClaimElement(
                    kpi_type=kpi_type.value,
                    categories=[
                        CostCategory.fuel_cost.value,
                    ],
                ),
            ),
            kpi_category=(
                f'Coût > Flotte > Energies {KPI_CAT_DICT[kpi_type.value]}'
            ),
        ).json
        for kpi_type in KPITypes
    ]

    kpi_lst += [
        KPI(
            name=f'insurance_total_{kpi_type.value}',
            unit=Units.EUR.value,
            formula=Block(
                left=ExpenseElement(
                    kpi_type=kpi_type.value,
                    categories=[
                        CostCategory.insurance_vehicle.value,
                        CostCategory.insurance_replacement_vehicle.value,
                        CostCategory.insurance_assistance.value,
                        CostCategory.insurance_financial_loss.value,
                        CostCategory.insurance_glass.value,
                        CostCategory.insurance_deductible_cost.value,
                        CostCategory.self_insurance.value,
                        CostCategory.insurance_brokerage_cost.value,
                    ],
                ),
            ),
            kpi_category=(
                'Coût > Flotte > Assurances ' + KPI_CAT_DICT[kpi_type.value]
            ),
        ).json
        for kpi_type in KPITypes
    ]

    kpi_lst += [
        KPI(
            name='travel_total_' + kpi_type.value,
            unit=Units.EUR.value,
            formula=Block(
                left=TravelExpenses(
                    type=ElementTypes.travel_expenses.value,
                    kpi_type=kpi_type.value,
                    categories=[
                        TravelTypes.air.value,
                        TravelTypes.rail.value,
                        'RENTAL_CARS',
                        'HOTELS',
                    ],
                ),
            ),
            kpi_category=(
                "Coût > Voyages d'affaires > dépenses "
                + KPI_CAT_DICT[kpi_type.value]
            ),
        ).json
        for kpi_type in KPITypes
    ]

    kpi_lst += [
        KPI(
            name='travel_cost_per_travel_' + kpi_type.value,
            unit=Units.EUR_PER_EVENT.value,
            formula=Block(
                left=kpi_formula_dict['travel_total_' + kpi_type.value],
                right=Element(type=ElementTypes.travel_occurences.value),
            ),
            kpi_category=(
                "Coût > Voyages d'affaires > dépenses "
                + KPI_CAT_DICT[kpi_type.value]
            ),
        ).json
        for kpi_type in KPITypes
    ]

    kpi_lst += [
        KPI(
            name='travel_cost_per_travellers_' + kpi_type.value,
            unit=Units.EUR_PER_PERSON.value,
            formula=Block(
                left=kpi_formula_dict['travel_total_' + kpi_type.value],
                right=Element(type=ElementTypes.travellers.value),
            ),
            kpi_category=(
                "Coût > Voyages d'affaires > dépenses "
                + KPI_CAT_DICT[kpi_type.value]
            ),
        ).json
        for kpi_type in KPITypes
    ]

    kpi_lst += [
        KPI(
            name='total_CO2_fleet',
            unit=Units.CO2.value,
            formula=Block(
                left=Block(
                    left=kpi_formula_dict['CO2_usage'],
                    operator=OperatorTypes.PLUS.value,
                    right=Element(type=ElementTypes.CO2_production.value),
                ),
                operator=OperatorTypes.PLUS.value,
                right=Element(type=ElementTypes.CO2_recycling.value),
            ),
            kpi_category='CO2 > Flotte',
        ).json
    ]
    kpi_lst += [
        KPI(
            name='total_CO2_travel',
            unit=Units.CO2.value,
            formula=Block(
                left=Block(
                    left=Block(
                        left=kpi_formula_dict['CO2_rental_cars'],
                        operator=OperatorTypes.PLUS.value,
                        right=Element(type=ElementTypes.CO2_trains.value),
                    ),
                    operator=OperatorTypes.PLUS.value,
                    right=kpi_formula_dict['CO2_taxi'],
                ),
                operator=OperatorTypes.PLUS.value,
                right=Element(type=ElementTypes.CO2_planes.value)
            ),
            kpi_category="CO2 > Voyages d'affaires",
        ).json
    ]
    kpi_lst += [
        KPI(
            name='total_CO2',
            unit=Units.CO2.value,
            formula=Block(
                left=kpi_formula_dict['total_CO2_fleet'],
                operator=OperatorTypes.PLUS.value,
                right=kpi_formula_dict['total_CO2_travel'],
            ),
            kpi_category='CO2 > Tous',
        ).json,
        KPI(
            name='CO2_per_collaborator',
            unit=Units.CO2_PER_PERSON.value,
            formula=Block(
                left=kpi_formula_dict['total_CO2'],
                operator=OperatorTypes.DIVIDE.value,
                right=Element(type=ElementTypes.collaborators.value),
            ),
            kpi_category='CO2 > Tous',
        ).json,
        KPI(
            name='CO2_fleet_per_driver',
            unit=Units.CO2_PER_PERSON.value,
            formula=Block(
                left=kpi_formula_dict['total_CO2_fleet'],
                operator=OperatorTypes.DIVIDE.value,
                right=Element(type=ElementTypes.drivers.value),
            ),
            kpi_category='CO2 > Flotte',
        ).json,
        KPI(
            name='CO2_usage_per_driver',
            unit=Units.CO2_PER_PERSON.value,
            formula=Block(
                left=kpi_formula_dict['CO2_usage'],
                operator=OperatorTypes.DIVIDE.value,
                right=Element(type=ElementTypes.drivers.value),
            ),
            kpi_category='CO2 > Flotte',
        ).json,
        KPI(
            name='CO2_production_per_driver',
            unit=Units.CO2_PER_PERSON.value,
            formula=Block(
                left=kpi_formula_dict['CO2_production'],
                operator=OperatorTypes.DIVIDE.value,
                right=Element(type=ElementTypes.drivers.value),
            ),
            kpi_category='CO2 > Flotte',
        ).json,
        KPI(
            name='CO2_recycling_per_driver',
            unit=Units.CO2_PER_PERSON.value,
            formula=Block(
                left=kpi_formula_dict['CO2_recycling'],
                operator=OperatorTypes.DIVIDE.value,
                right=Element(type=ElementTypes.drivers.value),
            ),
            kpi_category='CO2 > Flotte',
        ).json,
        KPI(
            name='CO2_per_km',
            unit=Units.CO2_PER_PERSON.value,
            formula=Block(
                left=kpi_formula_dict['total_CO2_fleet'],
                operator=OperatorTypes.DIVIDE.value,
                right=Element(type=ElementTypes.mileage.value),
            ),
            kpi_category='CO2 > Flotte',
        ).json,

        KPI(
            name='CO2_fleet_per_vehicles',
            unit=Units.CO2_PER_PERSON.value,
            formula=Block(
                left=kpi_formula_dict['total_CO2_fleet'],
                operator=OperatorTypes.DIVIDE.value,
                right=Element(type=ElementTypes.vehicles.value),
            ),
            kpi_category='CO2 > Flotte',
        ).json,
        KPI(
            name='CO2_usage_per_vehicles',
            unit=Units.CO2_PER_PERSON.value,
            formula=Block(
                left=kpi_formula_dict['CO2_usage'],
                operator=OperatorTypes.DIVIDE.value,
                right=Element(type=ElementTypes.vehicles.value),
            ),
            kpi_category='CO2 > Flotte',
        ).json,
        KPI(
            name='CO2_production_per_vehicles',
            unit=Units.CO2_PER_PERSON.value,
            formula=Block(
                left=kpi_formula_dict['CO2_production'],
                operator=OperatorTypes.DIVIDE.value,
                right=Element(type=ElementTypes.vehicles.value),
            ),
            kpi_category='CO2 > Flotte',
        ).json,
        KPI(
            name='CO2_recycling_per_vehicles',
            unit=Units.CO2_PER_PERSON.value,
            formula=Block(
                left=kpi_formula_dict['CO2_recycling'],
                operator=OperatorTypes.DIVIDE.value,
                right=Element(type=ElementTypes.vehicles.value),
            ),
            kpi_category='CO2 > Flotte',
        ).json,

        KPI(
            name='CO2_travel_per_travellers',
            unit=Units.CO2_PER_PERSON.value,
            formula=Block(
                left=kpi_formula_dict['total_CO2_travel'],
                operator=OperatorTypes.DIVIDE.value,
                right=Element(type=ElementTypes.travellers.value),
            ),
            kpi_category="CO2 > Voyages d'affaires",
        ).json,
        KPI(
            name='CO2_trains_per_travellers',
            unit=Units.CO2_PER_PERSON.value,
            formula=Block(
                left=Element(type=ElementTypes.CO2_trains.value),
                operator=OperatorTypes.DIVIDE.value,
                right=Element(type=ElementTypes.travellers.value),
            ),
            kpi_category="CO2 > Voyages d'affaires",
        ).json,
        KPI(
            name='CO2_planes_per_travellers',
            unit=Units.CO2_PER_PERSON.value,
            formula=Block(
                left=Element(type=ElementTypes.CO2_planes.value),
                operator=OperatorTypes.DIVIDE.value,
                right=Element(type=ElementTypes.travellers.value),
            ),
            kpi_category="CO2 > Voyages d'affaires",
        ).json,
        KPI(
            name='CO2_taxi_per_travellers',
            unit=Units.CO2_PER_PERSON.value,
            formula=Block(
                left=kpi_formula_dict['CO2_taxi'],
                operator=OperatorTypes.DIVIDE.value,
                right=Element(type=ElementTypes.travellers.value),
            ),
            kpi_category='CO2 > Notes de frais',
        ).json,
        KPI(
            name='CO2_rental_cars_per_travellers',
            unit=Units.CO2_PER_PERSON.value,
            formula=Block(
                left=kpi_formula_dict['CO2_rental_cars'],
                operator=OperatorTypes.DIVIDE.value,
                right=Element(type=ElementTypes.travellers.value),
            ),
            kpi_category="CO2 > Voyages d'affaires",
        ).json,

        KPI(
            name='CO2_travel_per_travel',
            unit=Units.CO2_PER_EVENT.value,
            formula=Block(
                left=kpi_formula_dict['total_CO2_travel'],
                operator=OperatorTypes.DIVIDE.value,
                right=Element(type=ElementTypes.travel_occurences.value),
            ),
            kpi_category="CO2 > Voyages d'affaires",
        ).json,
        KPI(
            name='CO2_trains_per_travel',
            unit=Units.CO2_PER_EVENT.value,
            formula=Block(
                left=Element(type=ElementTypes.CO2_trains.value),
                operator=OperatorTypes.DIVIDE.value,
                right=Element(type=ElementTypes.travel_occurences.value),
            ),
            kpi_category="CO2 > Voyages d'affaires",
        ).json,
        KPI(
            name='CO2_planes_per_travel',
            unit=Units.CO2_PER_EVENT.value,
            formula=Block(
                left=Element(type=ElementTypes.CO2_planes.value),
                operator=OperatorTypes.DIVIDE.value,
                right=Element(type=ElementTypes.travel_occurences.value),
            ),
            kpi_category="CO2 > Voyages d'affaires",
        ).json,
        KPI(
            name='CO2_rental_cars_per_travel',
            unit=Units.CO2_PER_EVENT.value,
            formula=Block(
                left=kpi_formula_dict['CO2_rental_cars'],
                operator=OperatorTypes.DIVIDE.value,
                right=Element(type=ElementTypes.travel_occurences.value),
            ),
            kpi_category="CO2 > Voyages d'affaires",
        ).json,
    ]

    target_folder = '~/dev/temp/kpi.json'
    with open(os.path.expanduser(target_folder), 'w') as file:
        json.dump(
            kpi_lst,
            fp=file,
            indent=4,
        )
    print('All done - kpi json saved under ', target_folder)
