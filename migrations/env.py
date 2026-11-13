"""Alembic ortamı — yalnızca user.db için kullanılır."""

from alembic import context
from sqlalchemy import create_engine

from app.database.user_db import UserBase
from app.models import user  # noqa: F401  (modellerin metadata'ya kaydı)

config = context.config
target_metadata = UserBase.metadata


def run_migrations() -> None:
    engine = create_engine(config.get_main_option("sqlalchemy.url"))
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite'ta ALTER TABLE kısıtları için
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations()
