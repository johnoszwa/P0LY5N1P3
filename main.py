import time
import requests
import csv
import os
from datetime import datetime
from engine import score_signal, decide
from tracker import get_bias, log_trade
from risk_manager import (
    calculate_position_size,
    check_stop_loss,
    record_capital_after_trade,
    get_current_capital
)

# =========================
# 🔐 TELEGRAM CONFIG (PUT YOUR TOKEN HERE)
# =========================
BOT_TOKEN = "8774910658:AAFpCLE7MMd_3tphzc_ZOmMO6ipN7vnAN4A"
CHAT_ID = "P0ly5n1p3bot"

USE_TELEGRAM = True

# =========================
# PAPER TRADING FILES
# =========================
POSITIONS_FILE = "positions.csv"
TRADES_FILE = "trades.csv"

# =========================
# TELEGRAM SEND
# =========================
def send(msg):
    if not USE_TELEGRAM:
        print(msg)
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg})
    except:
        pass

# =========================
# INITIALIZE PAPER TRADING FILES
# =========================
def init_files():
    if not os.path.exists(POSITIONS_FILE):
        with open(POSITIONS_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["market", "side", "entry_price", "size_usd", "entry_time", "score", "decision"])
    if not os.path.exists(TRADES_FILE):
        with open(TRADES_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["market", "side", "entry_price", "exit_price", "size_usd", "pnl_usd", "entry_time", "exit_time", "outcome"])

# =========================
# PAPER TRADING FUNCTIONS
# =========================
def open_position(market, side, entry_price, size_usd, score, decision):
    with open(POSITIONS_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            market, side, entry_price, size_usd,
            datetime.utcnow().isoformat(), score, decision
        ])
    msg = f"📄 PAPER OPEN | {market} | {side} @ {entry_price:.2f} | ${size_usd}"
    send(msg)
    print(msg)

def close_position(market, exit_price, outcome, stop_loss=False):
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
        return None

    side = closed["side"]
    entry = float(closed["entry_price"])
    size = float(closed["size_usd"])

    # PnL calculation for binary markets
    if side == "YES":
        pnl = size * (exit_price - entry) / entry
    else:  # NO
        # entry stored as YES price; effective NO entry = 1 - entry
        entry_no = 1 - entry
        # exit_price is final YES price (1 or 0) or current price for stop-loss
        exit_no = 1 - exit_price
        pnl = size * (exit_no - entry_no) / entry_no

    pnl = round(pnl, 2)

    with open(TRADES_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            market, side, entry, exit_price, size, pnl,
            closed["entry_time"], datetime.utcnow().isoformat(), outcome
        ])

    # Rewrite positions file without closed one
    with open(POSITIONS_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["market", "side", "entry_price", "size_usd", "entry_time", "score", "decision"])
        writer.writerows([list(p.values()) for p in positions])

    # Update paper capital
    new_capital = record_capital_after_trade(pnl)

    msg = f"📄 PAPER CLOSE | {market} | {outcome} | PnL: ${pnl} | Balance: ${new_capital}"
    if stop_loss:
        msg = f"🛑 STOP-LOSS | {market} | Loss: ${pnl} | Balance: ${new_capital}"
    send(msg)
    print(msg)
    return pnl

def get_open_positions():
    if not os.path.exists(POSITIONS_FILE):
        return []
    with open(POSITIONS_FILE, "r") as f:
        reader = csv.DictReader(f)
        return list(reader)

# =========================
# LIVE MARKET DATA (Polymarket API)
# =========================
def fetch_markets():
    url = "https://gamma-api.polymarket.com/markets"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching markets: {e}")
        return []

def get_market_details(market_id):
    url = f"https://gamma-api.polymarket.com/markets/{market_id}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except:
        return None

def is_market_resolved(market_obj):
    # Polymarket API sometimes has 'resolved' boolean or 'closed' field
    return market_obj.get("resolved", False), market_obj.get("outcome", None)

