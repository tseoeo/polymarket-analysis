"""Opportunity explanation generator.

Produces plain-language explanations for each opportunity type,
including profit estimates per €1 and actionability signals.
"""

from typing import Dict, List, Optional, Any


# Configurable fee estimate for arbitrage
ESTIMATED_FEE_PCT = 0.005  # 0.5%


def build_explanation(
    alert_types: List[str],
    metrics: Dict[str, Any],
) -> Dict[str, Any]:
    """Build an explanation block for an opportunity.

    Chooses the best template based on alert types (priority order:
    arbitrage > spread_alert > volume_spike > mm_pullback).

    Args:
        alert_types: List of active signal types for this market.
        metrics: Opportunity metrics dict (spread_pct, best_bid, best_ask,
                 total_depth, freshness_minutes, slippage_100_eur,
                 signal_count, recent_price_move_pct, typical_move_pct_24h).

    Returns:
        Explanation dict with opportunity, action, profit_per_eur,
        profit_math, risks, and best_time_to_act.
    """
    # Pick the primary signal type by priority
    priority = ["arbitrage", "spread_alert", "volume_spike", "mm_pullback"]
    primary = None
    for p in priority:
        if p in alert_types:
            primary = p
            break
    if not primary:
        primary = alert_types[0] if alert_types else "unknown"

    # Dispatch to type-specific builder
    builders = {
        "arbitrage": _explain_arbitrage,
        "spread_alert": _explain_spread,
        "volume_spike": _explain_volume_spike,
        "mm_pullback": _explain_mm_pullback,
    }
    builder = builders.get(primary, _explain_generic)
    result = builder(metrics)

    # Compute best_time_to_act
    result["best_time_to_act"] = _compute_best_time(metrics)

    return result


def _explain_arbitrage(metrics: Dict[str, Any]) -> Dict[str, Any]:
    best_bid = metrics.get("best_bid")
    best_ask = metrics.get("best_ask")

    # For arbitrage, profit comes from price misalignment
    # Simplified: use spread as proxy for single-market arb
    profit_optimistic = None
    profit_conservative = None
    math_text = "No bid/ask data available."

    if best_bid is not None and best_ask is not None and best_ask > 0:
        gap = best_bid + (1.0 - best_ask)  # YES bid + NO ask complement
        # Simplified single-market: if YES+NO < 1, profit = 1 - (ask_yes + ask_no)
        # We only have one side, so use spread as approximation
        spread = best_ask - best_bid
        if spread > 0:
            profit_optimistic = round(spread / best_ask, 4)
            profit_conservative = round(max(profit_optimistic - ESTIMATED_FEE_PCT, 0), 4)
            math_text = (
                f"Buy at {best_ask:.3f}, sell at {best_bid:.3f}. "
                f"Gap: {spread:.3f}. Conservative subtracts ~{ESTIMATED_FEE_PCT:.1%} fees."
            )

    return {
        "opportunity": (
            "Price misalignment detected — the bid-ask gap is wider than normal, "
            "suggesting temporary mispricing."
        ),
        "action": (
            "Buy the underpriced side and sell the overpriced side. "
            "If both legs fill, you lock in the difference."
        ),
        "profit_per_eur": {
            "conservative": profit_conservative,
            "optimistic": profit_optimistic,
            "note": "Guaranteed profit if all legs fill. Conservative assumes fees.",
        },
        "profit_math": math_text,
        "risks": [
            "Fees and slippage can erase thin margins.",
            "One leg may fill late while prices move.",
            "Relationship tagging errors can create false signals.",
        ],
    }


def _explain_spread(metrics: Dict[str, Any]) -> Dict[str, Any]:
    best_bid = metrics.get("best_bid")
    best_ask = metrics.get("best_ask")
    spread_pct = metrics.get("spread_pct")

    profit_optimistic = None
    profit_conservative = None
    math_text = "No bid/ask data available."

    if best_bid is not None and best_ask is not None and best_bid > 0:
        gap = best_ask - best_bid
        profit_optimistic = round(gap / best_bid, 4)
        profit_conservative = round((gap * 0.5) / best_bid, 4)
        math_text = (
            f"Spread gap: {gap:.3f} (bid {best_bid:.3f}, ask {best_ask:.3f}). "
            f"Conservative assumes you capture half the gap."
        )

    return {
        "opportunity": (
            f"The bid-ask spread is unusually wide"
            f"{f' ({spread_pct:.1%})' if spread_pct else ''}"
            ", suggesting reduced competition from market makers."
        ),
        "action": (
            "Place a limit order near the bid price and wait for the spread to tighten. "
            "Sell when the gap closes."
        ),
        "profit_per_eur": {
            "conservative": profit_conservative,
            "optimistic": profit_optimistic,
            "note": "Conservative assumes you capture half the price gap. Optimistic assumes the full gap closes.",
        },
        "profit_math": math_text,
        "risks": [
            "The spread may stay wide or widen further.",
            "Low liquidity can cause slippage on entry or exit.",
            "The price may move against you before the spread tightens.",
        ],
    }


