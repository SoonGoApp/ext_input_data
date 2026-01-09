""" Lucca Data

Class loading, normalizing and organizing all Masternaut Datasets for a given
organization
"""
from soongo_data.connectors import Connector


class LuccaConnector(Connector):
    NAME = 'LUCCA'


if __name__ == '__main__':
    LuccaConnector.local_test(
        organization_name='groupe-batisseur-d-avenir',
    )
