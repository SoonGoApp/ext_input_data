""" Lucca Data

Class loading, normalizing and organizing all Masternaut Datasets for a given
organization
"""
import logging
import typing

import pandas as pd

from soongo_data.connectors import (
    Dataset, DataSource, attach_dataset, load_from_api
)
from soongo_data.connectors.lucca.utils import (
    form_field_params, get_ikb_value_date, get_extended_data_mapping,
    load_organizations
)
from soongo_data.data_models import (BusinessUnitsModel, CollaboratorsModel,
                                     VehicleAssociationsModel)
from soongo_data.utils.secrets_utils import get_local_secret
from soongo_data.utils.bu import correct_business_unit
from soongo_data.utils.enums import SynchronizationTypes
from soongo_data.utils.type import (DictColumnGetter, NamesConverter,
                                    convert_phone_number, convert_string)


class LuccaData(Dataset):
    CONNECTOR_NAME = 'LUCCA'
    NAME = 'LUCCA'
    TYPE = SynchronizationTypes.api.value

    def __init__(
        self,
        connector_folder: str,
        logger: logging.Logger,
        organization_name: str,
        s3_bucket: typing.Optional[str] = None,
        **connector_params,
    ) -> None:
        """ Instantiates MasternautData object containing fleet data from
        Masternaut.

        :param folder: str path to the root folder where all the data is
            stored.
        :param log_file: file where to write logs
        """
        secrets = get_local_secret(
            logger=logger,
        )
        connector_params['base_url'] = secrets[
            f'{organization_name}_{self.CONNECTOR_NAME}_URL'.upper()
        ]
        connector_params['api_key'] = secrets[
            f'{organization_name}_{self.CONNECTOR_NAME}_KEY'.upper()
        ]
        connector_params['headers'] = {
            'Authorization': f'lucca application={connector_params['api_key']}',
            'Accept': 'application/json',
        }
        super().__init__(
            connector_folder=connector_folder,
            logger=logger,
            organization_name=organization_name,
            s3_bucket=s3_bucket,
            **connector_params
        )


