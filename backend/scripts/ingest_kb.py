"""
Knowledge base ingestion pipeline.

Usage (from backend/):
    python -m scripts.ingest_kb

What it does:
  1. Discovers all .md files in knowledge_base/sources/
  2. Splits each file into paragraph-level chunks on ## H2 headers
  3. For each new chunk (identified by SHA-256 content hash):
       a. Calls Groq (llama-3.1-8b-instant) to generate a 1-2 sentence
          contextualising blurb that situates the chunk within its document
       b. Prepends the blurb to produce contextualized_content
       c. Embeds BOTH contextualized_content and raw_content using
          sentence-transformers/all-MiniLM-L6-v2 (local, no paid API)
       d. Inserts the chunk into the kb_chunks table
  4. Skips chunks whose content_hash already exists (idempotent)
  5. Logs a token and cost estimate at the end

Run twice: the second run should log 0 new chunks and 206 skipped.
"""

import hashlib
import logging
import os
import time
from pathlib import Path

from groq import Groq

# ---------------------------------------------------------------------------
# Path setup — must run from backend/ so the app package is importable
# ---------------------------------------------------------------------------
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.database import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SOURCES_DIR = Path(__file__).resolve().parent.parent / "knowledge_base" / "sources"

# ---------------------------------------------------------------------------
# Per-file metadata defaults.
# fitness_goals and fitness_levels use the enum values from schemas/workout.py.
# Empty list means "universal" — matches any user profile.
# ---------------------------------------------------------------------------
FILE_METADATA: dict[str, dict] = {
    "01_progressive_overload.md": {
        "fitness_goals": [],
        "fitness_levels": [],
        "equipment_tags": [],
        "topic": "progressive_overload",
    },
    "02_acsm_resistance_training.md": {
        "fitness_goals": ["build_muscle", "general_fitness"],
        "fitness_levels": [],
        "equipment_tags": [],
        "topic": "resistance_training",
    },
    "03_cardio_endurance.md": {
        "fitness_goals": ["improve_endurance", "lose_weight", "general_fitness"],
        "fitness_levels": [],
        "equipment_tags": [],
        "topic": "cardio_endurance",
    },
    "04_weight_loss_principles.md": {
        "fitness_goals": ["lose_weight"],
        "fitness_levels": [],
        "equipment_tags": [],
        "topic": "weight_loss",
    },
    "05_flexibility_mobility.md": {
        "fitness_goals": ["increase_flexibility", "general_fitness"],
        "fitness_levels": [],
        "equipment_tags": [],
        "topic": "flexibility",
    },
    "06_equipment_exercises.md": {
        "fitness_goals": [],
        "fitness_levels": [],
        "equipment_tags": [],  # section-level metadata injected per chunk below
        "topic": "equipment_exercises",
    },
    "07_injury_prevention.md": {
        "fitness_goals": [],
        "fitness_levels": ["beginner", "intermediate"],
        "equipment_tags": [],
        "topic": "injury_prevention",
    },
    "08_recovery_sleep.md": {
        "fitness_goals": [],
        "fitness_levels": [],
        "equipment_tags": [],
        "topic": "recovery",
    },
    "09_nutrition_basics.md": {
        "fitness_goals": [],
        "fitness_levels": [],
        "equipment_tags": [],
        "topic": "nutrition",
    },
    "10_program_design.md": {
        "fitness_goals": ["build_muscle", "general_fitness"],
        "fitness_levels": [],
        "equipment_tags": [],
        "topic": "program_design",
    },
    "11_periodization.md": {
        "fitness_goals": ["build_muscle", "improve_endurance"],
        "fitness_levels": ["intermediate", "advanced"],
        "equipment_tags": [],
        "topic": "periodization",
    },
}

# Equipment section headers in 06_equipment_exercises.md → equipment_tags
EQUIPMENT_SECTION_TAGS = {
    "No Equipment": ["no_equipment"],
    "Dumbbells": ["dumbbells"],
    "Barbell": ["barbell"],
    "Resistance Bands": ["resistance_bands"],
    "Pull-Up Bar": ["pull_up_bar"],
    "Kettlebell": ["kettlebell"],
    "Full Gym": ["full_gym", "barbell", "dumbbells", "kettlebell"],
}


def split_into_chunks(text: str, source_file: str) -> list[dict]:
    """Split a markdown document into chunks on ## H2 headers.

    Each chunk dict has:
      raw_content: the section text (header + body)
      section:     the H2 header text
    """
    parts = text.split("\n## ")
    chunks = []

    for i, part in enumerate(parts):
        if i == 0:
            # First part may be the H1 title; skip if it's very short
            stripped = part.strip()
            if len(stripped) < 50:
                continue
            raw = stripped
            section = stripped.split("\n")[0].lstrip("# ").strip()
        else:
            raw = "## " + part.strip()
            section = part.split("\n")[0].strip()

        if len(raw) < 80:
            continue  # discard near-empty sections

        chunks.append({"raw_content": raw, "section": section})

    return chunks


def content_hash(raw_content: str) -> str:
    return hashlib.sha256(raw_content.encode("utf-8")).hexdigest()


