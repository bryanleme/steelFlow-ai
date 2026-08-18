PYTHON ?= python

.PHONY: setup validate-config doctor generate-dev validate-data build-db diagnose build-features train evaluate optimize-demo test lint app

setup:
	$(PYTHON) -m pip install -e ".[data,dev]"

validate-config:
	$(PYTHON) -m steelflow validate-config --all

doctor:
	$(PYTHON) -m steelflow doctor

generate-dev:
	$(PYTHON) -m steelflow generate --profile dev

validate-data:
	$(PYTHON) -m steelflow validate-data --profile dev

build-db:
	$(PYTHON) -m steelflow build-db --profile dev

diagnose:
	$(PYTHON) -m steelflow diagnose --profile dev

build-features:
	$(PYTHON) -m steelflow build-features --profile dev

train:
	$(PYTHON) -m steelflow train --profile dev

evaluate:
	$(PYTHON) -m steelflow evaluate --profile dev

optimize-demo:
	$(PYTHON) -m steelflow optimize-demo --profile dev

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .

app:
	$(PYTHON) -m steelflow app --profile dev
