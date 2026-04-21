import time
import requests
import csv
import os
from datetime import datetime
from engine import score_signal, decide
from tracker import get_bias, log_trade

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

def close_position(market, exit_price, outcome):
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
        # exit_price is final YES price (1 or 0)
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

    msg = f"📄 PAPER CLOSE | {market} | {outcome} | PnL: ${pnl}"
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
    print("🧠 P0ly5n1p3 v5.3 PAPER TRADING SYSTEM (LIVE DATA)")
    init_files()

    while True:
        markets = fetch_markets()
        if not markets:
            print("No markets fetched. Retrying in 30s...")
            time.sleep(30)
            continue

        # 1. Check resolution for all open positions
        open_positions = get_open_positions()
        for pos in open_positions:
            market_name = pos["market"]
            # Find market object by question text
            market_obj = next((m for m in markets if m.get("question") == market_name), None)
            if not market_obj:
                continue
            resolved, outcome_yes = is_market_resolved(market_obj)
            if resolved:
                # outcome_yes is typically 1 if YES wins, 0 if NO wins
                exit_price = 100.0 if outcome_yes == 1 else 0.0
                # Determine trade outcome
                side = pos["side"]
                if (side == "YES" and outcome_yes == 1) or (side == "NO" and outcome_yes == 0):
                    trade_outcome = "WIN"
                else:
                    trade_outcome = "LOSS"
                close_position(market_name, exit_price, trade_outcome)
                # Also log to tracker's data.csv for bias learning
                log_trade(market_name, pos["score"], pos["decision"], trade_outcome, None)  # pnl handled separately

        # 2. Generate new signals for unresolved markets
        for m in markets[:20]:  # limit to 20 per cycle
            try:
                if m.get("resolved", False):
                    continue

                name = m["question"]
                # Ensure outcomes exist
                if "outcomes" not in m or len(m["outcomes"]) < 2:
                    continue
                yes_price = float(m["outcomes"][0]["price"]) * 100
                volume = m.get("volume", "Low")
                # Simple momentum proxy
                change = yes_price - 50

                bias = get_bias(name)
                score = score_signal(change, yes_price, volume, bias)
                decision = decide(score)

                # Trade only if score >= 4 (TRADE or STRONG_TRADE)
                if decision in ("TRADE", "STRONG_TRADE"):
                    # Avoid duplicate positions on same market
                    if any(p["market"] == name for p in get_open_positions()):
                        continue

                    # Simple side logic: if YES price < 50, buy YES; else buy NO
                    # (You can replace with your own strategy)
                    side = "YES" if yes_price < 50 else "NO"
                    size_usd = 10.0  # fixed paper size (can be adjusted)

                    open_position(name, side, yes_price, size_usd, score, decision)

            except Exception as e:
                print(f"Error processing market: {e}")
                continue

        time.sleep(60)  # run every minute

if __name__ == "__main__":
    run()
