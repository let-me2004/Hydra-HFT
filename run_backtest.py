from hydra_brain.backtest_engine import BacktestEngine
from hydra_brain.strategies import TrendStrategy

DATA_PATH = "data/parquet/BTCUSDT-2024-01.parquet"

print("\n--- TESTING TREND STRATEGY (With Band Filter) ---")
engine = BacktestEngine()

# Tuned Parameters:
# Windows: 20k / 80k (Slower, smoother trend)
# Threshold: 0.001 (Must be 0.1% trend divergence to trigger)
strat_trend = TrendStrategy(short_window=20000, long_window=80000, threshold=0.001)

engine.run(DATA_PATH, strat_trend.decide)