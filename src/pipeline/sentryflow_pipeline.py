from metaflow import FlowSpec, step, batch, kubernetes, environment
class SentryFlowPipeline(FlowSpec):
    @step
    def start(self):
        self.data = pd.read_parquet("data/ieee_train.parquet")
        self.next(self.feature_eng)

    @step
    def feature_eng(self):
        # DIBB + vendor mock features
        self.next(self.train_model)

    @step
    def train_model(self):
        # XGBoost + Isolation Forest
        self.next(self.backtest)

    @batch(cpu=4, memory=16000)
    @kubernetes
    @step
    def backtest(self):
        # shadow mode on 10k holdout + Loss-Friction Curve
        self.next(self.deploy)

    @step
    def deploy(self):
        # SageMaker endpoint via Inference Components (2026)
        self.next(self.end)