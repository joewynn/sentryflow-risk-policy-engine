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
	MLFLOW_EXPERIMENT_NAME=sentryflow-fraud-detection \
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) pipelines/backtest_flow.py run

mlflow-ui:
	$(PYTHON) -m mlflow ui --host 0.0.0.0 --port 5000

deploy:
	$(PYTHON) src/pipeline/sentryflow_pipeline.py --deploy-endpoint

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