def build_metadata(filename: str, section: str) -> dict:
    base = FILE_METADATA.get(filename, {}).copy()
    base["source_file"] = filename
    base["section"] = section

    # Equipment-specific tag injection for 06_equipment_exercises.md
    if filename == "06_equipment_exercises.md":
        for header_prefix, tags in EQUIPMENT_SECTION_TAGS.items():
            if section.startswith(header_prefix):
                base["equipment_tags"] = tags
                break

    return base


def generate_context_blurb(client: Groq, doc_text: str, chunk_text: str) -> str:
    """Call Groq to produce a 1-2 sentence blurb situating the chunk in its document."""
    prompt = (
        f"Document:\n{doc_text[:3000]}\n\n"
        f"Chunk:\n{chunk_text[:1500]}\n\n"
        "In 1-2 sentences, situate this chunk within the document. "
        "Describe what specific topic it covers and how it relates to "
        "the surrounding content. Output only the 2 sentences, nothing else."
    )
    response = client.chat.completions.create(
        model=settings.groq_context_model,
        messages=[
            {"role": "system", "content": "You are a fitness knowledge assistant."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=120,
        temperature=0.2,
    )
    return response.choices[0].message.content.strip()


def chunk_exists(db, hash_val: str) -> bool:
    result = db.execute(
        __import__("sqlalchemy").text(
            "SELECT COUNT(*) FROM kb_chunks WHERE content_hash = :h"
        ),
        {"h": hash_val},
    ).scalar()
    return result > 0


def insert_chunk(db, raw: str, ctx: str, meta: dict, emb: list, raw_emb: list, hash_val: str) -> None:
    import json
    from sqlalchemy import text

    # Use CAST(:param AS type) instead of :param::type because SQLAlchemy's
    # text() parser treats :: as the start of a named bindparam, causing a
    # syntax error. CAST(...) is equivalent and avoids the collision.
    db.execute(
        text("""
            INSERT INTO kb_chunks
                (content_hash, raw_content, contextualized_content,
                 metadata, embedding, raw_embedding)
            VALUES
                (:hash, :raw, :ctx,
                 CAST(:meta AS jsonb),
                 CAST(:emb AS vector),
                 CAST(:raw_emb AS vector))
        """),
        {
            "hash": hash_val,
            "raw": raw,
            "ctx": ctx,
            "meta": json.dumps(meta),
            "emb": str(emb),
            "raw_emb": str(raw_emb),
        },
    )
    db.commit()


def main() -> None:
    # ── Load models once ──────────────────────────────────────────────────────
    log.info("Loading embedding model: %s", settings.embed_model_name)
    from sentence_transformers import SentenceTransformer

    embed_model = SentenceTransformer(settings.embed_model_name)
    log.info("Embedding model loaded.")

    groq_client = Groq(api_key=settings.groq_api_key)
    db = SessionLocal()

    source_files = sorted(SOURCES_DIR.glob("*.md"))
    if not source_files:
        log.error("No .md files found in %s", SOURCES_DIR)
        return

    total_new = 0
    total_skipped = 0
    total_input_chars = 0
    start_time = time.time()

    for md_file in source_files:
        log.info("Processing: %s", md_file.name)
        doc_text = md_file.read_text(encoding="utf-8")
        chunks = split_into_chunks(doc_text, md_file.name)
        log.info("  → %d chunks found", len(chunks))

        for chunk in chunks:
            raw = chunk["raw_content"]
            hash_val = content_hash(raw)

            if chunk_exists(db, hash_val):
                log.info("    [SKIP] hash=%s section=%s", hash_val[:8], chunk["section"][:40])
                total_skipped += 1
                continue

            # Contextualise via Groq
            try:
                blurb = generate_context_blurb(groq_client, doc_text, raw)
            except Exception as exc:
                log.warning("    Groq error for chunk %s: %s — using raw as fallback", hash_val[:8], exc)
                blurb = ""

            time.sleep(0.3)  # stay within Groq free-tier rate limit (~30 req/min)

            ctx = (blurb + "\n\n" + raw).strip() if blurb else raw

            # Embed both versions
            emb = embed_model.encode(ctx, normalize_embeddings=True).tolist()
            raw_emb = embed_model.encode(raw, normalize_embeddings=True).tolist()

            meta = build_metadata(md_file.name, chunk["section"])

            insert_chunk(db, raw, ctx, meta, emb, raw_emb, hash_val)

            total_input_chars += len(doc_text[:3000]) + len(raw[:1500])
            total_new += 1
            log.info(
                "    [NEW] hash=%s section=%s", hash_val[:8], chunk["section"][:50]
            )

    db.close()

    # ── Cost estimate ─────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    estimated_tokens = total_input_chars // 4
    # llama-3.1-8b-instant pricing: $0.05 per 1M input tokens (as of 2026)
    estimated_cost = (estimated_tokens / 1_000_000) * 0.05

    log.info("─" * 60)
    log.info("Estimated input tokens:  %d", estimated_tokens)
    log.info("Estimated cost (llama-3.1-8b-instant @ $0.05/M): $%.4f", estimated_cost)
    log.info("Total chunks: %d new | %d skipped", total_new, total_skipped)
    log.info("Ingest complete in %.0fs", elapsed)


if __name__ == "__main__":
    main()
