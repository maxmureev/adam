import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from alembic.config import Config
from alembic.command import upgrade
import logging

from config import config

logger = logging.getLogger(__name__)

# Настройка движка SQLAlchemy
engine = create_engine(config.db.url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db():
    """Инициализация базы данных с применением миграций при необходимости"""
    alembic_cfg_path = "alembic.ini"  # Путь к конфигурации Alembic

    # Проверка существования файла базы данных
    if not os.path.exists(config.db.path):
        # logger.info(
        #     f"Database file {config.db.path} does not exist. Creating database and applying migrations."
        # )

        # Миграции Alembic
        try:
            alembic_cfg = Config(alembic_cfg_path)
            alembic_cfg.set_main_option("sqlalchemy.url", config.db.url)
            upgrade(alembic_cfg, "head")
            logger.info("Alembic migrations applied successfully.")
        except Exception as e:
            logger.error(f"Failed to apply Alembic migrations: {e}")
            raise
    # else:
    #     logger.info(
    #         f"Database file {config.db.path} already exists. Skipping migration application."
    #     )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
