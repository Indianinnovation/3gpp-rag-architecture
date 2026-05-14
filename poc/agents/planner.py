"""
Planner Agent — Decomposes query and retrieves relevant 3GPP chunks via vector search.
"""

import psycopg2
from sentence_transformers import SentenceTransformer
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

model = SentenceTransformer("all-MiniLM-L6-v2")


def retrieve_chunks(query: str, release: str = None, top_k: int = 5) -> list:
    embedding = model.encode(query).tolist()
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    if release:
        cur.execute("""
            SELECT content, release, spec_number, section_hierarchy,
                   1 - (embedding <=> %s::vector) as similarity
            FROM chunks WHERE release = %s
            ORDER BY embedding <=> %s::vector LIMIT %s
        """, (embedding, release, embedding, top_k))
    else:
        cur.execute("""
            SELECT content, release, spec_number, section_hierarchy,
                   1 - (embedding <=> %s::vector) as similarity
            FROM chunks ORDER BY embedding <=> %s::vector LIMIT %s
        """, (embedding, embedding, top_k))

    results = [{"content": r[0], "release": r[1], "spec_number": r[2],
                "section_hierarchy": r[3], "similarity": r[4]} for r in cur.fetchall()]
    cur.close()
    conn.close()
    return results


def plan_query(state: dict) -> dict:
    question = state["question"]
    release_filter = state.get("release_filter", "")

    plan = "analyze_spec"
    if any(kw in question.lower() for kw in ["compare", "difference", "vs", "between"]):
        plan = "compare_releases"
    elif any(kw in question.lower() for kw in ["phy", "physical", "mac", "layer"]):
        plan = "phy_mac_analysis"

    chunks = retrieve_chunks(question, release_filter or None)
    state["plan"] = plan
    state["retrieved_chunks"] = chunks
    state["retry_count"] = state.get("retry_count", 0)
    return state
