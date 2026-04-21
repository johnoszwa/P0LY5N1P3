import csv

MEMORY_FILE = "data.csv"

# =========================
# LEARNING FROM HISTORY
# =========================
def get_bias(market):
    try:
        wins, losses = 0, 0

        with open(MEMORY_FILE, "r") as f:
            reader = csv.DictReader(f)

            for r in reader:
                if r["market"] != market:
                    continue

                if r["outcome"] == "WIN":
                    wins += 1
                elif r["outcome"] == "LOSS":
                    losses += 1

        if wins + losses == 0:
            return 0

        winrate = wins / (wins + losses)

        if winrate > 0.6:
            return 1
        elif winrate < 0.4:
            return -1
        return 0

    except:
        return 0

# =========================
# LOG RESULTS
# =========================
def log_trade(market, score, decision, outcome, pnl):
    with open(MEMORY_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            market,
            score,
            decision,
            outcome,
            pnl
        ])
