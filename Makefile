PYTHON ?= .venv/Scripts/python.exe
NPM ?= npm

.PHONY: validate validate-architecture validate-frontend test architecture check-architecture status

validate:
	$(PYTHON) scripts/validate.py

validate-architecture:
	$(PYTHON) scripts/validate_structure.py
	$(PYTHON) scripts/validate_architecture.py
	$(PYTHON) scripts/generate_dependency_graph.py --check

validate-frontend:
	$(NPM) --prefix frontend run build
	$(NPM) --prefix frontend audit --audit-level=high

test:
	$(PYTHON) -m pytest tests/unit/detection tests/unit/evidence
	$(NPM) --prefix frontend test

architecture:
	$(PYTHON) scripts/generate_dependency_graph.py

check-architecture:
	$(PYTHON) scripts/generate_dependency_graph.py --check

status:
	$(PYTHON) scripts/show_status.py
