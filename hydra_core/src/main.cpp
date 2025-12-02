#include <boost/beast/core.hpp>
#include <boost/beast/ssl.hpp>
#include <boost/beast/websocket.hpp>
#include <boost/beast/websocket/ssl.hpp>
#include <boost/asio/connect.hpp>
#include <boost/asio/ip/tcp.hpp>
#include <boost/asio/ssl/stream.hpp>
#include <boost/interprocess/shared_memory_object.hpp>
#include <boost/interprocess/mapped_region.hpp>
#include <iostream>
#include <string>
#include <thread>
#include <chrono>
#include <iomanip>
#include <sstream>
#include <random> 

#include "../../shared_defs/schema.h"

// ================= CONFIGURATION =================
// SHADOW MODE (Bitcoin)
const double SIM_FEE_RATE = 0.00075; 
const double SIM_START_CASH = 10000.0;
// =================================================

namespace beast = boost::beast;         
namespace http = beast::http;           
namespace websocket = beast::websocket; 
namespace net = boost::asio;            
namespace ssl = boost::asio::ssl;       
namespace bip = boost::interprocess;
using tcp = net::ip::tcp;               

struct VirtualWallet {
    double usdt = SIM_START_CASH;
    double btc = 0.0;
} sim_wallet;

uint64_t current_timestamp() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
}

double get_json_value(const std::string& json, std::string key) {
    std::string search = "\"" + key + "\":\"";
    size_t start = json.find(search);
    if (start == std::string::npos) return 0.0;
    start += search.length();
    size_t end = json.find("\"", start);
    try { return std::stod(json.substr(start, end - start)); } catch (...) { return 0.0; }
}

// --- SHADOW SYNC THREAD ---
void balance_sync_loop(SharedMemoryLayout* layout) {
    std::cout << "[SHADOW SYNC] Thread Started." << std::endl;
    while(true) {
        layout->market.real_btc_balance = sim_wallet.btc;
        layout->market.real_usdt_balance = sim_wallet.usdt;
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }
}

