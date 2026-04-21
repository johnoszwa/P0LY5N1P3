import csv

# =========================
# SCORING ENGINE (LIVE)
# =========================
def score_signal(change, price, volume, bias):
    score = 0

    # movement strength
    if abs(change) > 20:
        score += 3
    elif abs(change) > 10:
        score += 2
    elif abs(change) > 5:
        score += 1

    # extreme pricing
    if price > 90:
        score += 2

    # low liquidity = more inefficiency
    if volume == "Low":
        score += 1

    # learned bias
    score += bias

    return score

# =========================
# DECISION ENGINE
# =========================
def decide(score):
    if score >= 6:
        return "STRONG_TRADE"
    elif score >= 4:
        return "TRADE"
    elif score >= 2:
        return "WATCH"
    return "IGNORE"
