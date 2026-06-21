.PHONY: setup data build serve test lint clean

VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PORT ?= 8765

setup: ## create venv and install deps
	python3 -m venv $(VENV)
	$(PIP) install -U pip
	$(PIP) install -r requirements.txt

data: ## regenerate derived geometry from sources (network; ~150MB INEGI download)
	$(PY) scripts/fetch_osm_lines.py     # HV transmission lines from Overpass (ODbL)
	$(PY) scripts/fetch_inegi.py         # INEGI municipio geometry (open)
	$(PY) scripts/dissolve_divisions.py  # CFE tariff-division polygons
	$(PY) scripts/dissolve_regions.py    # CENACE control-region polygons (needs coordinates*)
	@echo "* dissolve_regions needs data/sources/atlas-sen-geocoded.json (gitignored, maintainer-only)."
	@echo "  The committed data/derived/region_polys.json already contains the result."

demand: ## fetch the latest CENACE demand snapshot (used by the scheduled job)
	$(PY) scripts/fetch_demand.py

build: ## assemble the map into public/
	$(PY) scripts/build_map.py

serve: ## serve the built site locally
	$(PY) -m http.server $(PORT) --directory public

test: ## run data + UI tests
	$(PY) -m pytest tests/ -q
	cd tests/e2e && npx playwright test

lint:
	$(VENV)/bin/ruff check scripts tests
	npx prettier --check "src/**/*.{js,css,html}"

clean:
	rm -rf data/derived/* public/data/* $(VENV)

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n",$$1,$$2}'
