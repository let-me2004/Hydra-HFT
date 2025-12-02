import time
import sys
import os
import mmap
import ctypes
import numpy as np
from sb3_contrib import RecurrentPPO

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, '..'))
from shared_defs.schema import SharedMemoryLayout, SHM_NAME, SHM_SIZE

MODEL_PATH = os.path.join(current_dir, "checkpoints/hydra_lstm_v1")

# --- CONFIGURATION ---
MAX_INVENTORY = 0.005  
TAKE_PROFIT_PCT = 0.002 # 0.2%
# ---------------------

def main():
    print("-" * 50)
    print(f"[Hydra Strategy] Starting Hybrid AI Controller")
    print("-" * 50)

    try:
        model = RecurrentPPO.load(MODEL_PATH)
    except FileNotFoundError:
        print(f"[ERROR] Model not found.")
        return

    # Connect to Memory
    shm_fd = -1
    while True:
        try:
            shm_fd = os.open(f"/dev/shm{SHM_NAME}", os.O_RDWR)
            break
        except FileNotFoundError:
            time.sleep(1)

    with mmap.mmap(shm_fd, ctypes.sizeof(SharedMemoryLayout), mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE) as mm:
        layout = SharedMemoryLayout.from_buffer(mm)
        
        last_time = 0
        lstm_states = None
        episode_starts = np.ones((1,), dtype=bool)
        
        # ---------------------------------------------------------
        # FIX: SYNC ENTRY PRICE ON STARTUP
        # ---------------------------------------------------------
        print("[Hydra] Syncing initial state...")
        while layout.market.bid_price == 0: # Wait for C++ to get data
            time.sleep(0.1)
            
        real_btc = layout.market.real_btc_balance
        mid_price = (layout.market.bid_price + layout.market.ask_price) / 2
        
        # If we wake up holding a bag, assume current price is our basis
        # This prevents the "500% Profit" hallucination
        if real_btc > 0:
            avg_entry_price = mid_price
            print(f"[STARTUP] Detected existing inventory: {real_btc:.4f} BTC")
            print(f"[STARTUP] Resetting cost basis to current price: ${avg_entry_price:.2f}")
        else:
            avg_entry_price = 0.0
        # ---------------------------------------------------------

        print("[Hydra Strategy] LIVE. Waiting for ticks...")

        while True:
            if layout.market.local_time_ms == last_time:
                continue 
            
            # 1. Read State
            real_usd = layout.market.real_usdt_balance
            real_btc = layout.market.real_btc_balance
            mid_price = (layout.market.bid_price + layout.market.ask_price) / 2
            
            # 2. Get AI Decision
            total_qty = layout.market.bid_qty + layout.market.ask_qty
            ofi = (layout.market.bid_qty - layout.market.ask_qty) / total_qty if total_qty > 0 else 0
            
            obs = np.array([0.0, ofi, real_btc, 0.0]).reshape(1, -1)
            action, lstm_states = model.predict(obs, state=lstm_states, episode_start=episode_starts, deterministic=True)
            episode_starts[0] = False
            
            ai_decision = int(action[0])
            
            # 3. Hybrid Logic
            final_action = 0 
            
            # RULE A: Inventory Cap
            if real_btc >= MAX_INVENTORY:
                if ai_decision == 1:
                    ai_decision = 0 
            
            # RULE B: Take Profit (Now fixed!)
            if real_btc > 0 and avg_entry_price > 0:
                pnl_pct = (mid_price - avg_entry_price) / avg_entry_price
                
                # Print Status occasionally
                if np.random.random() < 0.01:
                     print(f"[STATUS] PnL: {pnl_pct*100:.4f}% | Entry: {avg_entry_price:.2f} | Curr: {mid_price:.2f}")

                if pnl_pct > TAKE_PROFIT_PCT:
                     print(f"[PROFIT TAKER] Target Hit (+{pnl_pct*100:.2f}%). Selling.")
                     final_action = 2 

            if final_action == 0:
                if ai_decision == 1: final_action = 1
                elif ai_decision == 3: final_action = 2

            # 4. Execution
            if final_action == 1: # BUY
                if real_usd > 15.0:
                    print(f"[BUY] OFI: {ofi:.2f}")
                    layout.command.action = 1
                    layout.command.quantity = 0.001
                    layout.command.command_id += 1 
                    
                    # Update Weighted Average Entry Price
                    total_value = (real_btc * avg_entry_price) + (0.001 * mid_price)
                    avg_entry_price = total_value / (real_btc + 0.001)
                    
                    time.sleep(2)

            elif final_action == 2: # SELL
                if real_btc >= 0.001:
                    print(f"[SELL] Closing Position.")
                    layout.command.action = 2
                    layout.command.quantity = 0.001
                    layout.command.command_id += 1
                    time.sleep(2)

            last_time = layout.market.local_time_ms

if __name__ == "__main__":
    main()