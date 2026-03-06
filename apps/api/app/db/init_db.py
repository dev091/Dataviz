from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import settings


def init_db() -> None:
    project_root = Path(__file__).resolve().parents[2]
    alembic_ini = project_root / "alembic.ini"
    script_location = project_root / "alembic"

    config = Config(str(alembic_ini))
    config.set_main_option("script_location", str(script_location))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")
