"""decision_engine.py — Rule-based decision intelligence for Inventory Steward.

Generates recommendations, priority scores, explanations, and estimated impact
for each inventory risk without relying on an LLM for core business logic.
All logic is deterministic and auditable — suitable for hackathon demo and SME use.
"""

import math

# Mirror the same defaults used in main.py (env vars are loaded there)
LOW_STOCK_DAYS_THRESHOLD = 15
SLOW_MOVING_DAYS_LEFT_THRESHOLD = 45


# ─── Priority scoring ─────────────────────────────────────────────────────────

def _safe_num(value, default=0.0) -> float:
    """Best-effort numeric parsing for robust queue generation."""
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _low_stock_priority(days_left: float) -> tuple:
    """Low-stock severity rule requested by business."""
    if days_left <= 3:
        return "HIGH", 95
    if days_left <= 7:
        return "MEDIUM", 70
    return "LOW", 45


def _slow_moving_priority(days_to_clear: float, daily_sales: float, stock: float) -> tuple:
    """Slow-moving severity rule requested by business."""
    if (daily_sales <= 0 and stock > 0) or days_to_clear >= 90:
        return "HIGH", 90
    if days_to_clear >= 60:
        return "MEDIUM", 65
    return "LOW", 40


# ─── Main decision builder ────────────────────────────────────────────────────

def build_decision(item: dict, issue_type: str) -> dict:
    """
    Build a full decision record for a given inventory item and issue type.

    Args:
        item: dict from inventory row (must include stock, daily_sales, cost_price, sku, name)
        issue_type: 'low_stock' or 'slow_moving'

    Returns:
        dict with keys:
            recommendation  — what the system recommends doing
            priority_score  — numeric 0-100
            priority_level  — HIGH / MEDIUM / LOW
            explanation     — why this recommendation was generated (business-rule text)
            estimated_impact — quantified business value of taking action
    """
    stock = _safe_num(item.get("stock", 0), 0)
    daily_sales = _safe_num(item.get("daily_sales", 0), 0)
    # `cost_price` is used as a proxy for unit value in risk estimate.
    cost_price = _safe_num(item.get("cost_price", 0), 0)
    sku = item.get("sku", "N/A")
    name = item.get("name", "Unknown Item")

    days_left = (stock / daily_sales) if daily_sales > 0 else float("inf")

    if issue_type == "low_stock":
        # Formula:
        # target_stock = daily_sales * 30
        # reorder_qty = ceil(max(0, target_stock - current_stock))
        target_days = 30
        target_stock = daily_sales * target_days
        reorder_qty = max(0, math.ceil(target_stock - stock))

        level, score = _low_stock_priority(days_left)

        recommendation = (
            f"Reorder {reorder_qty} units immediately to cover 30 days of demand."
        )
        explanation = (
            f"{name} ({sku}) has {days_left:.2f} days of stock coverage "
            f"at {daily_sales:.2f} units/day. "
            f"This breaches the {LOW_STOCK_DAYS_THRESHOLD}-day reorder threshold. "
            f"Supplier should be contacted without delay."
        )
        # Missed-sales rule (consistent for all low-stock actions):
        # shortage_window = max(0, 15 - days_left)
        # missed_units = shortage_window * daily_sales
        shortfall_days = max(0.0, LOW_STOCK_DAYS_THRESHOLD - days_left)
        missed_units = round(daily_sales * shortfall_days, 1)
        missed_value = round(missed_units * cost_price, 2)
        estimated_impact = (
            f"Prevents ~{missed_units} units of missed sales over the next {shortfall_days:.2f} day(s). "
            f"Estimated revenue at risk: ${missed_value:,.0f}."
        )

    else:  # slow_moving
        capital_tied = round(stock * cost_price, 2)
        days_to_clear = (stock / daily_sales) if daily_sales > 0 else float("inf")
        level, score = _slow_moving_priority(days_to_clear, daily_sales, stock)

        recommendation = (
            f"Run flash clearance or pause restocking. "
            f"At current velocity, full stock clearance takes {days_to_clear:.2f} days."
            if math.isfinite(days_to_clear)
            else "Run flash clearance or pause restocking. At current velocity, stock is stagnant (no sales)."
        )
        explanation = (
            f"{name} ({sku}) holds {stock:.0f} units selling at only {daily_sales:.2f} units/day. "
            f"Stock will last {days_to_clear:.2f} days — "
            if math.isfinite(days_to_clear)
            else f"{name} ({sku}) has {stock:.0f} units with zero daily sales — "
        ) + (
            f"far exceeding the {SLOW_MOVING_DAYS_LEFT_THRESHOLD}-day slow-moving threshold. "
            f"Capital tied: ${capital_tied:,.0f}."
        )
        recovery_estimate = round(capital_tied * 0.55, 2)
        estimated_impact = (
            f"Estimated ${recovery_estimate:,.0f} capital recovery via clearance pricing. "
            f"Reduces holding cost for {stock} idle units."
        )

    return {
        "recommendation": recommendation,
        "priority_score": score,
        "priority_level": level,
        "explanation": explanation,
        "estimated_impact": estimated_impact,
    }


