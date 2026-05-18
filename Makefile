PYTHON := .venv/bin/python3
UV     := uv
PYTHONPATH := $(PWD)

setup:
	$(UV) pip install --python $(PYTHON) -r requirements.txt
	.venv/bin/kaggle competitions download -c ieee-fraud-detection -p data/
	unzip -o data/ieee-fraud-detection.zip -d data/

lint:
	$(PYTHON) -m ruff check src/ tests/

train:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) pipelines/training_pipeline.py

train-dev:
	SENTRYFLOW_MODEL_NAME=sentryflow_xgb_dev \
	SENTRYFLOW_RUN_CONFIG=run_config_dev.yaml \
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) pipelines/training_pipeline.py

train-local:
	SENTRYFLOW_MODEL_NAME=sentryflow_xgb_dev \
	SENTRYFLOW_RUN_CONFIG=run_config_local.yaml \
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) pipelines/training_pipeline.py

zenml-ui:
	zenml up

zenml-status:
	zenml model list && zenml stack describe

zenml-rollback:
	@echo "Usage: make zenml-rollback VERSION=<version_number>"
	zenml model version update sentryflow_xgb $(VERSION) --stage=production

test:
	$(PYTHON) -m pytest tests/

up:
	docker-compose up --build

down:
	docker-compose down

docs-serve:
	$(PYTHON) -m mkdocs serve

docs-build:
	$(PYTHON) -m mkdocs build

# Run the full suite: Setup data, build containers, and start services
ship-it: setup up