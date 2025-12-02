import pandas as pd
import numpy as np
import time
from itertools import product
from backtest_engine import BacktestEngine
from strategies import TrendStrategy

# 1. Configuration: The Search Space
# We will test faster windows (Scalping) vs Slower windows (Swing)
SHORT_WINDOWS = [1000, 3000, 5000, 10000] 
LONG_WINDOWS = [10000, 30000, 50000, 100000]
THRESHOLDS = [0.0005, 0.001, 0.002] # 0.05%, 0.1%, 0.2% bands

DATA_PATH = "data/parquet/BTCUSDT-2024-01.parquet"

def optimize():
    print(f"--- STARTING BRUTE FORCE OPTIMIZATION ---")
    print(f"Target: Finding the 'Golden Parameter Set'...")
    
    # Load data ONCE to save time (Use limited columns)
    # Note: For optimization, we can use a smaller slice (e.g., 5 million ticks) 
    # to get a rough idea, then verify on full data.
    print("Loading Data Slice (5M ticks)...")
    try:
        df_slice = pd.read_parquet(DATA_PATH, columns=['price']).iloc[:5000000]
    except FileNotFoundError:
        print("Error: Data file not found.")
        return

    # We need a custom mini-runner because the streaming engine is too slow for 100 loops
    # We will run an in-memory backtest on the slice
    
    results = []
    
    # Generate all combinations
    combinations = list(product(SHORT_WINDOWS, LONG_WINDOWS, THRESHOLDS))
    print(f"Testing {len(combinations)} combinations...")
    
    for i, (short_w, long_w, thresh) in enumerate(combinations):
        # Skip invalid combinations (Short must be < Long)
        if short_w >= long_w:
            continue
            
        start_time = time.time()
        
        # Initialize Strategy
        strat = TrendStrategy(short_window=short_w, long_window=long_w, threshold=thresh)
        
        # Fast Vectorized Backtest (Simplified for Speed)
        # We simulate the logic without the full engine overhead for speed
        prices = df_slice['price'].values
        
        # Calculate Rolling Means (Vectorized is instant vs Loop)
        # Note: Pandas rolling is faster than looping 5M times
        short_ma = df_slice['price'].rolling(window=short_w).mean()
        long_ma = df_slice['price'].rolling(window=long_w).mean()
        
        # Signals
        # 1 = Buy, -1 = Sell, 0 = Hold
        signals = np.where(short_ma > long_ma * (1 + thresh), 1, 0)
        signals = np.where(short_ma < long_ma, -1, signals)
        
        # Calculate PnL (Vectorized)
        # Shift signals by 1 to simulate "Trade at NEXT Open"
        pos = 0
        cash = 10000.0
        btc = 0.0
        fee_rate = 0.001
        trade_count = 0
        
        # Iterating only on signal changes is fast
        # Find where signal changes
        diff = np.diff(signals, prepend=0)
        change_indices = np.where(diff != 0)[0]
        
        for idx in change_indices:
            sig = signals[idx]
            price = prices[idx]
            
            if sig == 1 and pos == 0: # BUY
                cost = price * 0.001 # Buy 0.001
                if cash > cost:
                    cash -= cost * (1 + fee_rate)
                    btc += 0.001
                    pos = 1
                    trade_count += 1
                    
            elif sig == -1 and pos == 1: # SELL
                rev = price * 0.001
                cash += rev * (1 - fee_rate)
                btc -= 0.001
                pos = 0
                trade_count += 1
        
        # Final Value
        final_val = cash + (btc * prices[-1])
        pnl = final_val - 10000.0
        
        duration = time.time() - start_time
        
        print(f"[{i+1}/{len(combinations)}] S:{short_w} L:{long_w} T:{thresh} -> PnL: ${pnl:.2f} (Trades: {trade_count})")
        
        results.append({
            'short': short_w,
            'long': long_w,
            'thresh': thresh,
            'pnl': pnl,
            'trades': trade_count
        })

    # Sort and Show Winner
    results.sort(key=lambda x: x['pnl'], reverse=True)
    
    print("\n" + "="*40)
    print("       OPTIMIZATION RESULTS       ")
    print("="*40)
    print(f"{'Short':<8} {'Long':<8} {'Thresh':<8} {'PnL':<10} {'Trades'}")
    print("-" * 45)
    
    for r in results[:5]: # Top 5
        print(f"{r['short']:<8} {r['long']:<8} {r['thresh']:<8} ${r['pnl']:<9.2f} {r['trades']}")
        
    print("="*40)
    print(f"Best Parameters: {results[0]}")

if __name__ == "__main__":
    optimize()