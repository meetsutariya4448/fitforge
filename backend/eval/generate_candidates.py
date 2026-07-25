"""
Generate candidate eval queries from KB chunks using Groq.

Samples chunks from the database, asks llama-3.1-8b-instant to draft 3
natural-language queries per chunk, and writes candidates_raw.json.

candidates_raw.json is NOT committed — it is an intermediate artefact used as
inspiration for manually curating eval_set.json.

Usage (from backend/):
    python -m eval.generate_candidates [--limit N] [--topic-sample]

Options:
    --limit N        Max chunks to process (default: 40, 0 = all)
    --topic-sample   Sample one chunk per source_file (11 chunks total)
"""

import argparse
import json
import os
import sys
import time

from groq import Groq

# ---------------------------------------------------------------------------
# Groq setup
# ---------------------------------------------------------------------------

_GROQ_MODEL = "llama-3.1-8b-instant"

_SYSTEM = (
    "You are helping build an evaluation dataset for a fitness knowledge "
    "retrieval system. Respond with raw JSON only — no markdown fences."
)

_USER_TEMPLATE = """\
Given this fitness knowledge base chunk, write exactly 3 natural-language
questions that a gym-goer or fitness enthusiast might realistically ask,
where THIS chunk would be a highly relevant answer.

Requirements:
- Phrase questions as a real user would (conversational, not academic).
- Each question should be specific enough that ONLY this chunk (or very
  few chunks) would answer it.
- Vary complexity and phrasing across the 3 questions.
- Do NOT simply rephrase the section heading.

Chunk:
{chunk_text}

Output JSON: {{"queries": ["<q1>", "<q2>", "<q3>"]}}
"""


def _generate_queries_for_chunk(client: Groq, chunk_text: str) -> list[str]:
    resp = client.chat.completions.create(
        model=_GROQ_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": _USER_TEMPLATE.format(chunk_text=chunk_text[:1200])},
        ],
        max_tokens=300,
        temperature=0.7,
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    data = json.loads(raw)
    return data.get("queries", [])


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _fetch_chunks(db, limit: int, topic_sample: bool) -> list[dict]:
    from sqlalchemy import text

    if topic_sample:
        sql = text("""
            SELECT DISTINCT ON (metadata->>'source_file')
                   id, raw_content, metadata->>'source_file' AS source_file,
                   metadata->>'section' AS section
            FROM kb_chunks
            ORDER BY metadata->>'source_file', id
        """)
    else:
        lim_clause = f"LIMIT {limit}" if limit > 0 else ""
        sql = text(f"""
            SELECT id, raw_content,
                   metadata->>'source_file' AS source_file,
                   metadata->>'section'     AS section
            FROM kb_chunks
            ORDER BY id
            {lim_clause}
        """)

    rows = db.execute(sql).fetchall()
    return [
        {
            "chunk_id": r.id,
            "source_file": r.source_file or "",
            "section": r.section or "",
            "raw_content": r.raw_content,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate eval candidate queries from KB chunks.")
    parser.add_argument("--limit",        type=int,  default=40,    help="Max chunks (0=all)")
    parser.add_argument("--topic-sample", action="store_true",       help="One chunk per source file")
    parser.add_argument("--out",          default="eval/candidates_raw.json",
                        help="Output file path (relative to backend/)")
    args = parser.parse_args()

    groq_key = os.environ.get("GROQ_API_KEY") or ""
    if not groq_key:
        # Try loading from .env
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        if os.path.exists(env_path):
            for line in open(env_path):
                line = line.strip()
                if line.startswith("GROQ_API_KEY="):
                    groq_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

    if not groq_key:
        print("ERROR: GROQ_API_KEY not set and not found in backend/.env", file=sys.stderr)
        sys.exit(1)

    client = Groq(api_key=groq_key)

    from app.database import SessionLocal
    db = SessionLocal()
    try:
        chunks = _fetch_chunks(db, args.limit, args.topic_sample)
    finally:
        db.close()

    print(f"Processing {len(chunks)} chunks …")

    candidates = []
    for i, chunk in enumerate(chunks, 1):
        print(f"  [{i}/{len(chunks)}] chunk_id={chunk['chunk_id']}  {chunk['section'][:60]}")
        try:
            queries = _generate_queries_for_chunk(client, chunk["raw_content"])
        except Exception as exc:
            print(f"    WARN: {exc}")
            queries = []

        for q in queries:
            candidates.append({
                "chunk_id":   chunk["chunk_id"],
                "source_file": chunk["source_file"],
                "section":    chunk["section"],
                "query":      q,
                "expected_chunk_ids": [chunk["chunk_id"]],
                "notes":      "LLM-generated — review before using in eval_set.json",
            })

        time.sleep(0.4)   # respect Groq free-tier rate limit

    out_path = os.path.join(os.path.dirname(__file__), "..", args.out.lstrip("eval/"))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(candidates, f, indent=2)

    print(f"\nWrote {len(candidates)} candidates to {out_path}")
    print("Review candidates_raw.json and curate into eval_set.json.")


if __name__ == "__main__":
    main()
