import requests
from eligibility_pipeline.logger import get_logger


logger = get_logger("BDNB_Client")

REQUEST_TIMEOUT = 10
MAX_RETRIES = 3
BDNB_BASE_URL = "https://api.bdnb.io/v1/bdnb"


def get_geocode_data(address: str) -> str | None:
    try:
        resp = requests.get(
            f"{BDNB_BASE_URL}/geocodage",
            params={"q": address},
            timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()

        features = resp.json().get("features", [])
        
        if len(features) == 0:
            return None, None, None

        cle_interop_adr = features[0]["properties"]["id"]
        longitude = features[0]["geometry"]["coordinates"][0]
        latitude = features[0]["geometry"]["coordinates"][1]

        return cle_interop_adr, longitude, latitude

    except Exception as e:
        logger.exception(f"Failed to fetch geocode info, Exception: {e}")
        return None


def get_building_infos(cle_interop_adr: str) -> str | None:
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

            usage_batiment = data.get("usage_principal_bdnb_open")
            type_batiment = data.get("type_batiment_dpe")
            nb_logement = data.get("nb_log")
            nb_niveau = data.get("nb_niveau")
            s_geom = data.get("s_geom_groupe")
            surface = data.get("surface_emprise_sol")

            return usage_batiment, type_batiment, nb_logement, nb_niveau, s_geom, surface
        return None, None, None, None, None, None

    except Exception as e:
        logger.exception(f"Failed to fetch building info, Exception: {e}")
        return None
