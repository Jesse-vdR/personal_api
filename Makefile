.PHONY: install dev deploy clean

VENV ?= .venv
PY := $(VENV)/bin/python

install:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt

dev:
	$(VENV)/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

deploy:
	bash scripts/manual-deploy.sh

clean:
	rm -rf $(VENV) app/__pycache__ app/version.txt
