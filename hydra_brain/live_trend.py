import time
import sys
import os
import mmap
import ctypes
from collections import deque

# -----------------------------------------------------------------------------
# 1. SYSTEM SETUP
# -----------------------------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, '..'))
from shared_defs.schema import SharedMemoryLayout, SHM_NAME, SHM_SIZE

# -----------------------------------------------------------------------------
# 2. STRATEGY CONFIGURATION (The "Sniper" Settings)
# -----------------------------------------------------------------------------
SYMBOL = "BTC"
SHORT_WINDOW = 5000   # Fast Moving Average (~5 min)
LONG_WINDOW = 30000  # Slow Moving Average (~10 min)
THRESHOLD = 0.002    # 0.4% Band (Filters out noise/whipsaws)

# RISK MANAGEMENT
TRADE_SIZE = 0.001    # Trade 0.001 BTC (~$95)
MAX_INVENTORY = 0.005 # Max risk allowed (~$450)
MIN_CASH = 15.0       # Minimum USDT required to trade
TRAILING_STOP = 50.0  # Sell if price drops $50 from the highest point seen

def main():
    print("-" * 60)
    print(f"[Hydra Sniper] Starting LIVE TREND STRATEGY ({SYMBOL})")
    print(f"[Config] Short: {SHORT_WINDOW} | Long: {LONG_WINDOW} | Band: {THRESHOLD*100}%")
    print("-" * 60)

    # -------------------------------------------------------------------------
    # 3. CONNECT TO MEMORY BRIDGE
    # -------------------------------------------------------------------------
    shm_fd = -1
    while True:
        try:
            shm_fd = os.open(f"/dev/shm{SHM_NAME}", os.O_RDWR)
            break
        except FileNotFoundError:
            print("[WAITING] C++ Engine not ready... (Is ./hydra_engine running?)")
            time.sleep(1)

    # Map the C++ Memory Block
    with mmap.mmap(shm_fd, ctypes.sizeof(SharedMemoryLayout), mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE) as mm:
        layout = SharedMemoryLayout.from_buffer(mm)
        
        # ---------------------------------------------------------------------
        # 4. INITIALIZE STATE
        # ---------------------------------------------------------------------
        # High-Speed Deques for O(1) Moving Average Calculation
        short_deque = deque(maxlen=SHORT_WINDOW)
        long_deque = deque(maxlen=LONG_WINDOW)
        short_sum = 0.0
        long_sum = 0.0
        
        position = 0 # 0=Cash, 1=Long
        highest_price_seen = 0.0
        last_time = 0
        
        # ---------------------------------------------------------------------
        # 5. STARTUP SYNC (The "Amnesia" Fix)
        # ---------------------------------------------------------------------
        print("[Hydra] Syncing with C++ Engine...")
        while layout.market.bid_price == 0: # Wait for first tick
            time.sleep(0.1)

        real_btc = layout.market.real_btc_balance
        if real_btc >= TRADE_SIZE:
            print(f"[RESUME] Detected existing inventory: {real_btc:.5f} BTC")
            position = 1
            highest_price_seen = layout.market.bid_price # Reset trailing stop base
        
        print("[Hydra Sniper] LIVE. Accumulating history...")

        # ---------------------------------------------------------------------
        # 6. THE HIGH-FREQUENCY LOOP
        # ---------------------------------------------------------------------
        while True:
            # A. Stale Data Check (Safety Guard)
            # If C++ crashes, the timestamp stops updating. We must detect this.
            current_ts = time.time() * 1000
            data_age = current_ts - layout.market.local_time_ms
            
            if data_age > 5000: # 5 Seconds Lag
                print(f"\r[WARNING] Data Stale! Lag: {data_age/1000:.1f}s (Waiting for C++...)", end="", flush=True)
                time.sleep(1)
                continue

            # B. Spinlock (Wait for NEW tick)
            if layout.market.local_time_ms == last_time:
                continue 
            
            # C. Read Market Data
            bid = layout.market.bid_price
            ask = layout.market.ask_price
            price = (bid + ask) / 2
            
            real_usd = layout.market.real_usdt_balance
            real_btc = layout.market.real_btc_balance 

            # D. Update Moving Averages (O(1) Speed)
            # Short Window
            if len(short_deque) == SHORT_WINDOW:
                short_sum -= short_deque[0]
            short_deque.append(price)
            short_sum += price
            
            # Long Window
            if len(long_deque) == LONG_WINDOW:
                long_sum -= long_deque[0]
            long_deque.append(price)
            long_sum += price
            
            # Warmup Progress Bar
            if len(long_deque) < LONG_WINDOW:
                if len(long_deque) % 100 == 0:
                    pct = len(long_deque) / LONG_WINDOW * 100
                    print(f"\r[Warmup] {len(long_deque)}/{LONG_WINDOW} ticks ({pct:.0f}%) | Price: {price:.2f}", end="", flush=True)
                last_time = layout.market.local_time_ms
                continue

            # E. Calculate Signals
            short_avg = short_sum / SHORT_WINDOW
            long_avg = long_sum / LONG_WINDOW
            
            # -----------------------------------------------------------------
            # 7. RISK MANAGER: TRAILING STOP
            # -----------------------------------------------------------------
            if position == 1:
                # Track Peak Price
                if price > highest_price_seen:
                    highest_price_seen = price
                
                # Check Drawdown
                drawdown = highest_price_seen - price
                if drawdown > TRAILING_STOP:
                    print(f"\n[RISK] TRAILING STOP HIT! Dropped ${drawdown:.2f} from Peak (${highest_price_seen:.2f})")
                    
                    # Panic Sell (Limit Order inside spread to exit fast)
                    target_price = ask - 10.0 
                    
                    layout.command.action = 2 # SELL
                    layout.command.quantity = TRADE_SIZE
                    layout.command.price = target_price 
                    layout.command.command_id += 1
                    
                    position = 0
                    highest_price_seen = 0.0
                    time.sleep(5) # Wait for dust to settle
                    continue

            # -----------------------------------------------------------------
            # 8. STRATEGY: TREND SNIPER
            # -----------------------------------------------------------------
            
            # BUY SIGNAL (Golden Cross + Band)
            if short_avg > long_avg * (1 + THRESHOLD):
                # Filter: Cash Check & Inventory Check
                if position == 0 and real_usd > MIN_CASH and real_btc < MAX_INVENTORY:
                    
                    # EXECUTION: Limit Order @ Best Bid + 0.01 (Penny Jumping)
                    target_price = bid + 0.01
                    
                    print(f"\n[SNIPER] BUY SIGNAL! (S:{short_avg:.2f} > L:{long_avg:.2f})")
                    print(f"         -> POSTING LIMIT BUY @ {target_price:.2f}")
                    
                    layout.command.action = 1 # BUY
                    layout.command.quantity = TRADE_SIZE
                    layout.command.price = target_price 
                    layout.command.command_id += 1
                    
                    position = 1
                    highest_price_seen = price # Initialize stop loss baseline
                    time.sleep(2)
            
            # SELL SIGNAL (Trend Collapse)
            elif short_avg < long_avg:
                # Filter: Do we have inventory?
                if position == 1 and real_btc >= TRADE_SIZE:
                    
                    # EXECUTION: Limit Order @ Best Ask - 0.01
                    target_price = ask - 0.01 
                    
                    print(f"\n[SNIPER] SELL SIGNAL! (Trend Down)")
                    print(f"         -> POSTING LIMIT SELL @ {target_price:.2f}")
                    
                    layout.command.action = 2 # SELL
                    layout.command.quantity = TRADE_SIZE 
                    layout.command.price = target_price 
                    layout.command.command_id += 1
                    
                    position = 0
                    highest_price_seen = 0.0
                    time.sleep(2)

            last_time = layout.market.local_time_ms

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[Hydra] Shutting down.")