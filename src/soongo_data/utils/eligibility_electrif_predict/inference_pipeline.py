from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.eligibility_electrif_predict.data_pipeline import DataLoader
from soongo_data.utils.eligibility_electrif_predict.model_predict import ElectrificationModel


logger = gen_logger('Inference_model')


class InferencePipeline:
    """Orchestrates the complete predict pipeline."""
    
    def __init__(self, config: dict):

        self.config = config
        self.data_loader = DataLoader(config=self.config)
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

            final_df = features_df[['vehicle_id', 'score']].copy()
            final_df.loc[:, 'model'] = self.model.model_type

            self.data_loader.write_results_to_db(final_df)

            self.model.remove_model_folder_from_local()

            return features_df
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            raise
        


def run_pipeline(config: dict):
    # Run pipeline
    pipeline = InferencePipeline(config=config)
    pipeline.run()