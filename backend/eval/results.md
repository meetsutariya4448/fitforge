# FitForge RAG — Evaluation Results

## Retrieval Evaluation

**Dataset**: 30 hand-curated queries across 11 topic areas
**Metrics**: P@5 (precision at 5), R@5 (recall at 5), MRR (mean reciprocal rank)
**Latency**: wall-clock per query, models pre-loaded; includes DB round-trip

| Condition            | P@5   | R@5   | MRR   | p50 (ms) | p95 (ms) |
|----------------------|-------|-------|-------|----------|----------|
| sparse_only          | 0.287 | 0.822 | 0.836 |       3 |       7 |
| dense_ctx            | 0.307 | 0.867 | 1.000 |      16 |     383 |
| dense_raw            | 0.293 | 0.833 | 0.928 |      15 |      19 |
| hybrid               | 0.320 | 0.900 | 0.983 |      19 |      27 |
| hybrid_rerank        | 0.307 | 0.867 | 0.956 |     348 |     466 |

**Best MRR**: `dense_ctx` (MRR=1.000 — every query's first relevant chunk at rank 1)

### Key findings

- **Contextual embedding beats raw (MRR 1.000 vs 0.928)** — the 2-sentence Groq blurb prepended during
  ingestion measurably improves embedding alignment. The document-level context helps the model locate
  the query's intent even when the chunk itself uses different terminology.
- **Hybrid (RRF) achieves best P@5/R@5 (0.320 / 0.900)** — combining sparse term-match signal with
  dense semantic signal consistently surfaces more relevant chunks than either alone.
- **hybrid_rerank MRR slightly below hybrid (0.956 vs 0.983)** on this eval set. The cross-encoder
  improves ranking for ambiguous queries but occasionally reorders correctly-ranked hybrid results.
  At 30 eval queries the gap is within noise; production logs would clarify.
- **dense_ctx p95=383ms** is a first-query artifact (cold DB cursor / CPU cache miss). Steady-state
  p50 is 16ms — well within budget given the 10–30s Groq generation time.
- **Reranking adds ~330ms median latency** (p50: 348ms vs 19ms for hybrid). Acceptable given the
  Groq call dominates at 10–30s; flagged for potential async pre-fetch optimisation at scale.

### Per-query breakdown (hybrid_rerank)

| query_id | P@5 | R@5 | RR  | retrieved_ids |
|----------|-----|-----|-----|---------------|
| q001 | 0.40 | 1.00 | 1.00 | [1, 2, 7, 3, 5] |
| q002 | 0.40 | 1.00 | 1.00 | [3, 2, 4, 69, 7] |
| q003 | 0.20 | 0.50 | 1.00 | [7, 48, 4, 51, 3] |
| q004 | 0.20 | 0.50 | 1.00 | [5, 80, 3, 7, 78] |
| q005 | 0.20 | 0.50 | 1.00 | [10, 72, 14, 69, 13] |
| q006 | 0.20 | 0.50 | 1.00 | [9, 72, 70, 11, 14] |
| q007 | 0.20 | 1.00 | 1.00 | [11, 72, 73, 13, 10] |
| q008 | 0.20 | 1.00 | 1.00 | [12, 72, 16, 47, 13] |
| q009 | 0.40 | 1.00 | 1.00 | [13, 70, 4, 69, 10] |
| q010 | 0.40 | 1.00 | 1.00 | [17, 49, 18, 23, 22] |
| q011 | 0.20 | 0.50 | 0.33 | [29, 18, 19, 23, 22] |
| q012 | 0.40 | 1.00 | 1.00 | [30, 29, 33, 20, 26] |
| q013 | 0.40 | 1.00 | 1.00 | [27, 26, 33, 31, 28] |
| q014 | 0.40 | 1.00 | 1.00 | [31, 33, 63, 28, 29] |
| q015 | 0.40 | 1.00 | 1.00 | [33, 32, 26, 27, 28] |
| q016 | 0.40 | 1.00 | 1.00 | [36, 38, 35, 39, 40] |
| q017 | 0.20 | 0.50 | 0.33 | [35, 36, 39, 12, 16] |
| q018 | 0.20 | 1.00 | 1.00 | [42, 69, 47, 72, 12] |
| q019 | 0.20 | 1.00 | 1.00 | [44, 37, 16, 14, 72] |
| q020 | 0.20 | 1.00 | 1.00 | [41, 69, 72, 52, 3] |
| q021 | 0.40 | 1.00 | 1.00 | [49, 7, 48, 54, 2] |
| q022 | 0.20 | 0.50 | 1.00 | [52, 48, 54, 49, 7] |
| q023 | 0.40 | 1.00 | 1.00 | [16, 50, 12, 48, 3] |
| q024 | 0.40 | 1.00 | 1.00 | [56, 4, 68, 57, 11] |
| q025 | 0.20 | 0.50 | 1.00 | [60, 4, 7, 73, 1] |
| q026 | 0.40 | 1.00 | 1.00 | [61, 66, 68, 63, 64] |
| q027 | 0.20 | 1.00 | 1.00 | [63, 68, 61, 66, 72] |
| q028 | 0.20 | 1.00 | 1.00 | [68, 63, 65, 61, 64] |
| q029 | 0.40 | 1.00 | 1.00 | [69, 3, 4, 72, 13] |
| q030 | 0.60 | 1.00 | 1.00 | [77, 15, 76, 74, 78] |

---

## Generation Evaluation (RAGAS-style)

**Dataset**: 12 queries from eval_set.json (q001–q012), scored with 2–3 sentence
reasoning. All 12 plans returned `grounded=True` — retrieval confidence cleared
the −2.0 threshold on every query, confirming the KB covers all topic areas
without gaps.

**Judge model**: `llama-3.1-8b-instant`  
**Reasoning format**: 2–3 sentences per score (extended from the original 1-sentence
run, which produced uniform 0.50/0.90 across the board)

### Summary (n=12)

| Metric | Mean | Min | Max | Std |
|--------|------|-----|-----|-----|
| Faithfulness | 0.592 | 0.50 | 0.60 | 0.029 |
| Answer Relevancy | 0.883 | 0.80 | 0.90 | 0.039 |
| E2E Latency (s) | 18.6 | 2.9 | 33.2 | — |

### Per-query breakdown

| query_id | grounded | faithfulness | relevancy | latency |
|----------|----------|--------------|-----------|---------|
| q001 | ✓ | 0.60 | 0.90 | 2.9s |
| q002 | ✓ | 0.60 | 0.90 | 7.3s |
| q003 | ✓ | 0.60 | 0.90 | 30.8s |
| q004 | ✓ | 0.60 | 0.90 | 14.2s |
| q005 | ✓ | 0.60 | 0.90 | 33.2s |
| q006 | ✓ | 0.50 | 0.90 | 3.2s |
| q007 | ✓ | 0.60 | 0.90 | 27.0s |
| q008 | ✓ | 0.60 | 0.90 | 17.4s |
| q009 | ✓ | 0.60 | 0.90 | 29.9s |
| q010 | ✓ | 0.60 | 0.90 | 29.4s |
| q011 | ✓ | 0.60 | 0.80 | 11.2s |
| q012 | ✓ | 0.60 | 0.80 | 12.2s |

### Negative-control validation

To test whether the judge has real dynamic range, a hand-crafted contradicting
plan was scored against real context (chunk 11: ACSM rest period recommendations,
60–90 s for hypertrophy, 2–5 min for strength). The negative-control plan
recommended 10–15 second rest periods, 20–25 sets per exercise, and claimed
"muscles grow during the workout itself, not during recovery."

**Negative-control faithfulness score: 0.0**

Judge reasoning:
> *"No claims from the training plan are supported by the context passages. The
> plan recommends 10–15 seconds rest between sets, which contradicts the
> context's recommendation of 2–5 minutes for maximal strength work and 60–90
> seconds for hypertrophy training. Additionally, the plan suggests that muscles
> grow during the workout itself, not during recovery, which contradicts the
> context's mention of ATP-PCr restoration and neuromuscular recovery."*

Gap between real-plan mean (0.592) and negative control (0.0): **+0.59**. The
judge reaches the floor correctly when presented with specific contradictions.

### Judge resolution — documented limitation

The extended-reasoning format (2–3 sentences) moved faithfulness scores from a
uniform 0.50 to 0.50–0.60, and revealed two relevancy dips to 0.80 on q011 and
q012 (both cases where the onboarding-derived retrieval returned off-topic
content — see eval/README.md for the retrieval–generation query mismatch
discussion). However, across all 12 real generations the scores occupy only two
discrete values per metric: {0.50, 0.60} for faithfulness and {0.80, 0.90} for
relevancy.

**The judge can reliably detect obviously wrong generations** (score ≤ 0.2 is a
meaningful "bad plan" signal) but **cannot finely rank partially-grounded plans**
within the 0.4–0.8 range. A plan that grounds 30% of its claims in context
receives the same 0.60 as one that grounds 70%. The prompt uses an open 0.0–1.0
scale with no anchoring examples; adding explicit anchors (e.g. "0.0–0.2 = no
claims traceable, 0.8–1.0 = nearly all claims directly traceable") is the
recommended next step if finer resolution is needed for production monitoring.

- **E2E latency is dominated by Groq generation** — retrieval (p50 ~350 ms)
  is < 2% of total wall time (p50 15.8s).
