
from pathlib import Path
from datetime import datetime
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.eligibility_electrif_training.data_pipeline import DataLoader
from soongo_data.utils.eligibility_electrif_training.model_training import ElectrificationModel


logger = gen_logger('Train_model')


class TrainingPipeline:
    """Orchestrates the complete training pipeline."""
    
    def __init__(self, config: dict):

        self.config = config
        self.data_loader = DataLoader()
        self.model = ElectrificationModel(config=self.config)
        self.results = {}
    
    def setup(self):
        """Setup pipeline components."""
                
        # Create output directories
        for dir_path in ['models']:
            Path(self.config.get(f'{dir_path}_dir', dir_path)).mkdir(
                parents=True, exist_ok=True
            )
    

    
    def save_artifacts(self):
        """Save model and results."""
        
        # Save model
        model_dir = Path(self.config['models_dir']) / f'model_{datetime.now().strftime('%Y-%m-%d')}'
        
        self.model.save_model(str(model_dir), self.results, self.config)
        
        return model_dir
    


    def run(self):
        """Execute complete training pipeline."""
        try:
            # Setup
            self.setup()
            
            # Load data
            df = self.data_loader.load_data()

            # Create features
            features = df.drop(columns=['target'])
            # Create target
            target = df[['vehicle_id', 'target']]
            
            # Train model
            self.results = self.model.train_model(features, target)
            
            # Save artifacts
            model_dir = self.save_artifacts()
            
            logger.info("PIPELINE COMPLETED SUCCESSFULLY")
            
            return model_dir
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            raise
        


def run_pipeline(config: dict):
    # Run pipeline
    pipeline = TrainingPipeline(config=config)
    pipeline.run()

