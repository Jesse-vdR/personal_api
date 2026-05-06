.PHONY: install dev worker migrate revision deploy clean

VENV ?= .venv
PY := $(VENV)/bin/python

install:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt

dev:
	$(VENV)/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

worker:
	$(VENV)/bin/python -m app.agents.worker

migrate:
	$(VENV)/bin/alembic upgrade head

revision:
	@test -n "$(m)" || (echo "usage: make revision m='describe change'"; exit 1)
	$(VENV)/bin/alembic revision --autogenerate -m "$(m)"

deploy:
	bash scripts/manual-deploy.sh

clean:
	rm -rf $(VENV) app/__pycache__ app/version.txt
