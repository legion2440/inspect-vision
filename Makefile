PYTHON ?= .venv/Scripts/python.exe
NPM ?= npm

.PHONY: validate validate-architecture validate-frontend test architecture check-architecture probe-service probe-api probe-bonuses validate-samples probe-samples status

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
	$(PYTHON) -m pytest tests/unit/backend_api tests/unit/contracts tests/unit/detection tests/unit/history tests/unit/evidence tests/integration/api
	$(NPM) --prefix frontend test

architecture:
	$(PYTHON) scripts/generate_dependency_graph.py

check-architecture:
	$(PYTHON) scripts/generate_dependency_graph.py --check

probe-service:
	$(PYTHON) scripts/probe_inspection_service.py

probe-api:
	$(PYTHON) scripts/probe_api_persistence.py

probe-bonuses:
	$(PYTHON) scripts/probe_api_bonuses.py

validate-samples:
	$(PYTHON) scripts/validate_demo_samples.py
	$(PYTHON) scripts/validate_showcase_samples.py

probe-samples:
	$(PYTHON) scripts/probe_demo_samples.py

status:
	$(PYTHON) scripts/show_status.py
