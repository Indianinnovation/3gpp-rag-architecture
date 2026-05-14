"""
Simulated Lambda: 3GPP Preprocessor.
In production: Triggered by S3 event, calls Textract + Glue.
"""

import os
import re
import json
from pypdf import PdfReader


def lambda_handler(event=None, context=None):
    file_path = event.get("file_path") if event else None
    release = event.get("release", "rel-17") if event else "rel-17"
    output_dir = os.getenv("PROCESSED_BUCKET", "./data/processed")

    if not file_path or not os.path.exists(file_path):
        return {"statusCode": 400, "body": "File not found"}

    os.makedirs(output_dir, exist_ok=True)
    reader = PdfReader(file_path)
    full_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    sections = re.split(r"\n(?=\d+\.?\d*\.?\d*\s+[A-Z])", full_text)
    chunks = []
    for section in sections:
        hierarchy_match = re.match(r"(\d+\.?\d*\.?\d*)\s+(.*?)(?:\n|$)", section)
        hierarchy = hierarchy_match.group(0).strip() if hierarchy_match else ""
        words = section.split()
        for i in range(0, len(words), 400):
            content = " ".join(words[i:i + 500])
            if len(content.strip()) > 50:
                chunks.append({"content": content, "section_hierarchy": hierarchy, "release": release})

    output_file = os.path.join(output_dir, f"{os.path.basename(file_path)}.json")
    with open(output_file, "w") as f:
        json.dump({"source": file_path, "release": release, "chunks": chunks}, f, indent=2)

    print(f"✅ Processed: {len(chunks)} chunks → {output_file}")
    return {"statusCode": 200, "body": f"{len(chunks)} chunks"}


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        lambda_handler({"file_path": sys.argv[1]})
