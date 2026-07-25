.PHONY: migrate ingest eval-retrieval eval-generation test

migrate:
	cd backend && alembic upgrade head

ingest:
	cd backend && python -m scripts.ingest_kb

eval-retrieval:
	cd backend && python -m eval.run_retrieval_eval

eval-generation:
	cd backend && python -m eval.run_generation_eval

test:
	cd backend && python -m pytest tests/ -v
