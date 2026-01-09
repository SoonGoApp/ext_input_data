import re
import pandas as pd


from soongo_data.utils.type import str_is_nan, DictColumnGetter
from soongo_data.data_models import CollaboratorsModel
from soongo_data.utils.adress_utils.codes_postaux import COMMUNES
from soongo_data.utils.adress_utils.departements import DEPARTEMENTS
from soongo_data.utils.adress_utils.cedex import CEDEX


class SoonGoFrAdressParser:
    """
    Parser d'adresse FR.

    Credit: Maxime Challon https://github.com/MaximeChallon/AdresseParser/blob/master/AdresseParser
    """
    STREET_BLOC_REGEX = "^(([0-9]+)( ?(B|BIS|T|TER|QUATER|C|D|E|F) )?) ?(.+)?"

    def __init__(self):
        self.regex_rue = '((AVENUE|IMPASSE|QUAI|VOIE|RUELLE|PLACE|BOULEVARD|RUE|VOIE|CIT(E|É)|ALL(É|E)E|CHEMIN|ROUTE|GR|R(É|E)SIDENCE|HAMEAU|LIEU(-| )DIT|TRAVERSE|PROMENADE|ROND(-| )POINT|PASSAGE)( D(E(S?| LA)|U))? )'
        self.type_rue = ['rue', 'avenue', 'boulevard', 'impasse', 'quai', 'voie', 'place', 'ruelle', 'cour', 'cité', 'cite', 'allée','allee','chemin','lieu-dit','promenade','lieu dit','rond point', 'rond-point', 'passage','traverse','route','gr','résidence','residence','hameau']
        self.cedex = pd.DataFrame(CEDEX)

    def parse(self, adresse_string):
        """
        Parse la chaîne mise en paramètre et retourne un dictionnaire
        :param adresse_string: chaîne de caractères de l'adresse
        :return: dict
        """
        bloc_rue, bloc_ville = self.blocs(adresse_string)

        nom_rue = re.sub(
            r'([0-9]+)( ?(B|BIS|T|TER|QUATER|C|D|E|F) )?',
            '',
            bloc_rue,
            flags=re.IGNORECASE,
        ).strip()
        ville, _ = self.get_ville(bloc_ville)

        code_postal, _ = self.get_code_postal(bloc_ville)

        numero, indice = self.get_numero_rue(bloc_rue)

        if numero is None:
            street_number = None
        else:
            street_number = numero + ((" " + indice) if indice else "")

        dict_adresse = {
            CollaboratorsModel.personal_street_number.name: street_number,
            CollaboratorsModel.personal_street_name.name: nom_rue,
            CollaboratorsModel.personal_postal_code.name: code_postal,
            CollaboratorsModel.personal_city.name: ville,
        }

        return dict_adresse

    def blocs(self, adresse_string):
        """
        Permet d'extraire l'adresse' de la requête de l'utilisateur
        :param requete: requête faite dans l'api
        :return: str
        """
        # retournement de l'adresse donnée en string pour la mettre sous la forme Numéro_rue Rue Code_postal Ville
        # si le code postal est au début
        if re.match("^[0-9]{5}[a-zA-Z éèàùêôî-]{0,}[0-9]{1,4}(.+)$", adresse_string):
            pattern = "^([0-9]{5}[a-zA-Z éèàùêôî-]{0,})([0-9]{0,4}.+)$"
            requete = re.match(pattern, adresse_string).group(2) +" "+ re.match(pattern, adresse_string).group(1)

        # si le bloc_ville est au début et qu'il n'y a pas de numéro de rue
        elif re.match("[0-9]{5} ?.+ ?([r|R]ue|RUE|[a|A]venue|AVENUE|[b|B]oulevard|BOULEVARD|QUAI|[q|Q]uai|PLACE|[p|P]lace).+", adresse_string):
            pattern = "^([0-9]{5} ?.+) ?(([r|R]ue|RUE|[a|A]venue|AVENUE|[b|B]oulevard|BOULEVARD|QUAI|[q|Q]uai|PLACE|[p|P]lace).+)$"
            requete = re.match(pattern, adresse_string).group(2) + " " + re.match(pattern, adresse_string).group(1)

        # si le code postal est en deuxième partie
        elif re.match("^[0-9]{0,4}.*[0-9]{5}[a-zA-Z éèàùêôî-]{0,}$", adresse_string):
            requete = adresse_string

        else:
            requete = adresse_string

        # à partir de l'adresse normalisée, extraction des différents blocs d'information
        # vérification de la présence d'un cedex dans l'adresse en premier lieu
        if "cedex" in requete.lower():
            if re.match("^[0-9]{0,4}.*[0-9]{5}.*$", requete):
                bloc_rue = re.sub("[0-9]{5}.*", "", requete)
                bloc_ville = re.match("^[0-9]{0,4}.*([0-9]{5}.*)$", requete).group(1)

        else:
            if re.match("^[0-9]{0,4}.*[0-9]{5}[a-zA-Z éèàùêôî-]{0,}$", requete):
                bloc_rue = re.sub("[0-9]{5}.*", "", requete)
                bloc_ville = re.match("^[0-9]{0,4}.*([0-9]{5}[a-zA-Z éèàùêôî-]{0,})$", requete).group(1)

            elif re.match("^[0-9]{0,4}.*$", requete):
                bloc_rue = re.sub("[0-9]{5}.*", "", requete)
                bloc_ville = re.match("^([0-9]{5}[a-zA-Z éèàùêôî-]{0,})[0-9]{0,4}.*$", requete)
                if bloc_ville is not None:
                    bloc_ville = bloc_ville.group(1)

        return (bloc_rue, bloc_ville)

    def get_numero_rue(self, bloc_rue):
        """
        Permet d'extraire le numéro de la rue et son indice
        :param bloc_rue: string avec le numéro et le nom de la rue
        :return: tuple(str, str)
        """
        indice_mapping = {
            "B": "BIS",
            "BI": "BIS",
            "BIS": "BIS",
            "T": "TER",
            "TE": "TER",
            "TER": "TER",
            "C": "TER",
            "Q": "QUATER",
            "QUATER": "QUATER",
            "D": "QUATER",
        }

        if re.match(
            self.STREET_BLOC_REGEX,
            bloc_rue,
            flags=re.IGNORECASE,
        ):
            combined_number_index = str(
                re.match(
                    self.STREET_BLOC_REGEX,
                    bloc_rue,
                    flags=re.IGNORECASE,
                ).group(1)
            )
            combined_number_index = combined_number_index.replace(" ", "").lower()
            numero_rue = re.sub(
                r'[^0-9\-]',
                '',
                combined_number_index,
                flags=re.IGNORECASE,
            )
            indice = str(
                re.sub(
                    r'[0-9\-]',
                    '',
                    combined_number_index,
                    flags=re.IGNORECASE,
                )
            ).upper()
            if indice == '':
                indice = None
            else:
                indice = indice_mapping.get(indice.upper())

        else:
            numero_rue = None
            indice = None

        return numero_rue, indice

    def get_nom_type_rue(self, bloc_rue):
        """
        Permet d'extraire le nom et le type de la rue
        :param bloc_rue: string avec le numéro et le nom de la rue
        :return: str
        """
        nom_rue = re.sub(
            self.regex_rue,
            "",
            re.sub(
                self.STREET_BLOC_REGEX,
                "",
                bloc_rue.upper(),
                flags=re.IGNORECASE,
            )
        )
        nom_rue = re.sub(" +$", "", nom_rue)

        type = ""

        for type_rue in self.type_rue:
            if (type_rue + " ") in bloc_rue.lower():
                type = type_rue.upper()
                break

        return nom_rue, type

    def get_code_postal(self, bloc_ville):
        """
        Extrait le code postal s'il existe
        :param bloc_ville: string avec code postal et ville
        :return: int
        """
        if bloc_ville is None or not re.match("([0-9]{5}) ?([^0-9]+)?", bloc_ville):
            return None, None

        code_postal = re.match("([0-9]{5}) ?([^0-9]+)?", bloc_ville).group(1)

        numero_dpt = int(re.sub('[0-9]{3}$', '', str(code_postal)))
        if int(numero_dpt) < 10:
            numero_dpt = "0" + str(numero_dpt)
        if 20000 <= int(code_postal) < 21000:
            if int(code_postal) <= 20190:
                numero_dpt = "2A"
            else:
                numero_dpt = "2B"

        return code_postal, numero_dpt

    def get_ville(self, bloc_ville):
        """
        Extrait la ville et l'arrondissement si nécessaire
        :param bloc_ville: string avec le code postal et la ville
        :return: str
        """
        if bloc_ville is not None:
            code_postal, _ = self.get_code_postal(bloc_ville)

            if re.match("[0-9]{5} ?[^0-9]+(cedex.*)?$", str(bloc_ville).lower()):
                ville = re.sub("[0-9]{5} ?", "", str(bloc_ville))
                ville = re.sub(" ?cedex.*", "", str(ville).lower())
                ville = ville.upper().rstrip()
            else:
                ville = COMMUNES.get(code_postal, '').upper().rstrip()

            if "PARIS" in ville or "LYON" in bloc_ville or "MARSEILLE" in bloc_ville or re.match('^75[0-9]{3}', code_postal):
                arrondissement = int(re.sub("^0+", "", code_postal.replace('75', '')))
                if arrondissement > 20:
                    arrondissement = None
            else:
                arrondissement = None
        else:
            arrondissement = None
            ville = ""

        return ville, arrondissement

    def get_cedex(self, bloc_ville, code_postal):
        """
        Extrait le cedex s'il existe
        :param bloc_ville: string 
        :param code_postal: string
        :return: str
        """
        cedex = []
        if bloc_ville:
            if "cedex" in bloc_ville.lower():
                result = self.cedex[self.cedex['cedex'] == int(code_postal)]
                for _, row in result.iterrows():
                    cedex.append(
                        {
                            "libelle": row['libelle'],
                            "code_insee": str(row['insee'])
                        }
                    )

        return cedex


