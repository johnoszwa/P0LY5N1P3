# risk_manager.py
import csv
import os
from datetime import datetime

CAPITAL_FILE = "paper_capital.csv"
POSITIONS_FILE = "positions.csv"
TRADES_FILE = "trades.csv"

# Risk parameters (you can adjust these)
RISK_PER_TRADE = 0.02      # 2% of capital per trade
STOP_LOSS_PCT = 0.15       # 15% loss triggers stop-loss
TAKE_PROFIT_PCT = 0.30     # 30% profit triggers take-profit (optional)

def get_current_capital():
    """Read current paper trading capital from file, or initialise with $1000."""
    if not os.path.exists(CAPITAL_FILE):
        with open(CAPITAL_FILE, "w") as f:
            f.write("1000")  # start with $1000 paper money
        return 1000.0
    with open(CAPITAL_FILE, "r") as f:
        return float(f.read().strip())

def update_capital(new_balance):
    """Overwrite paper capital file."""
    with open(CAPITAL_FILE, "w") as f:
        f.write(str(round(new_balance, 2)))

def calculate_position_size(entry_price, side):
    """
    Calculate position size in USD based on risk per trade.
    For prediction markets, we risk the full entry amount.
    Simple model: size = capital * RISK_PER_TRADE
    """
    capital = get_current_capital()
    size_usd = capital * RISK_PER_TRADE
    return round(size_usd, 2)

def check_stop_loss(market_name, current_price):
    """
    Check if any open position on this market should be stopped out.
    Returns (should_close, pnl_percent, side, entry_price, size_usd)
    """
    if not os.path.exists(POSITIONS_FILE):
        return False, 0, None, 0, 0

    with open(POSITIONS_FILE, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["market"] == market_name:
                side = row["side"]
                entry = float(row["entry_price"])
                size = float(row["size_usd"])

                if side == "YES":
                    pnl_pct = (current_price - entry) / entry
                else:  # NO
                    # entry is YES price, effective NO entry = 1 - entry
                    entry_no = 1 - entry
                    current_no = 1 - current_price
                    pnl_pct = (current_no - entry_no) / entry_no

                # Stop loss hit?
                if pnl_pct <= -STOP_LOSS_PCT:
                    return True, pnl_pct, side, entry, size
                # Optional take profit
                if pnl_pct >= TAKE_PROFIT_PCT:
                    return True, pnl_pct, side, entry, size

    return False, 0, None, 0, 0

def record_capital_after_trade(pnl_usd):
    """Update capital after a trade closes (including stop-loss)."""
    capital = get_current_capital()
    new_capital = capital + pnl_usd
    update_capital(new_capital)
    return new_capital