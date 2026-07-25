# FitForge RAG Evaluation — Methodology Notes

## Eval Set Construction

`eval_set.json` contains 30 hand-curated query–relevance pairs spanning all 11
knowledge-base topic areas. Each pair was authored by:

1. Reading the `raw_content` of individual `kb_chunks` rows.
2. Writing a natural-language question a gym-goer would plausibly ask.
3. Manually assigning `expected_chunk_ids` (the SERIAL PKs of rows that
   directly answer the question).

`generate_candidates.py` can generate LLM-drafted candidate queries (via Groq
`llama-3.1-8b-instant`). Those candidates were used as inspiration but every
pair in `eval_set.json` was reviewed and edited by hand.

## Known Limitations

### Optimistic retrieval metrics

Because queries were authored by reading the chunks, the vocabulary and phrasing
in queries partially overlaps with chunk text. This inflates **all** conditions,
not just sparse:

- **sparse_only** benefits from lexical overlap: exact or stemmed terms from the
  chunk appear in the query, so `ts_rank_cd` scores are artificially high.

- **dense_ctx** is equally biased — and arguably more so. Writing a query by
  reading a chunk produces semantically-aligned language, not just lexical
  overlap. This gives the contextual embedding a "home-field" advantage: the
  embedding of the hand-crafted query will be unusually close to the embedding
  of the source chunk. The MRR=1.000 for dense_ctx should be treated with
  particular scepticism — a real user asking "what rep range for hypertrophy?"
  in casual phrasing would not land as precisely in embedding space.

- **hybrid / hybrid_rerank** inherit both biases.

All metrics are upward-biased relative to a real-user eval set. Relative
comparisons between conditions (contextual vs raw, hybrid vs sparse) are more
trustworthy than the absolute numbers. Real production query logs would give
a less biased eval set — flagged as future work.

### Chunk ID stability

`expected_chunk_ids` references `kb_chunks.id`, which is a SERIAL primary key.
If the database is wiped and re-seeded the IDs may shift, making the eval file
stale. The correct long-term fix is to reference `content_hash` (SHA-256 of
`raw_content`) and resolve to IDs at eval runtime. Documented here as a known
limitation; acceptable for a stable dev database.

### LLM judge calibration

The generation eval uses `llama-3.1-8b-instant` as a faithfulness and
relevancy judge (RAGAS-style). LLM judges are not calibrated in the
statistical sense — scores are relative, not absolute. The numbers should be
interpreted comparatively (grounded vs. low-confidence paths) rather than as
ground-truth quality metrics.

### Confidence threshold is empirical

The default threshold of `-2.0` was chosen from cross-encoder score
distributions observed during Phase 2 manual verification (fitness queries
scored +2 to +5; out-of-domain queries scored < -10). Platt scaling against a
labelled calibration set would be the principled approach — flagged as future
work.

## Retrieval eval vs generation eval — different retrieval queries

The retrieval ablation (`run_retrieval_eval.py`) calls `retrieve()` directly,
passing each query from `eval_set.json` verbatim as the retrieval string. This
is the fairest test of the retrieval pipeline in isolation.

`generate_workout_plan()`, by contrast, never sees the user's literal question.
It constructs its own retrieval query from the `OnboardingData` fields alone:

```python
def _build_retrieval_query(data: OnboardingData) -> str:
    return f"{goal} training program for {level} with {equipment}"
```

This means the generation eval's faithfulness score measures a different thing:
**is the generated plan grounded in what the onboarding-derived retrieval
returned**, not **is it grounded in content relevant to the user's literal
question**.

**Concrete example — q011:**
- Eval question: *"What heart rate zone should I be running in to burn fat?"*
- Expected chunks: [19] HR Zones, [21] RPE
- `_build_retrieval_query` output for this profile: `"lose weight training
  program for intermediate with no equipment"`
- Chunks actually retrieved by `generate_workout_plan`: [41 Bodyweight, 4 Rate
  of Progression, 3 Applying Overload, 33 Fat Loss Mistakes, 29 LISS vs HIIT]
- No HR zone content reached the prompt at all
- Plan scored `grounded=True` (confidence threshold was met) and
  faithfulness=0.6 (the plan was partially grounded in the bodyweight/fat-loss
  chunks that were retrieved)

The 0.6 faithfulness score is accurate relative to what was retrieved; it is
not a signal that the plan answered the user's actual question about heart rate
zones. The generation eval cannot detect this class of retrieval mismatch
because it has no access to the original eval question, only the onboarding
profile.

This is not a bug in `generate_workout_plan()` — the question of whether to
incorporate the user's literal free-text question into the retrieval query is a
scope decision recorded separately. It is documented here so the generation eval
numbers are not misread as topic-level coverage scores.

## Running Evals

```bash
# from project root
make eval-retrieval    # writes results to backend/eval/results.md
make eval-generation   # appends generation table to backend/eval/results.md
```

Both scripts must be run from the `backend/` directory (handled by the
Makefile). They require the `.venv` with sentence-transformers 2.7.0 + torch
2.2.2 and a running Postgres database (configured via `DATABASE_URL` in
`backend/.env`).
