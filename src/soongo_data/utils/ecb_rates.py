import io
import time
from typing import Optional

import numpy as np
import pandas as pd
import requests

from soongo_data.utils.logging_utils import gen_logger

logger = gen_logger('Rent_Cost - ECB_Rates')

ECB_API_URL = "https://data-api.ecb.europa.eu/service/data/FM/{key}"

# Opérations principales de refinancement :
#  - MRR_FR  : taux fixe (avant juin 2000, puis depuis octobre 2008)
#  - MRR_MBR : taux minimal de soumission, appels d'offres à taux variable (2000-2008)
# En combinant les deux séries on obtient un taux valable à chaque date.
ECB_SERIES = ("D.U2.EUR.4F.KR.MRR_FR.LEV", "D.U2.EUR.4F.KR.MRR_MBR.LEV")


def _fetch_series(key: str, start_period: str, timeout: int) -> pd.DataFrame:
    response = requests.get(
        ECB_API_URL.format(key=key),
        params={"format": "csvdata", "startPeriod": start_period, "detail": "dataonly"},
        headers={"Accept": "text/csv"},
        timeout=timeout,
    )
    response.raise_for_status()
    raw = pd.read_csv(io.StringIO(response.text))
    if "TIME_PERIOD" not in raw.columns or "OBS_VALUE" not in raw.columns:
        raise ValueError(f"Format inattendu pour {key}: colonnes {list(raw.columns)}")
    out = pd.DataFrame({
        "date": pd.to_datetime(raw["TIME_PERIOD"], errors="coerce"),
        "rate": pd.to_numeric(raw["OBS_VALUE"], errors="coerce"),
    }).dropna()
    return out


def fetch_ecb_rates(start_period: str = "2005-01-01", timeout: int = 30, retries: int = 3) -> pd.DataFrame:
    """Télécharge l'historique du taux de refinancement BCE.
    Retourne un DataFrame ['date', 'rate'] trié par date (taux en %).
    Lève RuntimeError si l'API est injoignable : on préfère échouer que d'utiliser
    silencieusement un taux périmé."""
    frames = []
    for key in ECB_SERIES:
        last_error = None
        for attempt in range(1, retries + 1):
            try:
                frames.append(_fetch_series(key, start_period, timeout))
                last_error = None
                break
            except Exception as e:  # réseau, HTTP, format
                last_error = e
                logger.warning(f"ECB API {key} (tentative {attempt}/{retries}) : {e}")
                if attempt < retries:
                    time.sleep(2 * attempt)
        if last_error is not None and not frames:
            # la 1re série (taux fixe) est indispensable
            raise RuntimeError(f"Impossible de récupérer les taux BCE ({key}): {last_error}")

    rates = pd.concat(frames, ignore_index=True)
    if rates.empty:
        raise RuntimeError("Les taux BCE récupérés sont vides")

    # Si les deux séries se recouvrent un jour donné, on garde la première (taux fixe)
    rates = rates.drop_duplicates(subset="date", keep="first").sort_values("date").reset_index(drop=True)
    logger.info(
        f"Taux BCE chargés : {len(rates)} jours, de {rates['date'].min().date()} "
        f"à {rates['date'].max().date()} (dernier taux : {rates['rate'].iloc[-1]}%)"
    )
    return rates


def add_ecb_features(
    df: pd.DataFrame,
    rates: Optional[pd.DataFrame] = None,
    date_col: str = "lease_start_date",
) -> pd.DataFrame:
    """Ajoute 'ecb_rate' (taux BCE en vigueur à la date de début du contrat) et
    'interest_per_month' (prix * taux / 1200), puis retire la colonne de date.
    Date absente ou antérieure au début de l'historique -> ecb_rate = NaN."""
    df = df.copy()
    if rates is None:
        rates = fetch_ecb_rates()

    rates = rates.sort_values("date")[["date", "rate"]].copy()
    rates["date"] = rates["date"].astype("datetime64[ns]")

    dates = pd.to_datetime(df[date_col], errors="coerce", utc=True).dt.tz_localize(None)
    left = pd.DataFrame({"_date": dates.astype("datetime64[ns]"), "_pos": np.arange(len(df))})
    left = left.dropna(subset=["_date"]).sort_values("_date")

    merged = pd.merge_asof(left, rates, left_on="_date", right_on="date", direction="backward")

    ecb_rate = np.full(len(df), np.nan)
    ecb_rate[merged["_pos"].values] = merged["rate"].values
    df["ecb_rate"] = ecb_rate

    if "vehicle_price" in df.columns:
        df["interest_per_month"] = df["vehicle_price"].astype(float) * df["ecb_rate"] / 1200.0

    return df.drop(columns=[date_col])