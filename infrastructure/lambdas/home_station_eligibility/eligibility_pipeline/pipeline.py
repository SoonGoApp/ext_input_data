import pandas as pd
from eligibility_pipeline.bdnb_client import get_cle_interop_adr, get_building_usage
import eligibility_pipeline.repository as rp
from soongo_data.utils.logging_utils import gen_logger


logger = gen_logger("Pipeline")


def home_station_eligibility_pipeline(config: dict, df: pd.DataFrame, process_type: str) -> pd.DataFrame:
    try:
        rows_nb = config['nb_rows_to_process']

        results = []
        
        if isinstance(rows_nb, int):
            rows = df.head(rows_nb).iterrows()
        else:
            rows = df.iterrows()

        for _, row in rows:
            cle_interop_adr = get_cle_interop_adr(
                row.full_address 
            )
            building_usage = get_building_usage(
                cle_interop_adr
            )

            results.append({
                "collaborator_id": row.id,
                "personal_address": row.full_address,
                "cle_interop_adr": cle_interop_adr,
                "building_usage": building_usage,
                "source": "BDNB"
            })

        output_df = pd.DataFrame(results)
        output_df_processed = output_df.dropna(subset=['collaborator_id', 'building_usage'])

        #  Insert Output
        rp.insert_collaborators_eligibility_data(config, output_df, process_type)

        logger.info(f"{process_type.upper()} Eligibility Pipeline completed – {len(output_df)} rows {process_type}ed, {len(output_df_processed)} rows processed")

        return output_df 
    
    except Exception as e:
        logger.exception(f"{process_type.upper()} Eligibility Pipeline - Failed to run Eligibility, Exception: {e}")
        raise


# MAIN PIPELINE
def run_pipeline(config: dict):
    # Pipeline for New Collaborators # INSERT
    collaborators_source_df = rp.get_collaborators_to_process(config=config)
    home_station_eligibility_pipeline(
        config=config,
        df=collaborators_source_df,
        process_type='insert'
    )

    # Pipeline for Collaborators with new Address # UPDATE
    collaborators_to_update_df = rp.get_collaborators_to_update(config=config)
    if collaborators_to_update_df.shape[0] != 0:
        home_station_eligibility_pipeline(
            config=config,
            df=collaborators_to_update_df,
            process_type='update'
        )

