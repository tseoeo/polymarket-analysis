"""Tests for opportunity explainer."""

import pytest
from services.opportunity_explainer import build_explanation, _compute_best_time


def test_arbitrage_explanation_positive_profit():
    """Arbitrage explanation returns positive profit per €1."""
    metrics = {
        "best_bid": 0.48,
        "best_ask": 0.52,
        "spread_pct": 0.08,
        "total_depth": 1000,
        "freshness_minutes": 10,
        "signal_count": 2,
        "slippage_100_eur": 0.005,
        "recent_price_move_pct": None,
        "typical_move_pct_24h": None,
    }
    result = build_explanation(["arbitrage", "spread_alert"], metrics)

    assert result["profit_per_eur"]["optimistic"] is not None
    assert result["profit_per_eur"]["optimistic"] > 0
    assert result["profit_per_eur"]["conservative"] is not None
    assert len(result["risks"]) >= 2
    assert result["best_time_to_act"]["status"] in ("act_now", "watch", "wait")


def test_spread_explanation_handles_missing_bid_ask():
    """Spread explanation gracefully handles missing bid/ask."""
    metrics = {
        "best_bid": None,
        "best_ask": None,
        "spread_pct": None,
        "total_depth": 500,
        "freshness_minutes": 20,
        "signal_count": 1,
        "slippage_100_eur": None,
        "recent_price_move_pct": None,
        "typical_move_pct_24h": None,
    }
    result = build_explanation(["spread_alert"], metrics)

    assert result["profit_per_eur"]["optimistic"] is None
    assert result["profit_per_eur"]["conservative"] is None
    assert "N/A" in result["profit_math"] or "No bid/ask" in result["profit_math"]


def test_volume_explanation_with_price_move():
    """Volume spike explanation uses recent price move."""
    metrics = {
        "best_bid": 0.50,
        "best_ask": 0.52,
        "spread_pct": 0.04,
        "total_depth": 2000,
        "freshness_minutes": 5,
        "signal_count": 2,
        "slippage_100_eur": 0.003,
        "recent_price_move_pct": 0.05,
        "typical_move_pct_24h": None,
    }
    result = build_explanation(["volume_spike"], metrics)

    assert result["profit_per_eur"]["optimistic"] == 0.05
    assert result["profit_per_eur"]["conservative"] == 0.025


def test_volume_explanation_no_price_move():
    """Volume/MM explanation returns None if price move missing."""
    metrics = {
        "best_bid": 0.50,
        "best_ask": 0.52,
        "spread_pct": 0.04,
        "total_depth": 1000,
        "freshness_minutes": 10,
        "signal_count": 1,
        "slippage_100_eur": None,
        "recent_price_move_pct": None,
        "typical_move_pct_24h": None,
    }
    result = build_explanation(["volume_spike"], metrics)

    assert result["profit_per_eur"]["optimistic"] is None
    assert result["profit_per_eur"]["conservative"] is None


def test_mm_pullback_with_typical_move():
    """MM pullback uses typical 24h move for profit estimate."""
    metrics = {
        "best_bid": 0.45,
        "best_ask": 0.55,
        "spread_pct": 0.10,
        "total_depth": 800,
        "freshness_minutes": 25,
        "signal_count": 1,
        "slippage_100_eur": None,
        "recent_price_move_pct": None,
        "typical_move_pct_24h": 0.08,
    }
    result = build_explanation(["mm_pullback"], metrics)

    assert result["profit_per_eur"]["optimistic"] == 0.08
    assert result["profit_per_eur"]["conservative"] == 0.04


def test_best_time_act_now():
    """Act now when all conditions are ideal."""
    metrics = {
        "freshness_minutes": 10,
        "slippage_100_eur": 0.005,
        "total_depth": 1000,
        "signal_count": 3,
    }
    result = _compute_best_time(metrics)
    assert result["status"] == "act_now"


def test_best_time_wait():
    """Wait when conditions are poor."""
    metrics = {
        "freshness_minutes": 45,
        "slippage_100_eur": 0.03,
        "total_depth": 200,
        "signal_count": 1,
    }
    result = _compute_best_time(metrics)
    assert result["status"] == "wait"


def test_best_time_watch():
    """Watch when conditions are mixed."""
    metrics = {
        "freshness_minutes": 20,
        "slippage_100_eur": 0.008,
        "total_depth": 600,
        "signal_count": 1,
    }
    result = _compute_best_time(metrics)
    assert result["status"] == "watch"


def test_priority_selects_arbitrage_over_spread():
    """When multiple signal types, arbitrage takes priority."""
    metrics = {
        "best_bid": 0.48,
        "best_ask": 0.52,
        "spread_pct": 0.08,
        "total_depth": 1000,
        "freshness_minutes": 10,
        "signal_count": 2,
        "slippage_100_eur": None,
        "recent_price_move_pct": None,
        "typical_move_pct_24h": None,
    }
    result = build_explanation(["spread_alert", "arbitrage"], metrics)
    # Should use arbitrage template (mentions "misalignment")
    assert "misalignment" in result["opportunity"].lower() or "mispricing" in result["opportunity"].lower()
