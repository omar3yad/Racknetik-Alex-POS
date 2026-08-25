.PHONY: install css migrate seed run test lint typecheck

install:
	pip install -r requirements.txt

css:
	npx tailwindcss -o static/css/tailwind.min.css --minify

migrate:
	alembic upgrade head

seed:
	python seed.py

run:
	uvicorn main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest -v --tb=short

lint:
	ruff check . && black --check .

typecheck:
	mypy .
