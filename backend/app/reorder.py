import math

Z = 1.28  # about 90% service level


def suggest(fc, sd, stock, lead):
    """fc: list of >=28 daily forecasts. Order covers lead time + 7 day review period + safety stock."""
    lead = max(1, min(int(lead), 21))
    avg = sum(fc[:14]) / 14
    cover = stock / max(avg, 1)
    target = sum(fc[: lead + 7]) + Z * sd * math.sqrt(lead)
    order = max(0, math.ceil((target - stock) / 10) * 10)
    status = "risk" if cover < lead + 2 else "over" if cover > 40 else "ok"
    return {"avg": avg, "cover": cover, "order": order, "status": status}