# ─── Return / complaint text analyser ────────────────────────────────────────

# Category signals are split into strong and weak buckets.
# Strong phrases are weighted more heavily and staff_note is weighted slightly
# higher to let warehouse evidence strengthen or override customer text.
_CATEGORY_SIGNALS = {
    "damaged_item": {
        "strong": [
            "damaged on arrival", "screen shattered", "shattered", "cracked",
            "broken", "dented", "arrived damaged", "smashed",
        ],
        "weak": [
            "damaged", "scratch", "scratched", "bent", "chipped", "cosmetic damage",
        ],
    },
    "defective_item": {
        "strong": [
            "not working", "cannot detect", "does not work", "stops charging",
            "malfunction", "faulty", "dead on arrival", "won't turn on", "no power",
        ],
        "weak": [
            "defective", "intermittent", "unstable", "disconnects", "not functioning",
            "unable to", "not recognized", "ports",
        ],
    },
    "wrong_item": {
        "strong": [
            "wrong model", "wrong color", "wrong colour", "received different item",
            "incorrect item", "not what i ordered",
        ],
        "weak": [
            "wrong item", "different item", "mismatch", "mistaken", "wrong size",
        ],
    },
    "missing_parts": {
        "strong": [
            "missing cable", "missing accessory", "missing parts", "incomplete package",
            "did not include", "not include", "missing charger",
        ],
        "weak": [
            "missing", "no cable", "no adapter", "no manual", "no accessories",
        ],
    },
    "delivery_issue": {
        "strong": [
            "never arrived", "not arrived", "still has not arrived", "parcel delayed",
            "delivery failed", "lost parcel", "tracking stuck",
        ],
        "weak": [
            "late delivery", "delayed", "delay", "overdue", "still waiting", "courier",
        ],
    },
    "customer_preference": {
        "strong": [
            "changed my mind", "do not want anymore", "ordered by mistake", "no longer want",
            "no longer need",
        ],
        "weak": [
            "don't want", "dont want", "not needed", "cancel", "return preference",
        ],
    },
    "quality_concern": {
        "strong": [
            "poor quality", "batch issue", "supplier issue", "material quality issue",
            "feels cheap",
        ],
        "weak": [
            "low quality", "bad quality", "flimsy", "not as described", "cheap",
            "quality concern",
        ],
    },
}

_CATEGORY_ACTIONS = {
    "damaged_item": "Approve refund or replacement. Flag transit handling and supplier damage review.",
    "defective_item": "Approve replacement or refund after quick verification. Flag product quality check.",
    "wrong_item": "Arrange exchange or return shipping. Review fulfilment accuracy and picking workflow.",
    "missing_parts": "Offer missing-part resend or replacement based on component criticality.",
    "delivery_issue": "Investigate courier status and provide resend or refund if non-delivery is confirmed.",
    "customer_preference": "Apply standard return-policy and eligibility checks before approval.",
    "quality_concern": "Review supplier batch quality and inspect similar inventory for related defects.",
    "other": "Route to manual review with additional evidence collection before final decision.",
}


def _match_signals(text: str, signals: dict) -> tuple:
    """Return matched strong/weak signals for one category in one text blob."""
    matched_strong = [kw for kw in signals["strong"] if kw in text]
    matched_weak = [kw for kw in signals["weak"] if kw in text]
    return matched_strong, matched_weak


