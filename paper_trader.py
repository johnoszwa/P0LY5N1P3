import csv
import os
from datetime import datetime

POSITIONS_FILE = "positions.csv"
TRADES_FILE = "trades.csv"

# Ensure CSV headers exist
def init_files():
    if not os.path.exists(POSITIONS_FILE):
        with open(POSITIONS_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["market", "side", "entry_price", "size_usd", "entry_time", "score", "decision"])
    if not os.path.exists(TRADES_FILE):
        with open(TRADES_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["market", "side", "entry_price", "exit_price", "size_usd", "pnl_usd", "entry_time", "exit_time", "outcome"])

def open_position(market, side, entry_price, size_usd, score, decision):
    """Open a paper trade position."""
    with open(POSITIONS_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            market, side, entry_price, size_usd,
            datetime.utcnow().isoformat(), score, decision
        ])
    print(f"[PAPER] OPEN {side.upper()} on {market} @ {entry_price:.2f} for ${size_usd}")

def close_position(market, exit_price, outcome):
    """Close any open position for a market, compute PnL."""
    positions = []
    closed = None
    with open(POSITIONS_FILE, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["market"] == market:
                closed = row
                continue
            positions.append(row)

    if not closed:
        return

    side = closed["side"]
    entry = float(closed["entry_price"])
    size = float(closed["size_usd"])

    # For binary markets: PnL = size * (exit_price - entry_price) / entry_price? 
    # Simpler: if you buy YES at 0.60 and it resolves to 1.00, profit = size * (1/0.60 - 1)
    # But paper trading: we'll use simple formula: profit = size * (exit_price - entry_price) / entry_price
    # For YES: exit_price is 1.00 if win, 0.00 if loss.
    # For NO: exit_price is 1.00 if win (i.e., NO resolved true), 0.00 if loss.
    if side == "YES":
        pnl = size * (exit_price - entry) / entry
    else:  # NO
        # If you buy NO at price p (which is YES price), your effective NO price = 1-p
        # But easier: treat NO as buying YES at (1 - entry_price) and resolution same.
        # Simpler: We'll store entry as YES price. For NO, exit_price = 1 - resolved_YES_price.
        resolved_yes = exit_price  # exit_price is final YES price (1 or 0)
        if resolved_yes == 1:
            # NO loses -> exit price for NO = 0
            exit_no = 0
        else:
            exit_no = 1
        entry_no = 1 - entry
        pnl = size * (exit_no - entry_no) / entry_no

    # Log closed trade
    with open(TRADES_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            market, side, entry, exit_price, size, round(pnl, 2),
            closed["entry_time"], datetime.utcnow().isoformat(), outcome
        ])

    # Rewrite positions file without the closed one
    with open(POSITIONS_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["market", "side", "entry_price", "size_usd", "entry_time", "score", "decision"])
        writer.writerows([list(p.values()) for p in positions])

    print(f"[PAPER] CLOSE {market} → {outcome} | PnL: ${pnl:.2f}")
    return pnl

def get_open_positions():
    """Return list of open positions."""
    if not os.path.exists(POSITIONS_FILE):
        return []
    with open(POSITIONS_FILE, "r") as f:
        reader = csv.DictReader(f)
        return list(reader)