def _explain_volume_spike(metrics: Dict[str, Any]) -> Dict[str, Any]:
    recent_move = metrics.get("recent_price_move_pct")

    profit_optimistic = None
    profit_conservative = None
    math_text = "No recent price move data available."

    if recent_move is not None and recent_move != 0:
        abs_move = abs(recent_move)
        profit_optimistic = round(abs_move, 4)
        profit_conservative = round(abs_move * 0.5, 4)
        direction = "up" if recent_move > 0 else "down"
        math_text = (
            f"Price moved {abs_move:.1%} {direction} in the last hour. "
            f"Conservative assumes you capture half of this move."
        )

    return {
        "opportunity": (
            "Unusual trading volume detected — often signals informed traders "
            "acting on new information."
        ),
        "action": (
            "Follow the momentum if the price is moving in a clear direction. "
            "Avoid chasing if the price has already jumped significantly."
        ),
        "profit_per_eur": {
            "conservative": profit_conservative,
            "optimistic": profit_optimistic,
            "note": "Estimated from the last hour's price move (not guaranteed).",
        },
        "profit_math": math_text,
        "risks": [
            "The news may already be priced in.",
            "Momentum can reverse quickly.",
            "Slippage is common in thin, fast-moving markets.",
        ],
    }


def _explain_mm_pullback(metrics: Dict[str, Any]) -> Dict[str, Any]:
    typical_move = metrics.get("typical_move_pct_24h")

    profit_optimistic = None
    profit_conservative = None
    math_text = "No reliable move estimate available."

    if typical_move is not None and typical_move != 0:
        abs_move = abs(typical_move)
        profit_optimistic = round(abs_move, 4)
        profit_conservative = round(abs_move * 0.5, 4)
        math_text = (
            f"Typical 24h price range: {abs_move:.1%}. "
            f"Conservative assumes you capture half of this."
        )

    return {
        "opportunity": (
            "Market makers have withdrawn liquidity — this often precedes "
            "significant price movement."
        ),
        "action": (
            "This is primarily a risk flag. Only act with strong conviction "
            "and use smaller position sizes than normal."
        ),
        "profit_per_eur": {
            "conservative": profit_conservative,
            "optimistic": profit_optimistic,
            "note": "Based on typical 24h price range. High uncertainty." if typical_move else "No reliable move estimate.",
        },
        "profit_math": math_text,
        "risks": [
            "No guaranteed edge — this is directional risk.",
            "Thin liquidity means poor fill prices.",
            "Often precedes volatility, not certainty.",
        ],
    }


def _explain_generic(metrics: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "opportunity": "A market signal was detected but the type is unclear.",
        "action": "Monitor the market and wait for clearer signals before acting.",
        "profit_per_eur": {
            "conservative": None,
            "optimistic": None,
            "note": "Cannot estimate profit without a clear signal type.",
        },
        "profit_math": "N/A",
        "risks": [
            "Signal type is unclear — proceed with caution.",
            "Market conditions can change quickly.",
            "Always check data freshness before acting.",
        ],
    }


def _compute_best_time(metrics: Dict[str, Any]) -> Dict[str, str]:
    """Compute act_now / watch / wait status."""
    freshness = metrics.get("freshness_minutes")
    slippage = metrics.get("slippage_100_eur")
    depth = metrics.get("total_depth", 0)
    signals = metrics.get("signal_count", 0)

    # Wait conditions
    wait_reasons = []
    if freshness is not None and freshness > 30:
        wait_reasons.append("data is stale")
    if slippage is not None and slippage > 0.02:
        wait_reasons.append("slippage is high")
    if depth < 300:
        wait_reasons.append("depth is too low")

    if wait_reasons:
        return {
            "status": "wait",
            "reason": f"Wait — {', '.join(wait_reasons)}.",
        }

    # Act now conditions
    act_now = (
        (freshness is not None and freshness <= 15)
        and (slippage is None or slippage <= 0.01)
        and depth >= 500
        and signals >= 2
    )

    if act_now:
        return {
            "status": "act_now",
            "reason": "Act now — fresh data, strong depth, low slippage.",
        }

    # Default: watch
    return {
        "status": "watch",
        "reason": "Watch — conditions are acceptable but not ideal.",
    }
