#ifndef HYDRA_SCHEMA_H
#define HYDRA_SCHEMA_H

#include <cstdint>

const char SHM_NAME[] = "/hydra_shm";
const size_t SHM_SIZE = 4096; 

// 1. Market & Account Data (C++ -> Python)
struct MarketState {
    uint64_t local_time_ms;    
    double bid_price;
    double bid_qty;
    double ask_price;
    double ask_qty;
    
    // --- NEW: REALITY SYNC ---
    double real_usdt_balance;  // Actual Cash on Binance
    double real_btc_balance;   // Actual Inventory on Binance
    // -------------------------

    bool system_ready;
};

// 2. Strategy Command (Python -> C++)
struct StrategyCommand {
    uint64_t command_id;      
    int action;               // 1=BUY, 2=SELL
    double quantity;
    double price;             
};

// 3. Master Layout
struct SharedMemoryLayout {
    MarketState market;
    StrategyCommand command;
};

#endif