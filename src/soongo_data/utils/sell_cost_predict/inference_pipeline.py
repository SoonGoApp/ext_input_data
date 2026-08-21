from soongo_data.utils.sell_cost_predict.data_loader import DataLoader
from soongo_data.utils.sell_cost_predict.model_predict import SellCostPredictor
from soongo_data.utils.logging_utils import gen_logger


logger = gen_logger('Sell_Cost_Predict - Inference')


class InferencePipeline:

    def __init__(self, config: dict):

        self.config = config
        self.data_loader = DataLoader(config=self.config)
        self.model = SellCostPredictor(config=self.config)
        self.predictions = None

    def run(self):
        """Main prediction script. Predit uniquement les vehicules en
        contrat ACQ (filtre applique cote SQL, sql_requests.py)."""
        try:

            # Load data (vehicules ACQ uniquement)
            features_df = self.data_loader.load_data()

            if features_df.empty:
                logger.info("Aucun vehicule ACQ a predire aujourd'hui - pipeline terminee.")
                return features_df

            # Predict Values
            self.predictions = self.model.predict(features_df.drop(columns=['vehicle_id']))
            features_df['predicted_rebate_price'] = self.predictions

            final_df = features_df[['vehicle_id', 'predicted_rebate_price']].copy()
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