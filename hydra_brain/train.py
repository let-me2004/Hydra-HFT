import sys
import os
import glob
import pandas as pd
import numpy as np
from sb3_contrib import RecurrentPPO
from stable_baselines3.common.vec_env import DummyVecEnv

# Fix Import Path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
sys.path.append(os.path.dirname(current_dir))

from envs.crypto_env import CryptoMarketMakingEnv

def load_all_data():
    """Loads and merges ALL Parquet files from data/parquet"""
    data_dir = os.path.join(os.path.dirname(current_dir), 'data/parquet')
    files = glob.glob(f'{data_dir}/*.parquet')
    
    if not files:
        print(f"Error: No Parquet files found in {data_dir}")
        print("Did you run scripts/download_data.py?")
        sys.exit(1)
        
    print(f"[Hydra] Found {len(files)} data files. Loading...")
    
    # Load all files into a list of DataFrames
    dfs = []
    for f in files:
        print(f"  - Loading {os.path.basename(f)}...")
        df = pd.read_parquet(f)
        dfs.append(df)
        
    # Concatenate into one massive timeline
    full_df = pd.concat(dfs).sort_values('time').reset_index(drop=True)
    print(f"[Hydra] Data Loaded. Total Ticks: {len(full_df):,}")
    return full_df

def train():
    # 1. Load Big Data
    df = load_all_data()

    # 2. Setup Environment
    # We pass the DataFrame directly to the Env
    print("[Hydra] Initializing Environment...")
    env = DummyVecEnv([lambda: CryptoMarketMakingEnv(df)])

    # 3. Define the LSTM Brain (RecurrentPPO)
    print("[Hydra] Initializing RecurrentPPO (LSTM)...")
    model = RecurrentPPO(
        "MlpLstmPolicy", 
        env, 
        verbose=1, 
        learning_rate=3e-4, # Standard for LSTMs
        batch_size=128,     # Larger batch size for sequence stability
        n_steps=1024,       # Steps per update
        ent_coef=0.01,      # Curiosity
        policy_kwargs={"enable_critic_lstm": False} # Optimization
    )

    # 4. Train
    print("[Hydra] Starting Training Loop (Target: 1 Million Steps)...")
    try:
        model.learn(total_timesteps=1_000_000)
    except KeyboardInterrupt:
        print("\n[Hydra] Training Interrupted. Saving current progress...")

    # 5. Save the Model
    save_path = os.path.join(current_dir, "checkpoints/hydra_lstm_v1")
    model.save(save_path)
    print(f"[Hydra] LSTM Brain saved to {save_path}.zip")

if __name__ == "__main__":
    train()