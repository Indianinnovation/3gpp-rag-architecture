"""
3GPP Document Ingestion Pipeline.
Extracts text, chunks with metadata, embeds, and upserts into pgvector.
Usage: python ingest.py --file spec.pdf --release rel-17
"""

import argparse
import re
import psycopg2
from pypdf import PdfReader
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


def extract_text(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def detect_metadata(text: str, release: str) -> dict:
    spec_match = re.search(r"(TS|TR)\s*(\d{2}\.\d{3})", text[:2000])
    series = ""
    if spec_match:
        series = f"{spec_match.group(2).split('.')[0]} series"

    subject = "General"
    if any(kw in text[:5000].lower() for kw in ["physical layer", "phy", "nr phy"]):
        subject = "PHY (Physical Layer)"
    elif any(kw in text[:5000].lower() for kw in ["mac", "medium access"]):
        subject = "MAC (Medium Access Control)"
    elif any(kw in text[:5000].lower() for kw in ["rrc", "radio resource"]):
        subject = "RRC (Radio Resource Control)"

    return {
        "release": release,
        "series": series,
        "spec_number": spec_match.group(0) if spec_match else "Unknown",
        "subject_matter": subject,
    }


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list:
    sections = re.split(r"\n(?=\d+\.?\d*\s+[A-Z])", text)
    chunks = []
    for section in sections:
        hierarchy_match = re.match(r"(\d+\.?\d*\.?\d*)\s+(.*?)(?:\n|$)", section)
        hierarchy = hierarchy_match.group(0).strip() if hierarchy_match else ""
        words = section.split()
        for i in range(0, len(words), chunk_size - overlap):
            chunk_content = " ".join(words[i:i + chunk_size])
            if len(chunk_content.strip()) > 50:
                chunks.append({"content": chunk_content, "section_hierarchy": hierarchy})
    return chunks


def embed_and_store(chunks: list, metadata: dict):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    contents = [c["content"] for c in chunks]
    embeddings = model.encode(contents)

    for chunk, embedding in zip(chunks, embeddings):
        cur.execute("""
            INSERT INTO chunks (content, embedding, release, series, spec_number,
                              subject_matter, section_hierarchy, hypothetical_question)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            chunk["content"], embedding.tolist(), metadata["release"],
            metadata["series"], metadata["spec_number"], metadata["subject_matter"],
            chunk["section_hierarchy"],
            f"What does the specification say about {chunk['content'][:80]}?",
        ))

    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ Ingested {len(chunks)} chunks")


def ingest(file_path: str, release: str):
    print(f"📄 Extracting: {file_path}")
    text = extract_text(file_path)
    metadata = detect_metadata(text, release)
    print(f"   Spec: {metadata['spec_number']}, Subject: {metadata['subject_matter']}")
    chunks = chunk_text(text)
    print(f"   Chunks: {len(chunks)}")
    embed_and_store(chunks, metadata)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--release", default="rel-17")
    args = parser.parse_args()
    ingest(args.file, args.release)
