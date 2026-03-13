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