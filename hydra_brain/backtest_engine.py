import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import pyarrow.parquet as pq

class BacktestEngine:
    def __init__(self, initial_cash=10000.0, fee_rate=0.001):
        self.initial_cash = initial_cash
        self.fee_rate = fee_rate
        self.cash = initial_cash
        self.btc = 0.0
        
        # Optimization: Don't store every single equity point (too much RAM)
        # Store equity every 1000 ticks
        self.equity_curve = [] 
        self.trades = []
        self.total_ticks = 0
        
    def run(self, parquet_path, strategy_func):
        print(f"[Backtest] Streaming data from: {parquet_path}")
        
        # 1. Open Parquet File Stream
        parquet_file = pq.ParquetFile(parquet_path)
        
        # 2. Iterate in batches of 100,000 rows
        batch_size = 100000
        
        for batch in parquet_file.iter_batches(batch_size=batch_size):
            # Convert only this chunk to Pandas (Low RAM usage)
            df_chunk = batch.to_pandas()
            
            # Process the chunk
            for row in df_chunk.itertuples():
                self.total_ticks += 1
                current_price = row.price
                
                # Calculate Equity (Optimization: Only record every 1000 ticks)
                if self.total_ticks % 1000 == 0:
                    equity = self.cash + (self.btc * current_price)
                    self.equity_curve.append(equity)
                
                # STRATEGY DECISION
                action = strategy_func(row, self.btc, self.cash)
                
                # EXECUTION LOGIC
                if action == 1: # BUY
                    cost = current_price * 0.001 
                    fee = cost * self.fee_rate
                    if self.cash >= (cost + fee):
                        self.cash -= (cost + fee)
                        self.btc += 0.001
                        # Only log trades, not every tick
                        # self.trades.append(...) 

                elif action == 2: # SELL
                    if self.btc >= 0.001:
                        revenue = current_price * 0.001
                        fee = revenue * self.fee_rate
                        self.cash += (revenue - fee)
                        self.btc -= 0.001

            # Progress Indicator
            print(f"\r[Backtest] Processed {self.total_ticks:,} ticks...", end="", flush=True)

        # Final Report
        final_price = df_chunk.iloc[-1]['price']
        self.generate_report(final_price)

    def generate_report(self, final_price):
        final_equity = self.cash + (self.btc * final_price)
        pnl = final_equity - self.initial_cash
        ret = (pnl / self.initial_cash) * 100
        
        print("\n\n" + "="*40)
        print("          BACKTEST RESULTS          ")
        print("="*40)
        print(f"Total Ticks:    {self.total_ticks:,}")
        print(f"Initial Cash:   ${self.initial_cash:.2f}")
        print(f"Final Equity:   ${final_equity:.2f}")
        print(f"Net Profit:     ${pnl:.2f} ({ret:.2f}%)")
        print("="*40)
        
        # Plotting (Downsampled)
        if len(self.equity_curve) > 0:
            plt.figure(figsize=(12, 6))
            plt.plot(self.equity_curve, label='Equity (x1000 ticks)')
            plt.title(f"Backtest: {ret:.2f}% Return")
            plt.xlabel("Time (x1000 ticks)")
            plt.ylabel("Portfolio Value ($)")
            plt.legend()
            # Save plot instead of showing (better for headless servers)
            plt.savefig("backtest_result.png")
            print("Chart saved to backtest_result.png")