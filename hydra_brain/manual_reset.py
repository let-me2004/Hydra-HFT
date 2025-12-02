import time
import sys
import os
import mmap
import ctypes

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, '..'))
from shared_defs.schema import SharedMemoryLayout, SHM_NAME

def main():
    print("-" * 50)
    print("[ADMIN] Hydra Liquidity Reset Tool")
    print("-" * 50)

    try:
        shm_fd = os.open(f"/dev/shm{SHM_NAME}", os.O_RDWR)
    except FileNotFoundError:
        print("[ERROR] C++ Engine is not running.")
        return

    # Create mmap
    mm = mmap.mmap(shm_fd, ctypes.sizeof(SharedMemoryLayout), mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE)
    
    # Create the struct wrapper
    layout = SharedMemoryLayout.from_buffer(mm)

    try:
        # 1. READ
        btc = layout.market.real_btc_balance
        usd = layout.market.real_usdt_balance
        
        print(f"[STATUS] Inventory: {btc:.5f} BTC")
        print(f"[STATUS] Cash:      ${usd:.2f}")

        # 2. DECIDE
        if btc < 0.001:
            print("[INFO] No BTC to sell.")
        else:
            confirm = input(f"\n[WARNING] Dump {btc:.5f} BTC? (y/n): ")
            if confirm.lower() == 'y':
                print("[ADMIN] Sending SELL commands...")
                while btc >= 0.001:
                    layout.command.action = 2 # SELL
                    layout.command.quantity = 0.001
                    layout.command.command_id += 1
                    print(f" -> Selling 0.001...")
                    btc -= 0.001
                    time.sleep(1)

    finally:
        # 3. CLEANUP (Crucial Order)
        del layout  # <--- Delete the Python object wrapper
        mm.close()  # <--- Now we can safely close the memory map
        os.close(shm_fd)
        print("[ADMIN] Done.")

if __name__ == "__main__":
    main()