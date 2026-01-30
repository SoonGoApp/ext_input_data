from soongo_data.utils.logging_utils import gen_logger
from electrification_ml_model.data_pipeline import DataLoader
from electrification_ml_model.model_predict import ElectrificationModel


logger = gen_logger('Inference_model')


class InferencePipeline:
    """Orchestrates the complete predict pipeline."""
    
    def __init__(self, config: dict):

        self.config = config
        self.data_loader = DataLoader()
        self.model = ElectrificationModel(config=self.config)
        self.predictions = None
    
    
    def run(self):
        """Execute complete training pipeline."""
        try:

            # Load data
            features_df = self.data_loader.load_data()
            
            # Predict Values
            self.predictions = self.model.predict_score(features_df.drop(columns=['vehicle_id']))
            features_df['score'] = self.predictions

            final_df = features_df[['vehicle_id', 'score']]
            final_df.loc[:, 'model'] = self.config['model_type']

            self.data_loader.write_results_to_db(final_df)

            self.model.remove_model_folder_from_local()

            logger.info("\n" + "="*60)
            logger.info("PIPELINE COMPLETED SUCCESSFULLY")
            logger.info("="*60)

            return features_df
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            raise
        


def run_pipeline(config: dict):
    # Run pipeline
    pipeline = InferencePipeline(config=config)
    pipeline.run()