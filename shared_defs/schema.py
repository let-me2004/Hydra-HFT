import ctypes

class MarketState(ctypes.Structure):
    _fields_ = [
        ("local_time_ms", ctypes.c_uint64),
        ("bid_price", ctypes.c_double),
        ("bid_qty", ctypes.c_double),
        ("ask_price", ctypes.c_double),
        ("ask_qty", ctypes.c_double),
        
        # --- NEW FIELDS ---
        ("real_usdt_balance", ctypes.c_double),
        ("real_btc_balance", ctypes.c_double),
        # ------------------
        
        ("system_ready", ctypes.c_bool),
    ]

class StrategyCommand(ctypes.Structure):
    _fields_ = [
        ("command_id", ctypes.c_uint64),
        ("action", ctypes.c_int),
        ("quantity", ctypes.c_double),
        ("price", ctypes.c_double),
    ]

class SharedMemoryLayout(ctypes.Structure):
    _fields_ = [
        ("market", MarketState),
        ("command", StrategyCommand),
    ]

SHM_NAME = "/hydra_shm"
SHM_SIZE = 4096