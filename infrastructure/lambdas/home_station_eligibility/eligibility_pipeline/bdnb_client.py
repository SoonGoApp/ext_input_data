import requests
from soongo_data.utils.logging_utils import gen_logger


logger = gen_logger("BDNB_Client")

REQUEST_TIMEOUT = 10
MAX_RETRIES = 3
BDNB_BASE_URL = "https://api.bdnb.io/v1/bdnb"


def get_cle_interop_adr(address: str) -> str | None:
    try:
        resp = requests.get(
            f"{BDNB_BASE_URL}/geocodage",
            params={"q": address},
            timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()

        features = resp.json().get("features", [])
        
        if len(features) == 0:
            return None

        cle_interop_adr = features[0]["properties"]["id"]

        return cle_interop_adr

    except Exception as e:
        logger.exception(f"Failed to fetch geocode info, Exception: {e}")
        return None


def get_building_usage(cle_interop_adr: str) -> str | None:
    try:
        resp = requests.get(
            f"{BDNB_BASE_URL}/donnees/batiment_groupe_complet/adresse",
            params={"cle_interop_adr": f"eq.{cle_interop_adr}"},
            timeout=REQUEST_TIMEOUT
        )

        resp.raise_for_status()
        data = resp.json()

        if len(data) != 0:
            data = data[0]
            building_usage = data.get("usage_principal_bdnb_open")
            
            return building_usage
        
        return None

    except Exception as e:
        logger.exception(f"Failed to fetch building info, Exception: {e}")
        return None