def _score_category(reason_text: str, staff_text: str, signals: dict) -> dict:
    """Score a category using both customer reason and staff note signals."""
    reason_strong, reason_weak = _match_signals(reason_text, signals)
    staff_strong, staff_weak = _match_signals(staff_text, signals)

    # Weighted scoring: staff signals can strengthen/override weak reason signals.
    score = (
        len(reason_strong) * 3.0
        + len(reason_weak) * 1.8
        + len(staff_strong) * 3.8
        + len(staff_weak) * 2.2
    )

    # Bonus if same category appears in both reason and staff note.
    if (reason_strong or reason_weak) and (staff_strong or staff_weak):
        score += 1.5

    keywords_reason = reason_strong + reason_weak
    keywords_staff = staff_strong + staff_weak
    keywords_all = list(dict.fromkeys(keywords_reason + keywords_staff))

    return {
        "score": score,
        "keywords_reason": keywords_reason,
        "keywords_staff": keywords_staff,
        "keywords_all": keywords_all,
    }


def _severity_for(category: str, keywords: list) -> str:
    """Map category and matched evidence to explainable severity."""
    severe_damage_terms = {"screen shattered", "shattered", "broken", "damaged on arrival", "arrived damaged"}
    severe_defect_terms = {"not working", "cannot detect", "dead on arrival", "won't turn on", "no power"}
    severe_delivery_terms = {"never arrived", "not arrived", "still has not arrived", "lost parcel"}
    core_missing_terms = {"missing charger", "missing cable", "missing parts", "incomplete package"}

    kw = set(keywords)

    if category == "damaged_item":
        return "HIGH" if kw.intersection(severe_damage_terms) else "MEDIUM"
    if category == "defective_item":
        return "HIGH" if kw.intersection(severe_defect_terms) else "MEDIUM"
    if category == "wrong_item":
        return "HIGH"
    if category == "missing_parts":
        return "HIGH" if kw.intersection(core_missing_terms) else "MEDIUM"
    if category == "delivery_issue":
        return "HIGH" if kw.intersection(severe_delivery_terms) else "MEDIUM"
    if category == "customer_preference":
        return "LOW"
    if category == "quality_concern":
        return "MEDIUM"
    return "LOW"


def _confidence_from(score: float, has_reason_match: bool, has_staff_match: bool) -> float:
    """
    Confidence as 0.0-1.0 for API compatibility with existing frontend.
    This corresponds to the requested percentage buckets.
    """
    both_consistent = has_reason_match and has_staff_match
    if score >= 8 and both_consistent:
        return 0.92  # 92%
    if score >= 6:
        return 0.84  # 84%
    if score >= 4:
        return 0.76  # 76%
    if score >= 2:
        return 0.62  # 62%
    return 0.53  # 53% ambiguous


def analyse_return_text(reason_text: str, staff_note: str = "") -> dict:
    """
    Categorise a return/complaint using multi-signal rule scoring.

    Returns:
        issue_category, severity, suggested_action, confidence (0.0-1.0), matched_keywords
    """
    reason_clean = (reason_text or "").lower()
    staff_clean = (staff_note or "").lower()

    category_results = {}
    for category, signals in _CATEGORY_SIGNALS.items():
        category_results[category] = _score_category(reason_clean, staff_clean, signals)

    # Select highest-scoring category.
    ranked = sorted(category_results.items(), key=lambda x: x[1]["score"], reverse=True)
    best_category, best_info = ranked[0]

    # Prevent wrong defaults: no strong evidence -> classify as Other.
    if best_info["score"] < 2.0:
        best_category = "other"
        best_info = {
            "score": best_info["score"],
            "keywords_reason": [],
            "keywords_staff": [],
            "keywords_all": [],
        }

    has_reason_match = bool(best_info["keywords_reason"])
    has_staff_match = bool(best_info["keywords_staff"])

    confidence = _confidence_from(best_info["score"], has_reason_match, has_staff_match)
    severity = _severity_for(best_category, best_info["keywords_all"])

    response = {
        "issue_category": best_category,
        "severity": severity,
        "suggested_action": _CATEGORY_ACTIONS[best_category],
        "confidence": round(confidence, 2),
        "matched_keywords": best_info["keywords_all"],
        # Extra fields preserve keyword evidence by source without breaking existing contract.
        "matched_keywords_reason": best_info["keywords_reason"],
        "matched_keywords_staff": best_info["keywords_staff"],
    }
    return response
