
import yaml
import json
from pathlib import Path
from datetime import datetime
from soongo_data.utils.logging_utils import gen_logger
from electification_ml_pipeline.electrification_ml_model.data_pipeline import DataLoader
from electification_ml_pipeline.electrification_ml_model.feature_engineering import FeatureEngineer
from electification_ml_pipeline.electrification_ml_model.model_training import ElectrificationModel


logger = gen_logger('Train_model')


class TrainingPipeline:
    """Orchestrates the complete training pipeline."""
    
    def __init__(self, config: dict):

        self.config = config
        self.feature_engineer = FeatureEngineer(config=self.config)
        self.data_loader = DataLoader()
        self.model = ElectrificationModel(config=self.config)
        self.results = {}
    

    def setup(self):
        """Setup pipeline components."""
        logger.info("="*60)
        logger.info("ELECTRIFICATION ELIGIBILITY MODEL - TRAINING PIPELINE")
        logger.info("="*60)
                
        # Create output directories
        for dir_path in ['models']:
            Path(self.config.get(f'{dir_path}_dir', dir_path)).mkdir(
                parents=True, exist_ok=True
            )
    

    
    def save_artifacts(self):

        """Save model and results."""
        logger.info("\n" + "="*60)
        logger.info("STEP 7: SAVING ARTIFACTS")
        logger.info("="*60)
        
        # Save model
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        model_dir = Path(self.config['models_dir']) / 'model'
        self.model.save_model(str(model_dir))
        
        # Save results
        results_path = model_dir / 'training_results.json'
        with open(results_path, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        logger.info(f"Training results saved to {results_path}")
        
        # Save config used
        config_path = model_dir / 'config.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(self.config, f)
        
        logger.info(f"Configuration saved to {config_path}")
        
        return model_dir
    


    def run(self):
        """Execute complete training pipeline."""
        try:
            # Setup
            self.setup()
            
            # Load data
            tables = self.data_loader.load_all_tables()
            
            # Create features
            features = self.feature_engineer.create_features(tables)
            
            # Create target
            target = self.feature_engineer.create_target(tables)
            
            # Train model
            self.results = self.model.train_model(features, target)
            
            # Generate evaluation figures
            # model_dir = Path(self.config['models_dir']) / "figures"
            # self.generate_evaluation_figures(self.X_test, self.y_test, model_dir)
            
            # Save artifacts
            model_dir = self.save_artifacts()
            
            logger.info("\n" + "="*60)
            logger.info("PIPELINE COMPLETED SUCCESSFULLY")
            logger.info(f"Model saved to: {model_dir}")
            logger.info("="*60)
            
            return model_dir
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            raise
        





def run_pipeline(config: dict):
    # Run pipeline
    pipeline = TrainingPipeline(config=config)
    pipeline.run()

