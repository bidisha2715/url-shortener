from pathlib import Path

import psycopg
from flask import current_app, g
from psycopg.rows import dict_row


def get_db():
    """Open one PostgreSQL connection for the current Flask request."""
    if "db" not in g:
        database_url = current_app.config["DATABASE_URL"]
        if not database_url:
            raise RuntimeError("DATABASE_URL is not configured")
        g.db = psycopg.connect(database_url, row_factory=dict_row)
    return g.db


def close_db(_error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_app(app):
    app.teardown_appcontext(close_db)


def initialize_schema(database_url):
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    schema_path = Path(__file__).with_name("schema.sql")
    with psycopg.connect(database_url) as connection:
        connection.execute(schema_path.read_text(encoding="utf-8"))