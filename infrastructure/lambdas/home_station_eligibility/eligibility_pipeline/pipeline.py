import pandas as pd
from eligibility_pipeline.bdnb_client import get_geocode_data, get_building_infos
import eligibility_pipeline.repository as rp
from soongo_data.utils.logging_utils import gen_logger


logger = gen_logger("Pipeline")
rows_nb = 20


def geocode_pipeline(config: dict, df: pd.DataFrame, process_type: str):
    try:
        results = []
        
        if rows_nb is not None:
            rows = df.head(rows_nb).iterrows()
        else:
            rows = df.iterrows()

        for _, row in rows:
            cle_interop_adr, longitude, latitude = get_geocode_data(
                row.full_address 
            )

            results.append({
                "collaborator_id": row.id,
                "personal_address": row.full_address,
                "cle_interop_adr": cle_interop_adr,
                "longitude": longitude,
                "latitude": latitude,
                "source": "BDNB"
            })

        output_df = pd.DataFrame(results)

        #  Insert Output
        rp.insert_collaborators_geocode_data(config, output_df, process_type)

        logger.info(f"{process_type.upper()} Geocode Pipeline completed – {len(output_df)} rows {process_type}ed")

    except Exception as e:
        logger.exception(f"{process_type.upper()} Geocode Pipeline - Failed to run Geocode, Exception: {e}")
        raise



def home_stattion_eligibility_pipeline(config: dict, df: pd.DataFrame, process_type: str):
    try:
        results = []

        if rows_nb is not None:
            rows = df.head(rows_nb).iterrows()
        else:
            rows = df.iterrows()

        for _, row in rows:
            usage_batiment, type_batiment, nb_logement, nb_niveau, s_geom, surface = get_building_infos(
                row.cle_interop_adr
            )
            eligible = eligible = None if usage_batiment is None else ('yes' if 'individuel' in usage_batiment.lower() else 'no')

            garden = (
                s_geom is not None
                and surface is not None
                and surface != s_geom
            )
            garden = 'yes' if garden else 'no'

            results.append({
                "collaborator_id": row.collaborator_id,
                "personal_address": row.personal_address,
                "eligibility_status": eligible,
                "building_usage": usage_batiment,
                "building_type": type_batiment,
                "housing_units": nb_logement,
                "building_levels": nb_niveau,
                "ground_surface": s_geom,
                "total_surface": surface,
                "has_garden": garden,
                "source": "BDNB"
            })

        output_df = pd.DataFrame(results)
        output_df_processed = output_df.dropna(subset=['collaborator_id', 'eligibility_status'])

        #  Insert Output
        rp.insert_collaborators_eligibility_data(config, output_df, process_type)

        logger.info(f"{process_type.upper()} Eligibility Pipeline completed – {len(output_df)} rows {process_type}ed, {len(output_df_processed)} rows processed")

    except Exception as e:
        logger.exception(f"{process_type.upper()} Eligibility Pipeline - Failed to run Eligibility, Exception: {e}")
        raise



def run_pipeline(config: dict):
    collaborators_source_df = rp.get_collaborators_to_process(config=config)
    geocode_pipeline(
        config=config,
        df=collaborators_source_df,
        process_type='insert'
    )

    collaborators_source_geocode_df = rp.get_collaborators_geocode_to_process(config=config)
    home_stattion_eligibility_pipeline(
        config=config,
        df=collaborators_source_geocode_df,
        process_type='insert'
    )

    collaborators_to_update_df = rp.get_collaborators_to_update(config=config)
    if collaborators_to_update_df.shape[0] != 0:
        geocode_pipeline(
            config=config,
            df=collaborators_to_update_df,
            process_type='update'
        )

        collaborators_to_update_geocode_df = rp.get_collaborators_geocode_to_update(config=config)
        home_stattion_eligibility_pipeline(
            config=config,
            df=collaborators_to_update_geocode_df,
            process_type='update'
        )

