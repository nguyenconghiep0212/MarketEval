import os
from pathlib import Path
import psycopg
from psycopg import sql
from dotenv import load_dotenv

load_dotenv()

# Resolve schema.sql relative to this script's directory
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

RAW_DB_URI = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/marketeval")
DB_URI = RAW_DB_URI.replace("postgresql+asyncpg://", "postgresql://")

def init_db():
    print("🔌 Connecting to PostgreSQL...")
    with psycopg.connect(DB_URI) as conn:
        with conn.cursor() as cur:
            print(f"📜 Executing {SCHEMA_PATH.name}...")
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                schema_sql = f.read()
            
            cur.execute(sql.SQL(schema_sql)) # type: ignore
            conn.commit()
    print("✅ Database initialized successfully with pgvector support!")

if __name__ == "__main__":
    init_db()