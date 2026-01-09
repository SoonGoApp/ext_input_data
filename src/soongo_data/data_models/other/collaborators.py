""" Collaborators

Defines columns used across to characterize collaborators
"""
from soongo_data.data_models.base import BaseModel, DataColumn
from soongo_data.utils.enums import Civility, mapper_factory
from soongo_data.utils.type import (CountryConverter, convert_boolean, convert_date,
                                    convert_phone_number, convert_string)


class CollaboratorsModel(BaseModel):
    collaborator_id: DataColumn = DataColumn(
        raw_name='collaborator_id',
        dtype='string',
        name='collaborator_id',
        description='SoonGo db uuid identifying the organization employee',
    )
    soongo_collab_reference: DataColumn = DataColumn(
        raw_name='soongo_collab_reference',
        dtype='string',
        name='soongo_collab_reference',
        description='SoonGo generated customer organization employee id'
    )
    collaborator_connector_id: DataColumn = DataColumn(
        raw_name='connector_id',
        dtype='string',
        post_processing=convert_string,
        name='collaborator_connector_id',
        description='Unique id for this collaborator in the connector system'
    )
    connector_entry_date: DataColumn = DataColumn(
        raw_name='connector_entry_date',
        name='connector_entry_date',
        dtype='datetime64[ns]',
    )
    employee_entry_date = DataColumn(
        raw_name='Date ancienneté groupe ',
        name='employee_entry_date',
        dtype='datetime64[ns]',
    )
    employee_exit_date = DataColumn(
        raw_name='Date sortie physique ',
        name='employee_exit_date',
        dtype='datetime64[ns]',
    )
    alternative_names: DataColumn = DataColumn(
        raw_name='alternative_names',
        dtype='string',
        name='alternative_names',
        description='Comma separated alternative names sets'
    )
    lastname: DataColumn = DataColumn(
        raw_name='Nom',
        dtype='string',
        post_processing=convert_string,
        name='lastname',
    )
    firstname: DataColumn = DataColumn(
        raw_name='Prénom',
        dtype='string',
        post_processing=convert_string,
        name='firstname',
    )
    employee_full_name: DataColumn = DataColumn(
        raw_name='Collaborateur',
        dtype='string',
        name='employee_full_name',
    )
    lastname_2: DataColumn = DataColumn(
        raw_name='Nom',
        dtype='string',
        post_processing=convert_string,
        name='lastname_2',
    )
    firstname_2: DataColumn = DataColumn(
        raw_name='Prénom',
        dtype='string',
        post_processing=convert_string,
        name='firstname_2',
    )
    employee_full_name_2: DataColumn = DataColumn(
        raw_name='Collaborateur',
        dtype='string',
        name='employee_full_name_2',
    )
    work_location: DataColumn = DataColumn(
        raw_name='Site de rattachement',
        dtype='string',
        post_processing=convert_string,
        name='work_location',
    )
    work_postal_code: DataColumn = DataColumn(
        raw_name='Site de rattachement',
        dtype='string',
        post_processing=convert_string,
        name='work_postal_code',
    )
    work_city: DataColumn = DataColumn(
        raw_name='Site de rattachement',
        dtype='string',
        post_processing=convert_string,
        name='work_city',
    )
    work_country: DataColumn = DataColumn(
        raw_name='Site de rattachement',
        dtype='string',
        post_processing=convert_string,
        name='work_country',
    )
    organization_collaborator_id: DataColumn = DataColumn(
        raw_name='Matricule',
        dtype='string',
        post_processing=convert_string,
        name='organization_collaborator_id',
    )
    role: DataColumn = DataColumn(
        raw_name="Fonction actuelle",
        dtype='string',
        post_processing=convert_string,
        name='role',
    )
    organization_collaborator_category = DataColumn(
        raw_name="Catégorie interne (Collaborateur)",
        dtype='string',
        name='organization_collaborator_category',
    )
    employee_category_name = DataColumn(
        raw_name="Catégorie > Libellé",
        dtype='string',
        name='employee_category_name',  # Distinguish from SoonGo's
    )
    civility: DataColumn = DataColumn(
        raw_name="Civilité conducteur",
        dtype='string',
        post_processing=mapper_factory(Civility),
        name='civility',
    )
    employee_entity: DataColumn = DataColumn(
        raw_name='Entité Collaborateur',
        dtype='string',
        post_processing=convert_string,
        name='employee_entity',
    )
    personal_street_number: DataColumn = DataColumn(
        raw_name='Collaborateur : Numéro de rue',
        dtype='string',
        post_processing=convert_string,
        name='personal_street_number',
    )
    personal_street_number_repetitor: DataColumn = DataColumn(
        raw_name='personal_street_number_repetitor',
        dtype='string',
        post_processing=convert_string,
        name='personal_street_number_repetitor',
    )
    personal_street_name: DataColumn = DataColumn(
        raw_name='Collaborateur : Nom de rue',
        dtype='string',
        post_processing=convert_string,
        name='personal_street_name',
    )
    personal_street_type: DataColumn = DataColumn(
        raw_name='personal_street_type',
        dtype='string',
        post_processing=convert_string,
        name='personal_street_type',
    )
    birthdate: DataColumn = DataColumn(
        raw_name='Collaborateur : Date de naissance',
        dtype='datetime64[ns]',
        name='birthdate',
    )
    birthplace: DataColumn = DataColumn(
        raw_name='Collaborateur : Ville de naissance',
        dtype='string',
        name='birthplace',
    )
    personal_address: DataColumn = DataColumn(
        raw_name='Collaborateur : Adresse (ligne 1)',
        dtype='string',
        name='personal_address',
    )
    personal_postal_code: DataColumn = DataColumn(
        raw_name='Collaborateur : Code Postal',
        dtype='Int64',
        name='personal_postal_code',
    )
    personal_city: DataColumn = DataColumn(
        raw_name='Collaborateur : Ville',
        dtype='string',
        name='personal_city',
    )
    personal_country: DataColumn = DataColumn(
        raw_name='Collaborateur : Pays',
        dtype='string',
        name='personal_country',
        post_processing=CountryConverter(['fr', 'en']),
    )
    employee_avg_monthly_mileage = DataColumn(
        raw_name="Moyenne kilométrique du collaborateur (Km (s) par mois)",
        dtype="Int64",
        name='employee_avg_monthly_mileage',
    )
    is_validated_driving_license = DataColumn(
        raw_name='Collaborateur : Permis attesté valide',
        dtype="boolean",
        name='is_validated_driving_license',
        post_processing=convert_boolean,
    )
    email = DataColumn(
        raw_name='Collaborateur : Email',
        dtype='string',
        name='email',
    )
    driving_licence_validation_date = DataColumn(
        raw_name='Collaborateur : Permis attesté le',
        dtype='datetime64[ns]',
        name='driving_licence_validation_date',
    )
    license_number = DataColumn(
        raw_name='Numéro de permis',
        dtype='string',
        post_processing=convert_string,
        name='license_number',
    )
    license_issuing_date: DataColumn = DataColumn(
        raw_name="Collaborateur : Délivré le",
        dtype="datetime64[ns]",
        name="license_issuing_date",
    )
    license_issuing_place: DataColumn = DataColumn(
        raw_name="Collaborateur : Délivré le",
        dtype="string",
        name="license_issuing_place",
    )
    license_country: DataColumn = DataColumn(
        raw_name="Collaborateur : Délivré le",
        dtype="string",
        name="license_country",
        post_processing=convert_date,
    )
    picture_href: DataColumn = DataColumn(
        raw_name="picture",
        dtype="string",
        name="picture_href",
    )
    manager_connector_id: DataColumn = DataColumn(
        raw_name="manager",
        dtype="string",
        name="manager_connector_id",
    )
    manager_first_name: DataColumn = DataColumn(
        raw_name="manager_first_name",
        dtype="string",
        name="manager_first_name",
    )
    manager_last_name: DataColumn = DataColumn(
        raw_name="manager_last_name",
        dtype="string",
        name="manager_last_name",
    )
    manager_full_name: DataColumn = DataColumn(
        raw_name="manager_full_name",
        dtype="string",
        name="manager_full_name",
    )
    manager_soongo_reference: DataColumn = DataColumn(
        raw_name="manager_soongo_reference",
        dtype="string",
        name="manager_soongo_reference",
    )
    manager_email: DataColumn = DataColumn(
        raw_name="manager_email",
        dtype="string",
        name="manager_email",
    )
    manager_organization_id: DataColumn = DataColumn(
        raw_name="manager_organization_id",
        dtype="string",
        name="manager_organization_id",
    )
    added_data: DataColumn = DataColumn(
        raw_name='added_data',
        dtype='object',
        name='added_data',
        description='Additional data in dict to be added to the collaborator'
    )
    personal_phone_number: DataColumn = DataColumn(
        raw_name='Collaborateur : Téléphone personnel',
        dtype='string',
        name='personal_phone_number',
        post_processing=convert_phone_number,
    )
    professional_phone_number: DataColumn = DataColumn(
        raw_name='Collaborateur : Téléphone professionnel',
        dtype='string',
        name='professional_phone_number',
        post_processing=convert_phone_number,
    )
