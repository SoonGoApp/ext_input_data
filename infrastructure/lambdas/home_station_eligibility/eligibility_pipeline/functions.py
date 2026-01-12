import pandas as pd
import re


def clean_street_number(value):
    if pd.isna(value):
        return ""
    value = str(value).strip()
    value = re.sub(r"\.0$", "", value)
    return value

def create_full_address(row) -> str:
    address = row["personal_address"]
    street_number = row["personal_street_number"]
    street_name = row["personal_street_name"]
    post_code = row["personal_postal_code"]
    city = row["personal_city"]

    address = "" if pd.isna(address) else str(address).strip()
    street_number = clean_street_number(street_number)
    street_name = "" if pd.isna(street_name) else str(street_name).strip()
    post_code = "" if pd.isna(post_code) else str(post_code).strip()
    city = "" if pd.isna(city) else str(city).strip()

    new_address = ""

    if address == "":
        if street_number or street_name:
            new_address = f"{street_number} {street_name}".strip()
    else:
        parts = address.split()
        if parts and parts[0].isdigit() and len(parts) >= 2:
            new_address = address

    if not new_address:
        return None

    full_address = f"{new_address} {post_code} {city}".strip()
    return full_address.upper()