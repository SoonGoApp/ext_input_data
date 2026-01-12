import os
from sqlalchemy import create_engine
from eligibility_pipeline.logger import get_logger

logger = get_logger("POSTRES_DB")

def get_pg_engine():
    try:
        return create_engine(
            os.environ["DATABASE_URL"],
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10
        )
    except Exception:
        logger.exception("Failed to create PostgreSQL engine")
        raise
