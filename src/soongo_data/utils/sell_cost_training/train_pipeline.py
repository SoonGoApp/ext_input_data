import os
from pathlib import Path
from datetime import datetime
import pandas as pd
from sqlalchemy import text
from soongo_data.utils.sell_cost_training.model_training import SellCostModel
from soongo_data.utils.sell_cost_training.sql_requests import SELECT_ALL_FEATURES_TRAINING
from soongo_data.utils.aws import push_folder_to_s3
from soongo_data.utils.db import gen_engine
from soongo_data.utils.logging_utils import gen_logger


logger = gen_logger('Sell_Cost_Train - Train_Pipeline')


class TrainingPipeline:
    """Orchestrates the complete training pipeline."""
    
    def __init__(self, config: dict):

        self.config = config
        self.engine = gen_engine(
            database_url=os.environ["DATABASE_URL"]
        )
        self.model = SellCostModel(config=self.config)
        self.results = {}
    
    def setup(self):
        """Setup pipeline components."""

        # Create output directories
        for dir_path in ['models']:
            Path(self.config.get(f'{dir_path}_dir', dir_path)).mkdir(
                parents=True, exist_ok=True
            )

    def run(self):
        """Execute complete training pipeline."""
        try:
            # Setup
            self.setup()
            
            # Load data
            # with self.engine.connect() as conn:
            #     # df = pd.read_sql(text(SELECT_ALL_FEATURES_TRAINING), conn)
            #     df = pd.read_sql(SELECT_ALL_FEATURES_TRAINING, conn)

            with self.engine.connect() as conn:
                result = conn.execute(text(SELECT_ALL_FEATURES_TRAINING))
                df = pd.DataFrame(result.fetchall(), columns=result.keys())

            # Create features
            features = df.drop(columns=['target'])

            # Create target
            target = df[['vehicle_id', 'target']]
            
            # Train model
            self.results = self.model.train_model(features, target)
            
            # Save artifacts
            model_dir = self.model.save_model(self.results, self.config)

            # UPLOAD TO S3
            push_folder_to_s3(
                local_dir=model_dir,
                s3_prefix=str(model_dir),
                bucket_name=self.config["bucket_name"]
            )

            # self.model.remove_model_folder_from_local()
            
            return True
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            raise


def run_pipeline(config: dict):
    # Run pipeline
    pipeline = TrainingPipeline(config=config)
    pipeline.run()