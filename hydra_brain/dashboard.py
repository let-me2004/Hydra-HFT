import time
import sys
import os
import mmap
import ctypes
from datetime import datetime
from collections import deque

from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.align import Align
from rich.console import Console
from rich import box

# -----------------------------------------------------------------------------
# 1. SETUP
# -----------------------------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, '..'))
from shared_defs.schema import SharedMemoryLayout, SHM_NAME

# CONFIGURATION
INITIAL_BALANCE = 10000.00
MAX_INV = 0.005

def get_data(layout):
    return {
        "usdt": layout.market.real_usdt_balance,
        "btc": layout.market.real_btc_balance,
        "bid": layout.market.bid_price,
        "ask": layout.market.ask_price,
        "latency": (time.time()*1000 - layout.market.local_time_ms),
        "cmd_id": layout.command.command_id,
        "last_action": layout.command.action
    }

# -----------------------------------------------------------------------------
# 2. VISUAL WIDGETS
# -----------------------------------------------------------------------------

def make_header(latency):
    beat = "●" if int(time.time() * 2) % 2 == 0 else "○"
    lat_color = "green" if latency < 50 else "yellow" if latency < 200 else "red"
    
    grid = Table.grid(expand=True)
    grid.add_column(justify="left", ratio=1)
    grid.add_column(justify="right", ratio=1)
    grid.add_row(
        f"[bold cyan]HYDRA HFT SYSTEM[/bold cyan] [dim]v2.1[/dim]",
        f"Latency: [{lat_color}]{latency:.1f}ms[/{lat_color}] | SYS {beat}"
    )
    return Panel(grid, style="white on black", box=box.HEAVY_EDGE)

def make_kpi_board(data):
    equity = data['usdt'] + (data['btc'] * data['bid'])
    pnl = equity - INITIAL_BALANCE
    pnl_pct = (pnl / INITIAL_BALANCE) * 100
    color = "spring_green1" if pnl >= 0 else "deep_pink1"

    # We use a Table to align the big numbers nicely
    table = Table(box=box.SIMPLE, expand=True, show_header=True)
    table.add_column("TOTAL EQUITY", justify="center")
    table.add_column("NET PnL ($)", justify="center")
    table.add_column("RETURN (%)", justify="center")
    table.add_column("CASH RESERVE", justify="center")
    
    table.add_row(
        f"[bold white]${equity:,.2f}[/bold white]",
        f"[bold {color}]${pnl:+,.2f}[/bold {color}]",
        f"[bold {color}]{pnl_pct:+.3f}%[/bold {color}]",
        f"[dim]${data['usdt']:,.2f}[/dim]"
    )
    return Panel(table, title="[bold]Portfolio Performance[/bold]", border_style=color)

def make_market_panel(data):
    spread = data['ask'] - data['bid']
    bps = (spread / data['bid']) * 10000
    
    grid = Table.grid(expand=True)
    grid.add_column(justify="left")
    grid.add_column(justify="right")
    
    grid.add_row("Ticker", "[bold]BTC/USDT[/bold]")
    grid.add_row("Price", f"[bold gold1]${data['bid']:,.2f}[/bold gold1]")
    grid.add_row("Spread", f"${spread:.2f} ({bps:.1f} bps)")
    
    return Panel(grid, title="Live Market", border_style="white")

def make_risk_panel(data):
    btc = data['btc']
    value = btc * data['bid']
    pct = min((btc / MAX_INV) * 100, 100)
    
    # ASCII Progress Bar
    bar_len = 30
    filled = int((pct / 100) * bar_len)
    color = "green" if pct < 50 else "yellow" if pct < 80 else "red"
    bar = f"[{color}]{'█' * filled}[/{color}]{'░' * (bar_len - filled)}"
    
    grid = Table.grid(expand=True)
    grid.add_column(justify="left")
    grid.add_column(justify="right")
    
    grid.add_row(f"Inventory: {btc:.5f} BTC", f"Value: [cyan]${value:,.2f}[/cyan]")
    grid.add_row(bar, f"{pct:.1f}% Used")
    
    return Panel(grid, title="Risk Management", border_style="blue")

def make_status_log(data):
    # Interpret Status
    if data['last_action'] == 1:
        msg = "[bold green]BUY SIGNAL ACTIVE[/bold green]"
    elif data['last_action'] == 2:
        msg = "[bold red]SELL SIGNAL ACTIVE[/bold red]"
    else:
        msg = "[dim]Scanning market structure...[/dim]"
        
    grid = Table.grid(expand=True)
    grid.add_column(style="dim", width=12)
    grid.add_column()
    
    ts = datetime.now().strftime("%H:%M:%S")
    grid.add_row(ts, f"Engine: {msg}")
    grid.add_row(ts, f"Command ID: #{data['cmd_id']}")
    
    return Panel(grid, title="System Logs", border_style="white")

# -----------------------------------------------------------------------------
# 3. MASTER COMPOSITOR
# -----------------------------------------------------------------------------
def generate_dashboard(data):
    # This creates a vertical stack of widgets
    
    # 1. Header
    header = make_header(data['latency'])
    
    # 2. KPI Board
    kpi = make_kpi_board(data)
    
    # 3. Middle Row (Market + Risk side-by-side)
    middle_row = Table.grid(expand=True, padding=(0, 1))
    middle_row.add_column(ratio=1)
    middle_row.add_column(ratio=2)
    middle_row.add_row(make_market_panel(data), make_risk_panel(data))
    
    # 4. Logs
    logs = make_status_log(data)
    
    # Assemble Main Grid
    layout = Table.grid(expand=True, padding=(0, 0))
    layout.add_row(header)
    layout.add_row(kpi)
    layout.add_row(middle_row)
    layout.add_row(logs)
    
    return layout

# -----------------------------------------------------------------------------
# 4. MAIN LOOP
# -----------------------------------------------------------------------------
def main():
    console = Console()
    console.clear()
    
    try:
        shm_fd = os.open(f"/dev/shm{SHM_NAME}", os.O_RDWR)
        mm = mmap.mmap(shm_fd, ctypes.sizeof(SharedMemoryLayout), access=mmap.ACCESS_WRITE)
        layout = SharedMemoryLayout.from_buffer(mm)
    except Exception as e:
        console.print(f"[bold red]CRITICAL ERROR:[/bold red] Hydra Engine not found.\n{e}")
        return

    # Use auto_refresh=False to prevent flickering
    with Live(console=console, refresh_per_second=10, screen=False) as live:
        while True:
            try:
                data = get_data(layout)
                ui = generate_dashboard(data)
                live.update(ui)
                time.sleep(0.1)
            except KeyboardInterrupt:
                break
    
    console.print("[yellow]Dashboard Disconnected.[/yellow]")

if __name__ == "__main__":
    main()