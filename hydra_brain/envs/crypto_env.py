import gymnasium as gym
import numpy as np
import pandas as pd
from gymnasium import spaces

class CryptoMarketMakingEnv(gym.Env):
    def __init__(self, df, max_steps=0):
        super(CryptoMarketMakingEnv, self).__init__()
        
        # 1. Use the Pre-loaded DataFrame
        self.df = df
        self.max_steps = len(self.df) if max_steps == 0 else min(len(self.df), max_steps)
        self.current_step = 0
        
        # 2. Define Action Space
        # 0=Hold, 1=Aggressive, 2=Passive, 3=Dump
        self.action_space = spaces.Discrete(4)
        
        # 3. Define Observation Space
        # [Spread, OFI, Inventory, Volatility]
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(4,), dtype=np.float32
        )
        
        # Simulation State
        self.inventory = 0.0
        self.cash = 10000.0 
        
        # Volatility Tracking (For Reward)
        self.recent_prices = []

    def reset(self, seed=None):
        super().reset(seed=seed)
        self.current_step = 0
        self.inventory = 0.0
        self.cash = 10000.0
        self.recent_prices = []
        return self._next_observation(), {}
    
    def _next_observation(self):
        if self.current_step >= len(self.df):
            self.current_step = len(self.df) - 1
            
        row = self.df.iloc[self.current_step]
        
        # Maintain a rolling window of last 20 prices for volatility
        self.recent_prices.append(row['price'])
        if len(self.recent_prices) > 20:
            self.recent_prices.pop(0)
            
        volatility = np.std(self.recent_prices) if len(self.recent_prices) > 1 else 0.0

        obs = np.array([
            0.0, # Placeholder for Spread (Parquet data might only have price)
            float(row['ibm']), # 'is_buyer_maker' acts as a proxy for flow direction
            self.inventory,
            volatility
        ], dtype=np.float32)
        return obs
    
    def step(self, action):
        self.current_step += 1
        terminated = (self.current_step >= self.max_steps - 1)
        truncated = False
        
        row = self.df.iloc[self.current_step]
        price = float(row['price'])
        reward = 0
        
        # --- EXECUTION LOGIC ---
        # We simulate a 0.01% spread capture
        spread = price * 0.0001 
        
        if action == 1: # Aggressive (Buy)
            reward += spread
            self.inventory += 0.001
        elif action == 3: # Dump (Sell)
            reward -= spread
            self.inventory -= 0.001
            
        # --- AVELLANEDA-STOIKOV REWARD ---
        # 1. Inventory Risk (Quadratic Penalty)
        inv_penalty = 0.5 * (self.inventory ** 2)
        
        # 2. Volatility Penalty
        vol = np.std(self.recent_prices) if len(self.recent_prices) > 1 else 0.0
        vol_penalty = vol * 1.0
        
        reward = reward - inv_penalty - vol_penalty
        
        return self._next_observation(), reward, terminated, truncated, {}