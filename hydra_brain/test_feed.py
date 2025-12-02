import sys
import time
import mmap
import ctypes
import os

# Add parent directory to path to find shared_defs
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from shared_defs.schema import MarketState, SHM_NAME, SHM_SIZE

def main():
    print(f"[Python] Waiting for Shared Memory: {SHM_NAME}...")
    
    # 1. Wait for C++ to create the memory
    shm_fd = -1
    while True:
        try:
            shm_fd = os.open(f"/dev/shm{SHM_NAME}", os.O_RDWR)
            break
        except FileNotFoundError:
            time.sleep(0.5)

    # 2. Map the memory
    with mmap.mmap(shm_fd, SHM_SIZE, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE) as mm:
        market_data = MarketState.from_buffer(mm)
        
        print("[Python] Connected! Watching Market Data...")
        print("-" * 50)
        
        # 3. Read Loop
        last_time = 0
        while True:
            # Only print if timestamp changed (new data)
            if market_data.local_time_ms != last_time:
                print(f"Time: {market_data.local_time_ms} | "
                      f"Bid: {market_data.bid_price:.2f} | "
                      f"Ask: {market_data.ask_price:.2f} | "
                      f"Spread: {market_data.ask_price - market_data.bid_price:.2f}")
                last_time = market_data.local_time_ms
            
            time.sleep(0.01) # Check 100 times a second

if __name__ == "__main__":
    main()