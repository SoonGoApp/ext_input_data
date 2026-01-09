""" ClaimsModel

Defines columns used across all fleet connectors datasets
"""
from soongo_data.data_models.base import BaseModel, DataColumn
from soongo_data.utils.enums import (ExpenseStatus, ExpenseType,
                                     mapper_factory)
from soongo_data.utils.type import CountryConverter, convert_date


class ClaimsModel(BaseModel):
    approbation_status: DataColumn = DataColumn(
        raw_name="Statut de l'approbation",
        dtype='string',
        post_processing=mapper_factory(ExpenseStatus),
        name='approbation_status'
    )
    claim_name: DataColumn = DataColumn(
        raw_name="Nom de la note de frais",
        dtype='string',
        name='claim_name'
    )
    claim_ref: DataColumn = DataColumn(
        raw_name="Identifiant de la note de frais",
        dtype='string',
        name='claim_ref'
    )
    expense_date: DataColumn = DataColumn(
        raw_name="Date de la transaction",
        dtype='datetime64[ns]',
        name='expense_date'
    )
    currency: DataColumn = DataColumn(
        raw_name="Devise du reporting",
        dtype='string',
        name='currency'
    )
    expense_type: DataColumn = DataColumn(
        raw_name="Type de frais",
        dtype='string',
        name='expense_type',
        post_processing=mapper_factory(ExpenseType)
    )
    professional_mileage: DataColumn = DataColumn(
        'Distance professionnelle',
        dtype='Int64',
        name='professional_mileage'
    )
    reimbursed_amount: DataColumn = DataColumn(
        'Montant remboursé',
        dtype='float64',
        name='reimbursed_amount'
    )
    submission_date: DataColumn = DataColumn(
        raw_name='Date de première soumission',
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='submission_date'
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
    payment_date = DataColumn(
        raw_name="Date d'envoi pour paiement",
        dtype='datetime64[ns]',
        post_processing=convert_date,
        name='payment_date'
    )
    deductible_vat = DataColumn(
        raw_name='deductible_vat',
        dtype='float64',
        name='deductible_vat',
        description='Amount of deductible VAT.'
    )
    claim_city = DataColumn(
        raw_name='city',
        dtype='string',
        name='claim_city',
        description='City of the expense.'
    )
    claim_country = DataColumn(
        raw_name='country',
        dtype='string',
        name='claim_country',
        description='Country of the expense.',
        post_processing=CountryConverter(['fr', 'en'])
    )
    claim_region = DataColumn(
        raw_name='state',
        dtype='string',
        name='claim_region',
        description='Region/State where the expense occured'
    )
    vat_amount = DataColumn(
        raw_name='vat_amount',
        dtype='float64',
        name='vat_amount',
        description='Amount of VAT.'
    )
    vat_rate = DataColumn(
        raw_name='vat_rate',
        dtype='float64',
        name='vat_rate',
        description='Rate of VAT.'
    )
    quantity = DataColumn(
        raw_name='quantity',
        dtype='float64',
        name='quantity',
        description='Quantity of items purchased.'
    )
    liters = DataColumn(
        raw_name='liters',
        dtype='float64',
        name='liters',
        description='Number of liters purchased.'
    )