def parse_address(
    address_series: pd.Series,
    country: str = 'FRA',
) -> pd.DataFrame:
    """Parse an address series into its components using the usaddress library

    :param address_series: a Series of addresses as strings

    :returns: DataFrame with columns for each component of the address
    """
    if country != 'FRA':
        raise NotImplementedError(
            f'Address parsing not implemented for country {country}'
        )
    parser = SoonGoFrAdressParser()

    addresses_part_df = pd.DataFrame(
        [
            parser.parse(address)
            if not str_is_nan(pd.Series([address])).any() else {}
            for address in address_series
        ],
        index=address_series.index
    )

    return addresses_part_df


def parse_df_adress(adress_df: pd.DataFrame) -> pd.DataFrame:
    """Parse a DataFrame of addresses into their components using the AdressParser library

    :param adress_df: a DataFrame with at least one column 'personal_address'

    :returns: DataFrame with columns for each component of the address
    """
    if CollaboratorsModel.personal_address.name not in adress_df.columns:
        raise ValueError(
            f"Input DataFrame must contain a column named '{CollaboratorsModel.personal_address.name}'"
        )

    parsed_address_df = parse_address(
        adress_df[CollaboratorsModel.personal_address.name],
        country='FRA',
    )

    for col in parsed_address_df.columns:
        if col in adress_df.columns:
            adress_df[col] = adress_df[col].fillna(parsed_address_df[col])
        else:
            adress_df[col] = parsed_address_df[col]

    return adress_df