def get_current_yes_price(market_id):
    details = get_market_details(market_id)
    if details and "outcomes" in details and len(details["outcomes"]) > 0:
        return float(details["outcomes"][0]["price"]) * 100
    return None

# =========================
# MAIN LOOP
# =========================
def run():
    print("🧠 P0ly5n1p3 v5.3 PAPER TRADING SYSTEM (LIVE DATA + RISK MGMT)")
    init_files()

    # Show starting capital
    capital = get_current_capital()
    send(f"🧠 P0ly5n1p3 v5.3 STARTING | Paper balance: ${capital} | Risk per trade: 2% | Stop-loss: 15%")

    while True:
        markets = fetch_markets()
        if not markets:
            print("No markets fetched. Retrying in 30s...")
            time.sleep(30)
            continue

        # 1. Check stop-loss for all open positions using current prices
        open_positions = get_open_positions()
        for pos in open_positions:
            market_name = pos["market"]
            # Find current market data
            market_obj = next((m for m in markets if m.get("question") == market_name), None)
            if market_obj and not market_obj.get("resolved", False):
                try:
                    current_yes_price = float(market_obj["outcomes"][0]["price"]) * 100
                    should_close, pnl_pct, side, entry, size = check_stop_loss(market_name, current_yes_price)
                    if should_close:
                        # Close as stop-loss
                        close_position(market_name, current_yes_price, "LOSS", stop_loss=True)
                        # Also log to bias tracker
                        log_trade(market_name, pos["score"], pos["decision"], "LOSS", None)
                except Exception as e:
                    print(f"Error checking stop-loss for {market_name}: {e}")
                    continue

        # 2. Check resolution for all open positions (normal close)
        open_positions = get_open_positions()  # refresh after potential stop-loss closes
        for pos in open_positions:
            market_name = pos["market"]
            market_obj = next((m for m in markets if m.get("question") == market_name), None)
            if not market_obj:
                continue
            resolved, outcome_yes = is_market_resolved(market_obj)
            if resolved:
                exit_price = 100.0 if outcome_yes == 1 else 0.0
                # Determine trade outcome
                side = pos["side"]
                if (side == "YES" and outcome_yes == 1) or (side == "NO" and outcome_yes == 0):
                    trade_outcome = "WIN"
                else:
                    trade_outcome = "LOSS"
                close_position(market_name, exit_price, trade_outcome)
                # Log to bias tracker
                log_trade(market_name, pos["score"], pos["decision"], trade_outcome, None)

        # 3. Generate new signals for unresolved markets
        for m in markets[:20]:  # limit to 20 per cycle
            try:
                if m.get("resolved", False):
                    continue

                name = m["question"]
                if "outcomes" not in m or len(m["outcomes"]) < 2:
                    continue
                yes_price = float(m["outcomes"][0]["price"]) * 100
                volume = m.get("volume", "Low")
                change = yes_price - 50  # momentum proxy

                bias = get_bias(name)
                score = score_signal(change, yes_price, volume, bias)
                decision = decide(score)

                # Trade only if score >= 4 (TRADE or STRONG_TRADE)
                if decision in ("TRADE", "STRONG_TRADE"):
                    # Avoid duplicate positions
                    if any(p["market"] == name for p in get_open_positions()):
                        continue

                    # Simple side logic: if YES price < 50, buy YES; else buy NO
                    side = "YES" if yes_price < 50 else "NO"
                    size_usd = calculate_position_size(yes_price, side)

                    # Ensure we have enough capital (should be fine with risk %)
                    capital = get_current_capital()
                    if size_usd > capital * 0.95:  # safety: don't use more than 95% of capital
                        print(f"Insufficient capital to open {name}: need ${size_usd}, have ${capital}")
                        continue

                    open_position(name, side, yes_price, size_usd, score, decision)

            except Exception as e:
                print(f"Error processing market: {e}")
                continue

        time.sleep(60)  # run every minute

if __name__ == "__main__":
    run()