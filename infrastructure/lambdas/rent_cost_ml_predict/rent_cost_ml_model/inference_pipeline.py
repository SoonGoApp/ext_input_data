from rent_cost_ml_model.data_loader import DataLoader
from rent_cost_ml_model.model_predict import RentalCostPredictor
from soongo_data.utils.logging_utils import gen_logger


logger = gen_logger('Inference_model')


class InferencePipeline:

    def __init__(self, config: dict):

        self.config = config
        self.data_loader = DataLoader(config=self.config)
        self.model = RentalCostPredictor(config=self.config)
        self.predictions = None
  

    def run(self):
        """Main prediction script."""
        logger.info("RENTAL COST PREDICTOR")
        
        try:
    
            # Load data
            features_df = self.data_loader.load_data()
            
            # Predict Values
            self.predictions = self.model.predict_cost(features_df.drop(columns=['vehicle_id']))
            features_df['predicted_total_rent_tax_exc'] = self.predictions

            final_df = features_df[['vehicle_id', 'predicted_total_rent_tax_exc']]
            final_df.loc[:, 'model'] = self.model.model_type

            self.data_loader.write_results_to_db(final_df)

            self.model.remove_model_folder_from_local()

            logger.info("PIPELINE COMPLETED SUCCESSFULLY")

            return final_df
            
        except Exception as e:
            logger.error(f"Prediction failed: {str(e)}", exc_info=True)
            raise



def run_pipeline(config: dict):
    """Main Pipeline"""
    pipeline = InferencePipeline(config=config)
    pipeline.run()