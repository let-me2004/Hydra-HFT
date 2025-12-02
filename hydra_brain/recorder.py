import sys
import time
import mmap
import os
import csv
import datetime

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from shared_defs.schema import MarketState, SHM_NAME, SHM_SIZE

# Configuration
DATA_DIR = os.path.join(os.path.dirname(__file__), '../data/raw_ticks')
os.makedirs(DATA_DIR, exist_ok=True)
FILENAME = os.path.join(DATA_DIR, f"ticks_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
SHM_SIZE = 4096 

def main():
    print(f"[Recorder] Waiting for Shared Memory...")
    
    # 1. Connect to SHM
    shm_fd = -1
    while True:
        try:
            shm_fd = os.open(f"/dev/shm{SHM_NAME}", os.O_RDWR)
            break
        except FileNotFoundError:
            time.sleep(0.5)

    print(f"[Recorder] Connected! Saving to: {FILENAME}")
    
    # 2. Open CSV file
    with open(FILENAME, 'w', newline='') as csvfile:
        fieldnames = ['local_time', 'bid_price', 'bid_qty', 'ask_price', 'ask_qty', 'spread', 'ofi']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        with mmap.mmap(shm_fd, SHM_SIZE, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE) as mm:
            market_data = MarketState.from_buffer(mm)
            
            last_time = 0
            tick_count = 0
            
            # 3. Recording Loop
            try:
                while True:
                    # Check if C++ has updated the timestamp
                    current_time = market_data.local_time_ms
                    
                    if current_time != last_time and current_time != 0:
                        # Calculate Derived Features immediately
                        spread = market_data.ask_price - market_data.bid_price
                        
                        # Simple Order Flow Imbalance (OFI) proxy
                        # (Bid Qty - Ask Qty) / Total Qty
                        total_qty = market_data.bid_qty + market_data.ask_qty
                        ofi = (market_data.bid_qty - market_data.ask_qty) / total_qty if total_qty > 0 else 0

                        writer.writerow({
                            'local_time': current_time,
                            'bid_price': market_data.bid_price,
                            'bid_qty': market_data.bid_qty,
                            'ask_price': market_data.ask_price,
                            'ask_qty': market_data.ask_qty,
                            'spread': f"{spread:.2f}",
                            'ofi': f"{ofi:.4f}"
                        })
                        
                        last_time = current_time
                        tick_count += 1
                        
                        if tick_count % 1000 == 0:
                            print(f"\r[Recorder] Captured {tick_count} ticks...", end="", flush=True)
                    
                    # Ultra-tight loop to catch every update
                    # We don't sleep here to match C++ speed as closely as possible
                    pass 

            except KeyboardInterrupt:
                print(f"\n[Recorder] Stopped. Saved {tick_count} ticks to {FILENAME}")

if __name__ == "__main__":
    main()