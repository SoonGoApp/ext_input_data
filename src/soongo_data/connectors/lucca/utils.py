import requests
import typing

import pandas as pd


def form_field_params(*args: str) -> typing.Dict[str, str]:
    """ form field params, e.g. the field dictionary to pass to requests
    to return the requested lucca API fields

    :args: string name of fields to return

    :returns: dictionnary of strings to strings
    """
    return {'fields': ','.join(args)}


def get_extended_data_mapping(
    base_url: str,
    headers: dict,
    mapping_name: str,
) -> typing.Dict:
    """ Fetch an extensionuserdefition mapping for extended data id

    :param mapping_name: the route of the mapping to fetch
    """
    response = requests.get(
        url=f'{base_url}/extensionuserdefinitions/{mapping_name}',
        params=None,
        headers=headers,
        auth=None,
    ).json()['data']

    mapping = {
        entry['id']: entry['name']
        for entry in
        response['extensionUserPropertyListEntries']
    }
    return mapping


def load_organizations(base_url, headers) -> dict:
    """ Load acorus organization tree as a recursive dictionary

    :returns: entity to business unit dictionary mapping
    """
    organization_tree = requests.get(
        url=f'{base_url}/departments/tree',
        headers=headers,
    ).json()['data']['children']

    active_bu_dict = build_business_units_from_tree(organization_tree)

    old_organization_tree = requests.get(
        url=f'{base_url}/departments/tree',
        headers=headers,
        params={'isActive': 'false'}
    ).json()['data']['children']

    old_bu_dict = build_business_units_from_tree(old_organization_tree)

    # Should there be any overlap between old and active, use active
    old_bu_dict.update(active_bu_dict)
    return old_bu_dict


def build_business_units_from_tree(
    org_tree: dict,
    previous_entity_bu: typing.Optional[str] = None,
    current_entity_bu_dict: typing.Optional[dict] = None,
) -> dict:
    """ Build a dictionary mapping entities to business units from the
    organization tree

    :param org_tree: organization tree dictionary

    :returns: entity to business unit dictionary mapping
    """
    if current_entity_bu_dict is None:
        current_entity_bu_dict = {}
    for entity in org_tree:
        entity_name = entity['node']['name']
        entity_id = entity['node']['id']
        assert entity_id not in current_entity_bu_dict, 'Entity already exists'
        entity_bu = (
            f'{previous_entity_bu} > {entity_name}' if previous_entity_bu
            else entity_name
        )
        current_entity_bu_dict[entity_id] = entity_bu
        if 'children' in entity:
            current_entity_bu_dict = build_business_units_from_tree(
                entity['children'],
                entity_bu,
                current_entity_bu_dict,
            )

    return current_entity_bu_dict


def get_ikb_value_date(
    added_data: dict
) -> typing.Tuple[typing.Optional[float], pd.Timestamp]:
    """ Get the IKB value from the extended data dictionary

    :param added_data: extended data dictionary

    :returns: IKB value, IKB start_date
    """
    if not added_data:
        return None, pd.NaT
    ikb_dict = added_data.get('e_Avantgae-en-nature', {})
    if not ikb_dict:
        return None, pd.NaT
    return (
        ikb_dict.get('value', {}).get('e_Montant', {}).get('value', {}),
        pd.to_datetime(
            ikb_dict.get(
                'value',
                {}
            ).get(
                'e_Prise-d-effet_AN',
                {}
            ).get(
                'value',
                {}
            )
        )
    )
