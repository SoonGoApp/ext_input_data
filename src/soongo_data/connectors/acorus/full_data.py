""" Acorus Data

Class loading, normalizing and organizing all datasets exported manually by
Domino, mostly for HR purposes
"""
from soongo_data.connectors import Connector


class AcorusConnector(Connector):

    NAME = 'ACORUS'


if __name__ == '__main__':
    AcorusConnector.local_test(
        organization_name='acorus',
    )