@attach_dataset(LuccaData)
class LuccaCollaboratorSource(DataSource):

    NAME = 'COLLABORATORS'

    def __fetch__(self: typing.Self) -> typing.Sequence[str]:
        return ('users', )

    def __parse__(
        self: typing.Self,
        data_path: typing.Sequence[str],
        **parsing_params: typing.Dict[str, typing.Any],
    ) -> typing.Optional[pd.DataFrame]:
        """ Load Lucca collaborators data as a pandas Dataframe

        :returns: collaborators df df
        """
        param_dict = form_field_params(
            'id',
            'name',
            'lastName',
            'firstName',
            'mail',
            'dtContractStart',
            'dtContractEnd',
            'employeeNumber',
            'department',
            'jobTitle',
            'picture',
            'manager',
            'extendedData',
            'professionalMobile',
            'personalMobile',
            'civilTitle',
            'birthDate',
            'address',
        )
        # See https://lucca.stoplight.io/docs/lucca-legacyapi/u681uu1emh7g0-users-examples
        # Poorly named argument but that returns all employees, including former ones
        param_dict['formerEmployees'] = 'true'

        collaborators_df = load_from_api(
            organization_name=self.organization_name,
            url=(
                f'{parsing_params['base_url']}/'
                f'{data_path[0]}'
            ),
            headers=parsing_params['headers'],
            response_keys=['data', 'items'],
            params=param_dict,
            col_lst=[
                CollaboratorsModel.collaborator_connector_id.return_variant(
                    raw_name='id',
                ),
                CollaboratorsModel.employee_full_name.return_variant(
                    raw_name='name',
                ),
                CollaboratorsModel.firstname.return_variant(
                    raw_name='firstName',
                ),
                CollaboratorsModel.lastname.return_variant(
                    raw_name='lastName',
                ),
                CollaboratorsModel.email.return_variant(
                    raw_name='mail',
                ),
                CollaboratorsModel.employee_entry_date.return_variant(
                    raw_name='dtContractStart',
                ),
                CollaboratorsModel.employee_exit_date.return_variant(
                    raw_name='dtContractEnd',
                ),
                CollaboratorsModel.organization_collaborator_id.return_variant(
                    raw_name='employeeNumber',
                ),
                BusinessUnitsModel.entity_3.return_variant(
                    raw_name='department',
                    post_processing=DictColumnGetter(('id', )),
                    dtype='Int64'
                ),
                CollaboratorsModel.role.return_variant(
                    raw_name="jobTitle",
                ),
                CollaboratorsModel.manager_connector_id.return_variant(
                    post_processing=DictColumnGetter(('id', )),
                ),
                CollaboratorsModel.picture_href.return_variant(
                    post_processing=DictColumnGetter(('href', )),
                ),
                CollaboratorsModel.added_data.return_variant(
                    raw_name='extendedData',
                ),
                CollaboratorsModel.professional_phone_number.return_variant(
                    raw_name='professionalMobile',
                    post_processing=convert_string,
                ),
                CollaboratorsModel.personal_phone_number.return_variant(
                    raw_name='personalMobile',
                    post_processing=convert_string,
                ),
                CollaboratorsModel.civility.return_variant(
                    raw_name='civilTitle',
                ),
                CollaboratorsModel.birthdate.return_variant(
                    raw_name='birthDate',
                ),
                CollaboratorsModel.personal_address.return_variant(
                    raw_name='address',
                ),
            ],
            record_dates=[
                CollaboratorsModel.employee_entry_date.name,
                CollaboratorsModel.employee_exit_date.name
            ],
            connector_name=self.CONNECTOR_NAME,
            source_dataset=self.DATASET_NAME,
            synchronization_type=self.DATASET_TYPE,
            source_table=self.NAME,
        )

        # Fetch manager
        manager_df = collaborators_df[
            [
                CollaboratorsModel.collaborator_connector_id.name,
                CollaboratorsModel.email.name,
                CollaboratorsModel.employee_full_name.name,
            ]
        ].rename(
            {
                CollaboratorsModel.collaborator_connector_id.name: CollaboratorsModel.manager_connector_id.name,
                CollaboratorsModel.email.name: CollaboratorsModel.manager_email.name,
                CollaboratorsModel.employee_full_name.name: CollaboratorsModel.manager_full_name.name,
            },
            axis=1,
        )
        collaborators_df = collaborators_df.merge(
            manager_df,
            how='left',
            on=CollaboratorsModel.manager_connector_id.name,
            validate='m:1',
        )
        collaborators_df[CollaboratorsModel.manager_full_name.name] = (
            NamesConverter(self.organization_name)(
                collaborators_df[CollaboratorsModel.manager_full_name.name]
            )
        )

        # Extended data
        if self.organization_name == 'acorus':
            ikb_tup = (
                collaborators_df[CollaboratorsModel.added_data.name].apply(
                    get_ikb_value_date
                )
            )
            collaborators_df[VehicleAssociationsModel.monthly_ikb_value.name] = ikb_tup.str[0]
            collaborators_df[VehicleAssociationsModel.ikb_start_date.name] = ikb_tup.str[1]
            collaborators_df[CollaboratorsModel.personal_postal_code.name] = (
                DictColumnGetter(('e_Codepostal', 'value'))(
                    collaborators_df[CollaboratorsModel.added_data.name]
                )
            )
            collaborators_df[CollaboratorsModel.birthplace.name] = (
                DictColumnGetter(('e_birthplace', 'value'))(
                    collaborators_df[CollaboratorsModel.added_data.name]
                )
            )
            collaborators_df[CollaboratorsModel.personal_street_number.name] = (
                DictColumnGetter(('e_Numerodevoie', 'value'))(
                    collaborators_df[CollaboratorsModel.added_data.name]
                )
            )
            collaborators_df[CollaboratorsModel.personal_street_name.name] = (
                DictColumnGetter(('e_Nom-de-la-voie', 'value'))(
                    collaborators_df[CollaboratorsModel.added_data.name]
                )
            )
            collaborators_df[CollaboratorsModel.personal_city.name] = (
                DictColumnGetter(('e_Ville', 'value'))(
                    collaborators_df[CollaboratorsModel.added_data.name]
                )
            )
            collaborators_df[BusinessUnitsModel.legal_entity.name] = (
                DictColumnGetter(('e_Societe2', 'value'))(
                    collaborators_df[CollaboratorsModel.added_data.name]
                )
            ).astype("Int64")
            legal_entity_mapping = get_extended_data_mapping(
                base_url=parsing_params['base_url'],
                headers=parsing_params['headers'],
                mapping_name='e_Societe2'
            )
            assert set(
                collaborators_df.loc[
                    collaborators_df[BusinessUnitsModel.legal_entity.name].notna(),
                    BusinessUnitsModel.legal_entity.name
                ].unique()
            ).difference(legal_entity_mapping) == set(), 'Some legal entities could not be found in the mapping'
            collaborators_df[BusinessUnitsModel.legal_entity.name] = (
                collaborators_df[BusinessUnitsModel.legal_entity.name].map(
                    legal_entity_mapping
                )
            )

            # After discussion with Acorus, we remove some collaborators
            # which are duplicates of existing ones
            collaborators_df = collaborators_df.loc[
                ~collaborators_df[CollaboratorsModel.email.name].isin(
                    [
                        'mickael.goncalves1@groupe-acorus.fr',
                        'aj.pereira@groupe-acorus.fr',
                        'BILEL.CHALHAFI@GROUPE-ACORUS.FR',
                        'melanie.pereira@groupe-acorus.fr',
                        'ndiaye@groupe-acorus.fr'
                    ]
                )
            ]

            # Some other names are irrelevant and should be removed
            collaborators_df = collaborators_df.loc[
                ~collaborators_df[CollaboratorsModel.employee_full_name.name].isin(
                    ['test test']
                )
            ]

            # On the contrary some employees share the same name
            # and are not duplicates
            are_homonyms = (
                (collaborators_df[CollaboratorsModel.lastname.name] == 'DE OLIVEIRA')
                &
                (collaborators_df[CollaboratorsModel.firstname.name] == 'JULIEN')
            )
            collaborators_df[CollaboratorsModel.employee_full_name.name] = (
                collaborators_df[CollaboratorsModel.employee_full_name.name].mask(
                    are_homonyms,
                    collaborators_df[CollaboratorsModel.email.name].map(
                        {
                           'julien.deoliveira@groupe-acorus.fr': '1903 de julien oliveira',
                           'julien.oliveira@groupe-acorus.fr': '2783 de julien oliveira',
                        }
                    ),
                )
            )

        if self.organization_name == 'groupe-batisseur-d-avenir':
            collaborators_df[CollaboratorsModel.personal_postal_code.name] = (
                DictColumnGetter(('e_Codepostal', 'value'))(
                    collaborators_df[CollaboratorsModel.added_data.name]
                )
            )
            collaborators_df[CollaboratorsModel.birthplace.name] = (
                DictColumnGetter(('e_birthplace', 'value'))(
                    collaborators_df[CollaboratorsModel.added_data.name]
                )
            )
            collaborators_df[CollaboratorsModel.personal_street_number.name] = (
                DictColumnGetter(('e_Numero-de-la-voie', 'value'))(
                    collaborators_df[CollaboratorsModel.added_data.name]
                )
            )
            collaborators_df[CollaboratorsModel.personal_street_name.name] = (
                DictColumnGetter(('e_Nomdelavoie', 'value'))(
                    collaborators_df[CollaboratorsModel.added_data.name]
                )
            )
            collaborators_df[CollaboratorsModel.personal_city.name] = (
                DictColumnGetter(('e_Ville', 'value'))(
                    collaborators_df[CollaboratorsModel.added_data.name]
                )
            )

        collaborators_df = collaborators_df.drop(
            columns=CollaboratorsModel.added_data.name
        )

        # Build entities
        entity_3_to_bu_mapping = load_organizations(
            base_url=parsing_params['base_url'],
            headers=parsing_params['headers'],
        )
        collaborators_df[BusinessUnitsModel.business_unit.name] = (
            collaborators_df[BusinessUnitsModel.entity_3.name].map(
                entity_3_to_bu_mapping
            )
        )
        assert (
            pd.notna(
                collaborators_df[BusinessUnitsModel.business_unit.name]
            ) == pd.notna(
                collaborators_df[BusinessUnitsModel.entity_3.name]
            )
        ).all(), 'Some departments could not be found in the organization mapping'

        # Replace entity 3 id with name
        collaborators_df[BusinessUnitsModel.entity_3.name] = (
            collaborators_df[BusinessUnitsModel.business_unit.name].str.split(
                ' > '
            ).str[-1]
        )

        collaborators_df = correct_business_unit(
            entity_df=collaborators_df,
            logger=self.logger,
            organization_name=self.organization_name,
        )

        if self.organization_name == 'acorus':
            # Drop BU / entities which do not stem from "GROUPE"
            # See email from Xiang Hei Friday 14 of March 2025
            bu_to_keep = (
                collaborators_df[BusinessUnitsModel.business_unit.name].str.startswith('GROUPE')
            )
            invalid_bu = collaborators_df.loc[
                ~bu_to_keep,
                BusinessUnitsModel.business_unit.name
            ]

            if len(invalid_bu):
                self.logger.error(
                    'There are bu names not starting by Groupe in Acorus: %s',
                    invalid_bu.unique()
                )
                for col in [
                    BusinessUnitsModel.business_unit.name,
                    BusinessUnitsModel.entity_3.name,
                ]:
                    collaborators_df[col] = collaborators_df[col].where(
                        bu_to_keep,
                        None,
                    )

            # Deduplicate
            collaborators_df['_temp_exit_date'] = pd.to_datetime(
                collaborators_df[CollaboratorsModel.employee_exit_date.name]
            ).fillna(pd.Timestamp('2099-12-31'))
            original_len = len(collaborators_df)
            collaborators_df.sort_values(
                by=[
                    CollaboratorsModel.employee_full_name.name,
                    CollaboratorsModel.email.name,
                    '_temp_exit_date',
                    CollaboratorsModel.employee_entry_date.name,
                ],
                ascending=[True, True, False, False],
                inplace=True,
            )
            collaborators_df.drop_duplicates(
                subset=[
                    CollaboratorsModel.employee_full_name.name,
                    CollaboratorsModel.email.name,
                ],
                inplace=True,
            )
            self.logger.info(
                'Deduplicated collaborators from %d to %d rows',
                original_len,
                len(collaborators_df),
            )

        # Phones
        for phone_col in [
            CollaboratorsModel.professional_phone_number.name,
            CollaboratorsModel.personal_phone_number.name,
        ]:
            collaborators_df[phone_col] = convert_phone_number(
                collaborators_df[phone_col],
                errors='drop',
            )

        return collaborators_df


if __name__ == '__main__':
    LuccaData.local_test(
        organization_name='acorus',
    )
