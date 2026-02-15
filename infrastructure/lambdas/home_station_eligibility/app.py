import os
import yaml
import traceback
from eligibility_pipeline import run_pipeline
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.secrets_utils import get_local_secret
from soongo_data.utils.aws import send_ses_email


def lambda_handler(context):

    try:
        logger = gen_logger("Lambda_handler")

        logger.info("Starting eligibility pipeline lambda")

        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "config.yaml",
        )
        with open(config_path, "r") as file:
            pipeline_config = yaml.safe_load(file)

        db_info = get_local_secret(
            logger=logger,
        )
        os.environ["DATABASE_URL"] = db_info["DATABASE_URL"]

        # Run pipeline
        run_pipeline(
            config=pipeline_config,
        )

        logger.info("Home Station Eligibility pipeline finished successfully")

        return {
            "status": "success"
        }
    
    except Exception as error:
        # print(traceback.format_exception(error))
        logger.error(
            f'Error on Home Station Eligibility pipeline with traceback {traceback.format_exception(error)}',
        )
        send_ses_email(
            sender_email="infra@soongo.co",
            recipient_email="data@soongo.co",
            subject="Alert: Error on Home Station Eligibility pipeline",
            body_text=(
                f"Home Station Eligibility pipeline failed"
                f"with traceback {traceback.format_exception(error)}"
            ),
            logger=logger,
        )


if __name__ == "__main__":
    lambda_handler(
        context=None,
    )
