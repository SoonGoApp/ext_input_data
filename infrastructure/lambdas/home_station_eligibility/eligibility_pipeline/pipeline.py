import pandas as pd
from eligibility_pipeline.bdnb_client import get_geocode_data, get_building_infos
import eligibility_pipeline.repository as rp
from eligibility_pipeline.logger import get_logger


logger = get_logger("Pipeline")
rows_nb = 20



def geocode_pipeline(pipeline_config: dict):
    try:
        df = rp.get_collaborators(pipeline_config=pipeline_config)
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
                "cle_interop_adr": cle_interop_adr,
                "longitude": longitude,
                "latitude": latitude,
                "source": "BDNB"
            })

        output_df = pd.DataFrame(results)

        #  Insert Output
        rp.insert_collaborators_geocode_data(pipeline_config, output_df)

        logger.info(f"Geocode Pipeline completed – {len(output_df)} rows written")

    except Exception as e:
        logger.exception(f"Geocode Pipeline - Failed to run Geocode, Exception: {e}")
        raise



def home_electric_born_eligibility_pipeline(pipeline_config: dict):
    try:
        df = rp.get_collaborators_geocode_data(pipeline_config=pipeline_config)
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
                "eligible": eligible,
                "usage_batiment": usage_batiment,
                "type_batiment": type_batiment,
                "nb_logement": nb_logement,
                "nb_niveau": nb_niveau,
                "s_geom": s_geom,
                "surface": surface,
                "garden": garden,
                "source": "BDNB"
            })

        output_df = pd.DataFrame(results)
        output_df_processed = output_df.dropna(subset=['collaborator_id', 'eligible'])

        #  Insert Output
        rp.insert_collaborators_eligibility_data(pipeline_config, output_df)

        logger.info(f"Eligibility Pipeline completed – {len(output_df)} rows written, {len(output_df_processed)} rows processed")

    except Exception as e:
        logger.exception(f"Eligibility Pipeline - Failed to run Eligibility, Exception: {e}")
        raise



def run_pipeline(config: dict):
    
    geocode_pipeline(
        pipeline_config=config
    )
    home_electric_born_eligibility_pipeline(
        pipeline_config=config
    )
