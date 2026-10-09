# HospitalShield AI - one entry point for every common task (Windows/Linux)
PY := .venv/Scripts/python
ifeq ($(OS),Linux)
	PY := .venv/bin/python
endif

.PHONY: setup test lint typecheck verify demo snapshots clean

setup:
	python -m venv .venv
	$(PY) -m pip install -r requirements.lock.txt
	cd frontend && npm install

test:
	cd backend && ../$(PY) -m pytest tests/ -q

lint:
	cd backend && ../$(PY) -m ruff check app tests scripts

typecheck:
	cd backend && ../$(PY) -m mypy
	cd frontend && npx tsc -b

verify: lint typecheck test
	cd frontend && npm run build

snapshots:
	cd backend && ../$(PY) scripts/generate_demo_snapshots.py

demo: verify snapshots
	cd backend && ../$(PY) -m uvicorn app.main:app --port 8000 &
	cd frontend && npm run dev

clean:
	rm -rf backend/.pytest_cache backend/**/__pycache__ frontend/dist
