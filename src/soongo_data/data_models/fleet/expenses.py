""" ExpenseModels

Defines columns used across all fleet connectors datasets
"""
from __future__ import annotations

import typing

from soongo_data.data_models.base import BaseModel, DataColumn
from soongo_data.utils.enums import (BillType, CostCategory, Suppliers,
                                     mapper_factory)
from soongo_data.utils.type import (convert_boolean, convert_date,
                                    convert_numeric, convert_string)

if typing.TYPE_CHECKING:
    import pandas as pd


def convert_dot_decimal_number(series: pd.Series) -> pd.Series:
    return convert_numeric(series, decimal='.')


class ExpensesModel(BaseModel):
    expense_reference: DataColumn = DataColumn(
        raw_name='Référence GAC',
        dtype='string',
        post_processing=convert_string,
        name='expense_reference',
    )
    billing_date: DataColumn = DataColumn(
        raw_name='Facturation',
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='billing_date',
    )
    billing_due_date: DataColumn = DataColumn(
        raw_name="Date d'échéance",
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='billing_due_date',
    )
    purchase_date: DataColumn = DataColumn(
        raw_name="Date d'achat",
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='purchase_date',
    )
    purchase_time: DataColumn = DataColumn(
        raw_name="Heure de la transaction",
        dtype='string',
        post_processing=convert_string,
        name='purchase_time',
    )
    amount_tax_exc: DataColumn = DataColumn(
        raw_name='Montant HT',
        dtype='float64',
        name='amount_tax_exc',
    )
    amount_tax_inc: DataColumn = DataColumn(
        raw_name='Montant TTC',
        dtype='float64',
        name='amount_tax_inc',
    )
    net_amount = DataColumn(
        raw_name='net_amount',
        dtype='float64',
        name='net_amount',
        description='Amount, all taxes included, deductible VAT deducted.'
    )
    deductible_vat_rate = DataColumn(
        raw_name='TVA déductible (%)',
        dtype="Int64",
        name='deductible_vat_rate'
    )
    deductible_vat = DataColumn(
        raw_name='deductible_vat',
        dtype='float64',
        name='deductible_vat',
        description='Amount of deductible VAT.'
    )
    vat_value = DataColumn(
        raw_name='Montant TVA',
        dtype='float64',
        name='vat_value'
    )
    vat_rate = DataColumn(
        raw_name='Taux TVA (%)',
        dtype='float64',
        post_processing=convert_dot_decimal_number,
        name='vat_rate'
    )
    amount_tax_exc_loc: DataColumn = DataColumn(
        raw_name='Montant HT monnaie locale',
        dtype='float64',
        name='amount_tax_exc_loc',
    )
    amount_tax_inc_loc: DataColumn = DataColumn(
        raw_name='Montant TTC monnaie locale',
        dtype='float64',
        name='amount_tax_inc_loc',
    )
    discount_rate = DataColumn(
        raw_name='Taux de remise',
        dtype='float64',
        name='discount_rate',
    )
    discount_per_unit = DataColumn(
        raw_name='discount_per_unit',
        dtype='float64',
        name='discount_per_unit',
    )
    discount_value = DataColumn(
        raw_name='Montant remisé',
        dtype='float64',
        name='discount_value',
    )
    amount_final: DataColumn = DataColumn(
        raw_name='Montant NET',
        dtype='float64',
        name='amount_final',
    )
    category_1: DataColumn = DataColumn(
        raw_name='Catégorie 1',
        dtype='string',
        post_processing=convert_string,
        name='category_1',
    )
    category_2: DataColumn = DataColumn(
        raw_name='Catégorie 2',
        dtype='string',
        post_processing=convert_string,
        name='category_2',
    )
    category_3: DataColumn = DataColumn(
        raw_name='Catégorie 3',
        dtype='string',
        post_processing=convert_string,
        name='category_3',
    )
    category_4: DataColumn = DataColumn(
        raw_name='Catégorie 4',
        dtype='string',
        post_processing=convert_string,
        name='category_4',
    )
    product: DataColumn = DataColumn(
        raw_name='Produit',
        dtype='string',
        post_processing=convert_string,
        name='product',
    )
    product_ref: DataColumn = DataColumn(
        raw_name='Code produit',
        dtype='string',
        post_processing=convert_string,
        name='product_ref',
    )
    spent_tag: DataColumn = DataColumn(
        raw_name='Étiquette de dépense',
        dtype='string',
        post_processing=convert_string,
        name='spent_tag',
    )
    source: DataColumn = DataColumn(
        raw_name='Source / Origine',
        dtype='string',
        post_processing=convert_string,
        name='source',
    )
    organization_employee_id: DataColumn = DataColumn(
        raw_name='Matricule',
        dtype='Int64',
        post_processing=convert_numeric,
        name='organization_employee_id',
    )
    soongo_category: DataColumn = DataColumn(
        raw_name='soongo_category',
        dtype='string',
        name='soongo_category',
        description=(
            'SoonGo category; categories correspond to a ExpenseCategory'
        ),
        post_processing=mapper_factory(CostCategory)
    )
    unit_price: DataColumn = DataColumn(
        raw_name="Prix unitaire",
        name="unit_price",
        dtype="float64",
    )
    quantity: DataColumn = DataColumn(
        raw_name="Quantité",
        name="quantity",
        dtype="float64",
    )
    expense_description: DataColumn = DataColumn(
        raw_name='Description',
        dtype='string',
        post_processing=convert_string,
        name='expense_description'
    )
    billing_reference: DataColumn = DataColumn(
        raw_name='Numéro de facture',
        dtype='string',
        post_processing=convert_string,
        name='billing_reference',
    )
    billing_account: DataColumn = DataColumn(
        raw_name='Compte facturé',
        dtype="Int64",
        name='billing_account',
    )
    expense_location: DataColumn = DataColumn(
        raw_name='Lieu',
        dtype='string',
        post_processing=convert_string,
        name='expense_location',
    )
    expense_department_code: DataColumn = DataColumn(
        raw_name='Département',
        dtype='string',
        name='expense_department_code',
        post_processing=convert_string,
    )
    expense_country: DataColumn = DataColumn(
        raw_name='Pays de la transaction',
        dtype='string',
        name='expense_country',
        post_processing=convert_string,
    )
    supplier: DataColumn = DataColumn(
        raw_name='Fournisseur',
        dtype='string',
        post_processing=mapper_factory(Suppliers),
        name='supplier',
    )
    transaction_start_date: DataColumn = DataColumn(
        raw_name='Facture > Début de période',
        name='transaction_start_date',
        dtype='datetime64[ns]',
    )
    transaction_start_time: DataColumn = DataColumn(
        raw_name='Facture > Début de période',
        name='transaction_start_time',
        dtype='str',
        post_processing=convert_string,
    )
    transaction_end_date: DataColumn = DataColumn(
        raw_name='Facture > Fin de période',
        name='transaction_end_date',
        dtype='datetime64[ns]',
    )
    transaction_end_time: DataColumn = DataColumn(
        raw_name='Facture > Début de période',
        name='transaction_end_time',
        dtype='str',
        post_processing=convert_string,
    )
    currency: DataColumn = DataColumn(
        raw_name="Devise du reporting",
        dtype='string',
        name='currency'
    )
    billing_type: DataColumn = DataColumn(
        raw_name='Facture > Type',
        dtype='string',
        name='billing_type',
        post_processing=mapper_factory(BillType),
    )
    is_anomalous: DataColumn = DataColumn(
        raw_name="Facture > Présence d'anomalie",
        dtype='boolean',
        name='is_anomalous',
        post_processing=convert_boolean,
    )
    anomaly_description: DataColumn = DataColumn(
        raw_name="Anomalie(s)",
        dtype='string',
        name='anomaly_description',
        post_processing=convert_string,
    )
    tire_season: DataColumn = DataColumn(
        raw_name='tire_season',
        dtype='str',
        name='tire_season',
        post_processing=convert_string,
    )
    is_reiumbursement: DataColumn = DataColumn(
        raw_name='is_reiumbursement',
        dtype='boolean',
        name='is_reiumbursement',
        post_processing=convert_boolean,
    )
    toll_distance: DataColumn = DataColumn(
        raw_name='toll_distance',
        dtype='int64',
        name='toll_distance',
        description='Distance between entry and exit in km for toll expenses'
    )
    merchant_code: DataColumn = DataColumn(
        raw_name='merchant_code',
        dtype='string',
        name='merchant_code',
        description='Merchant code for the expense, if applicable'
    )
    merchant_name: DataColumn = DataColumn(
        raw_name='merchant_name',
        dtype='string',
        name='merchant_name',
        description='Merchant name for the expense, if applicable'
    )
    expense_year: DataColumn = DataColumn(
        raw_name='expense_year',
        dtype='Int64',
        name='expense_year',
        description='Year of the expense'
    )
