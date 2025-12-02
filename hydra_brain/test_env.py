import sys
import os
import glob
import time

# --- FIX IMPORT PATHS ---
# 1. Add 'hydra_brain' folder to path (so we can find 'envs')
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# 2. Add 'HydraHFT' (root) folder to path (so we can find 'shared_defs' if needed)
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)
# ------------------------

from envs.crypto_env import CryptoMarketMakingEnv

# Auto-find the CSV file
data_dir = os.path.join(root_dir, 'data/raw_ticks')
list_of_files = glob.glob(f'{data_dir}/*.csv') 

if not list_of_files:
    print(f"Error: No CSV files found in {data_dir}")
    sys.exit(1)

latest_file = max(list_of_files, key=os.path.getctime)
print(f"Loading: {latest_file}")

env = CryptoMarketMakingEnv(latest_file)
obs, _ = env.reset()

print(f"Initial State: {obs}")

# Run 5 random steps
for i in range(5):
    action = env.action_space.sample()
    obs, reward, done, _, _ = env.step(action)
    print(f"Step {i+1} | Action: {action} | Inv: {obs[2]:.4f} | Reward: {reward:.4f}")