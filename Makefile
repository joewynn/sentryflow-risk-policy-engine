setup:
	pip install -r requirements.txt
	kaggle datasets download -d ieee-fraud-detection -p data/
	unzip -o data/ieee-fraud-detection.zip -d data/

lint:
	ruff check src/ tests/

train:
	python -m metaflow run pipelines/backtest_flow.py --package-suffixes .py

deploy:
	python src/pipeline/sentryflow_pipeline.py --deploy-endpoint

test:
	pytest tests/

up:
	docker-compose up --build

down:
	docker-compose down

# Run the full suite: Setup data, build containers, and start services
ship-it: setup up