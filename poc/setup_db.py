"""
Setup PostgreSQL + pgvector for 3GPP knowledge base.
Run: python setup_db.py
"""

import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "knowledge_base_3gpp"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}


def setup():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id SERIAL PRIMARY KEY,
            content TEXT NOT NULL,
            embedding vector(384),
            release VARCHAR(20),
            series VARCHAR(20),
            spec_number VARCHAR(50),
            subject_matter VARCHAR(200),
            section_hierarchy TEXT,
            hypothetical_question TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS chunks_embedding_idx
        ON chunks USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    """)

    cur.close()
    conn.close()
    print("✅ Database setup complete!")


if __name__ == "__main__":
    setup()
