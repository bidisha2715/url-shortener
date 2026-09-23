import os

from app.db import initialize_schema


if __name__ == "__main__":
    initialize_schema(os.getenv("DATABASE_URL", ""))
    print("PostgreSQL schema initialized successfully.")