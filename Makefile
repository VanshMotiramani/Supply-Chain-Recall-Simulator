PYTHON := .venv/Scripts/python.exe
PYTEST  := .venv/Scripts/pytest.exe

.PHONY: install test generate verify clean

install:
	$(PYTHON) -m pip install -e ".[dev]" --quiet

test:
	$(PYTEST) tests/ -v

generate:
	$(PYTHON) -m supply_chain.cli generate --seed $(or $(SEED),20261022) --mode $(or $(MODE),starter) --output-dir data/

verify:
	@echo "Running two independent generations and comparing checksums..."
	$(PYTHON) -m supply_chain.cli generate --seed 20261022 --mode starter --output-dir data/run1/
	$(PYTHON) -m supply_chain.cli generate --seed 20261022 --mode starter --output-dir data/run2/
	$(PYTHON) scripts/verify_reproducibility.py data/run1 data/run2

clean:
	Remove-Item -Recurse -Force data/ -ErrorAction SilentlyContinue
	Remove-Item -Recurse -Force __pycache__ -Recurse -ErrorAction SilentlyContinue
