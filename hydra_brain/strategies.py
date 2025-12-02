import numpy as np
from collections import deque

# ... (GridStrategy and OFIStrategy remain unchanged) ...
# Paste them here if you want, or just ensure TrendStrategy below replaces the old one

class TrendStrategy:
    def __init__(self, short_window=10000, long_window=50000, threshold=0.0005):
        self.short_window = short_window
        self.long_window = long_window
        self.threshold = threshold # <--- NEW FILTER
        
        self.short_deque = deque(maxlen=short_window)
        self.long_deque = deque(maxlen=long_window)
        
        self.short_sum = 0.0
        self.long_sum = 0.0
        
        self.position = 0

    def decide(self, row, inventory, cash):
        price = row.price
        
        # 1. Update Short Window
        if len(self.short_deque) == self.short_window:
            self.short_sum -= self.short_deque[0]
        self.short_deque.append(price)
        self.short_sum += price
        
        # 2. Update Long Window
        if len(self.long_deque) == self.long_window:
            self.long_sum -= self.long_deque[0]
        self.long_deque.append(price)
        self.long_sum += price
        
        # Warmup
        if len(self.long_deque) < self.long_window:
            return 0
            
        # 3. Calculate Averages
        short_avg = self.short_sum / self.short_window
        long_avg = self.long_sum / self.long_window
        
        # 4. Logic: Golden Cross WITH BAND FILTER
        # Only buy if Short is SIGNIFICANTLY higher than Long
        if short_avg > long_avg * (1 + self.threshold):
            if self.position == 0:
                self.position = 1
                return 1 # BUY
                
        # Sell if trend collapses (Standard Cross is fine for exit)
        elif short_avg < long_avg:
            if self.position == 1:
                self.position = 0
                return 2 # SELL
                
        return 0