// --- SHADOW EXECUTION THREAD ---
void execution_loop(SharedMemoryLayout* layout) {
    std::cout << "[EXECUTION] Shadow Execution Layer Active." << std::endl;
    uint64_t last_cmd_id = layout->command.command_id;
    std::default_random_engine generator;
    std::normal_distribution<double> latency_dist(20.0, 10.0);

    int pending_action = 0; 
    double pending_price = 0.0;
    double pending_qty = 0.0;

    while(true) {
         if (layout->command.command_id > last_cmd_id) {
            last_cmd_id = layout->command.command_id;
            std::this_thread::sleep_for(std::chrono::milliseconds(20));

            pending_action = layout->command.action;
            pending_qty = layout->command.quantity;
            pending_price = layout->command.price;
            
            std::string type = (pending_action == 1) ? "BUY" : "SELL";
            std::cout << "\n[ORDER] Placed " << type << " " << pending_qty << " @ " << pending_price << std::endl;
         }

         if (pending_action != 0) {
             double mkt_bid = layout->market.bid_price;
             double mkt_ask = layout->market.ask_price;
             bool filled = false;
             double fill_price = 0.0;

             if (pending_action == 1) { // BUY
                 if (pending_price == 0.0 || pending_price >= mkt_ask) { fill_price = mkt_ask; filled = true; } 
                 else if (mkt_ask <= pending_price) { fill_price = pending_price; filled = true; }
             }
             else if (pending_action == 2) { // SELL
                 if (pending_price == 0.0 || pending_price <= mkt_bid) { fill_price = mkt_bid; filled = true; }
                 else if (mkt_bid >= pending_price) { fill_price = pending_price; filled = true; }
             }

             if (filled) {
                 double cost = fill_price * pending_qty;
                 double fee = cost * SIM_FEE_RATE;
                 if (pending_action == 1 && sim_wallet.usdt >= cost + fee) {
                     sim_wallet.usdt -= (cost + fee);
                     sim_wallet.btc += pending_qty;
                     std::cout << "[SHADOW EXEC] BOUGHT " << pending_qty << " BTC @ " << fill_price << std::endl;
                 } 
                 else if (pending_action == 2 && sim_wallet.btc >= pending_qty) {
                     sim_wallet.btc -= pending_qty;
                     sim_wallet.usdt += (cost - fee);
                     std::cout << "[SHADOW EXEC] SOLD " << pending_qty << " BTC @ " << fill_price << std::endl;
                 }
                 pending_action = 0; 
             }
         }
         std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
}

int main() {
    try {
        std::cout << "[Hydra] Starting Engine..." << std::endl;

        bip::shared_memory_object::remove(SHM_NAME);
        bip::shared_memory_object shm(bip::create_only, SHM_NAME, bip::read_write);
        shm.truncate(sizeof(SharedMemoryLayout)); 
        bip::mapped_region region(shm, bip::read_write);
        SharedMemoryLayout *layout = static_cast<SharedMemoryLayout*>(region.get_address());
        layout->command.command_id = 0;

        std::thread exec_thread(execution_loop, layout);
        exec_thread.detach(); 
        std::thread sync_thread(balance_sync_loop, layout);
        sync_thread.detach();

        // --- RECONNECTION LOOP ---
        while(true) {
            try {
                std::cout << "[Hydra] Connecting..." << std::endl;
                net::io_context ioc;
                ssl::context ctx{ssl::context::tlsv12_client};
                ctx.set_default_verify_paths();
                
                tcp::resolver resolver{ioc};
                
                // FIX: Use beast::tcp_stream instead of tcp::socket
                // This class supports the .expires_after() timeout function
                websocket::stream<beast::ssl_stream<beast::tcp_stream>> ws{ioc, ctx};
                
                auto const host = "stream.binance.com";
                auto const port = "443";
                auto const target = "/ws/btcusdt@bookTicker"; 

                auto const results = resolver.resolve(host, port);
                
                // FIX: Use Beast's connect() method
                beast::get_lowest_layer(ws).connect(results);
                
                // Set initial handshake timeout
                beast::get_lowest_layer(ws).expires_after(std::chrono::seconds(30));
                
                ws.next_layer().handshake(ssl::stream_base::client);
                ws.handshake(host, target);
                
                // Disable timeout for the stream itself (we manage it per-read below)
                beast::get_lowest_layer(ws).expires_never();
                
                std::cout << "[Hydra] Connected!" << std::endl;

                beast::flat_buffer buffer;
                while(true) {
                    // --- TIMEOUT LOGIC (Zombie Fix) ---
                    // If no data arrives for 10 seconds, this throws an exception
                    beast::get_lowest_layer(ws).expires_after(std::chrono::seconds(10));
                    
                    ws.read(buffer);
                    
                    // Reset
                    beast::get_lowest_layer(ws).expires_never(); 

                    std::string msg = beast::buffers_to_string(buffer.data());
                    layout->market.bid_price = get_json_value(msg, "b");
                    layout->market.ask_price = get_json_value(msg, "a");
                    layout->market.bid_qty = get_json_value(msg, "B");
                    layout->market.ask_qty = get_json_value(msg, "A");
                    layout->market.local_time_ms = current_timestamp();
                    buffer.consume(buffer.size());
                }
            }
            catch (std::exception const& e) {
                // Catches the timeout and reconnects automatically
                std::cerr << "[Hydra] Connection Lost: " << e.what() << std::endl;
                std::cout << "[Hydra] Reconnecting in 5s..." << std::endl;
                std::this_thread::sleep_for(std::chrono::seconds(5));
            }
        }
    }
    catch (std::exception const& e) {
        std::cerr << "Fatal Error: " << e.what() << std::endl;
        return 1;
    }
    return 0;
}