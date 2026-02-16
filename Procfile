web: python scripts/run_schema.py 2>/dev/null || true; python scripts/run_migrate_phase1.py 2>/dev/null || true; exec python -m uvicorn api:app --host 0.0.0.0 --port $PORT
