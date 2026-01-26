# Polymarket Analysis Tool - Complete Technical Specification

## Overview

Build a Polymarket analysis tool that discovers trading opportunities not visible in the standard interface. The tool should analyze four key areas:

1. **Cross-Market Arbitrage Detection** - Find mispriced related markets
2. **Order Book Analysis** - Analyze liquidity, spreads, and depth
3. **Volume Anomaly Detection** - Spot unusual trading activity
4. **Market Maker Pattern Analysis** - Understand liquidity provider behavior

The user is not a developer, so all outputs should be clear dashboards, alerts, and explanations.

---

## Data Sources

### Polymarket APIs

**1. Gamma API (Market Metadata)**
- Base URL: `https://gamma-api.polymarket.com`
- Endpoints:
  - `GET /markets` - List all markets
  - `GET /markets/{id}` - Single market details
- Returns: Market titles, descriptions, outcomes, resolution criteria, dates, categories
- No authentication required
- Rate limits: Be respectful, add delays between requests

**2. CLOB API (Order Book & Trades)**
- Base URL: `https://clob.polymarket.com`
- Documentation: https://docs.polymarket.com
- Endpoints:
  - `GET /book` - Order book for a market
  - `GET /trades` - Recent trades
  - `GET /prices` - Current prices
- Returns: Bids, asks, trade history, timestamps
- Some endpoints require API key for higher rate limits

### Data to Collect

| Data Type | Source | Frequency | Purpose |
|-----------|--------|-----------|---------|
| Market list & metadata | Gamma API | Every 15 min | Know what markets exist |
| Current prices | CLOB API | Every 1 min | Arbitrage detection |
| Order books | CLOB API | Every 30 sec | Book analysis, MM patterns |
| Trade history | CLOB API | Every 1 min | Volume analysis |

---

## Database Schema

Use PostgreSQL or SQLite. PostgreSQL preferred for production.

### Tables

```sql
-- All markets on Polymarket
CREATE TABLE markets (
    id TEXT PRIMARY KEY,                    -- Polymarket's market ID
    condition_id TEXT,                      -- Contract condition ID
    question TEXT NOT NULL,                 -- Market question/title
    description TEXT,                       -- Full description
    outcomes TEXT[],                        -- Array of outcome names, e.g. ['Yes', 'No']
    outcome_prices DECIMAL[],               -- Current prices for each outcome
    category TEXT,                          -- e.g. 'Politics', 'Sports', 'Crypto'
    end_date TIMESTAMP,                     -- When market resolves
    volume_total DECIMAL,                   -- Total volume traded
    liquidity DECIMAL,                      -- Current liquidity
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- For tracking related markets (arbitrage detection)
CREATE TABLE market_relationships (
    id SERIAL PRIMARY KEY,
    relationship_type TEXT NOT NULL,        -- 'mutually_exclusive', 'conditional', 'time_sequence', 'subset'
    parent_market_id TEXT REFERENCES markets(id),
    child_market_id TEXT REFERENCES markets(id),
    group_id TEXT,                          -- Groups mutually exclusive markets together
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(parent_market_id, child_market_id, relationship_type)
);

-- Order book snapshots
CREATE TABLE order_book_snapshots (
    id SERIAL PRIMARY KEY,
    market_id TEXT REFERENCES markets(id),
    outcome_index INTEGER,                  -- 0 for first outcome, 1 for second, etc.
    timestamp TIMESTAMP DEFAULT NOW(),
    best_bid DECIMAL,
    best_ask DECIMAL,
    spread DECIMAL,
    spread_pct DECIMAL,
    bid_depth_1pct DECIMAL,                 -- Total $ within 1% of best bid
    ask_depth_1pct DECIMAL,                 -- Total $ within 1% of best ask
    bid_depth_5pct DECIMAL,                 -- Total $ within 5% of best bid
    ask_depth_5pct DECIMAL,                 -- Total $ within 5% of best ask
    imbalance DECIMAL,                      -- (bid_depth - ask_depth) / (bid_depth + ask_depth)
    full_book JSONB                         -- Store complete book for detailed analysis
);

-- Index for fast time-series queries
CREATE INDEX idx_book_snapshots_market_time ON order_book_snapshots(market_id, timestamp DESC);

-- Trade history
CREATE TABLE trades (
    id TEXT PRIMARY KEY,                    -- Trade ID from API
    market_id TEXT REFERENCES markets(id),
    outcome_index INTEGER,
    price DECIMAL NOT NULL,
    size DECIMAL NOT NULL,                  -- Dollar amount
    side TEXT,                              -- 'buy' or 'sell'
    timestamp TIMESTAMP NOT NULL,
    maker_address TEXT,
    taker_address TEXT
);

CREATE INDEX idx_trades_market_time ON trades(market_id, timestamp DESC);

-- Pre-calculated volume aggregates (updated periodically)
CREATE TABLE volume_stats (
    id SERIAL PRIMARY KEY,
    market_id TEXT REFERENCES markets(id),
    period_start TIMESTAMP,
    period_end TIMESTAMP,
    period_type TEXT,                       -- 'hour', 'day', 'week'
    volume DECIMAL,
    trade_count INTEGER,
    avg_trade_size DECIMAL,
    price_open DECIMAL,
    price_close DECIMAL,
    price_high DECIMAL,
    price_low DECIMAL,
    UNIQUE(market_id, period_start, period_type)
);

CREATE INDEX idx_volume_stats_market ON volume_stats(market_id, period_type, period_start DESC);

-- Alerts generated by the system
CREATE TABLE alerts (
    id SERIAL PRIMARY KEY,
    alert_type TEXT NOT NULL,               -- 'arbitrage', 'volume_spike', 'spread_widening', 'mm_pullback'
    market_id TEXT REFERENCES markets(id),
    related_market_ids TEXT[],              -- For arbitrage involving multiple markets
    severity TEXT,                          -- 'info', 'medium', 'high'
    title TEXT NOT NULL,
    description TEXT,
    data JSONB,                             -- Detailed data for the alert
    created_at TIMESTAMP DEFAULT NOW(),
    dismissed BOOLEAN DEFAULT FALSE,
    dismissed_at TIMESTAMP
);

CREATE INDEX idx_alerts_type_time ON alerts(alert_type, created_at DESC);
CREATE INDEX idx_alerts_active ON alerts(dismissed, created_at DESC);
```

---

## Module 1: Cross-Market Arbitrage Detection

### Purpose
Find markets that are logically connected but whose prices don't add up correctly, creating risk-free profit opportunities.

### Arbitrage Types

#### Type A: Mutually Exclusive Outcomes
Markets where exactly one outcome must happen. All YES prices should sum to 100%.

**Example:**
- "Trump wins" = 52¢
- "Biden wins" = 44¢
- "Other wins" = 6¢
- Total = 102¢ → SHORT all three, guaranteed 2¢ profit

**Detection Logic:**
```
For each group of mutually exclusive markets:
    sum_of_yes_prices = sum(market.yes_price for market in group)

    if sum_of_yes_prices > 1.00 + FEE_THRESHOLD:
        profit = sum_of_yes_prices - 1.00 - total_fees
        if profit > 0:
            create_alert(
                type="arbitrage_short_all",
                description=f"Short all outcomes for {profit:.1%} profit",
                markets=group,
                expected_profit=profit
            )

    if sum_of_yes_prices < 1.00 - FEE_TD:
        profit = 1.00 - sum_of_yes_prices - total_fees
        if profit > 0:
            create_alert(
                type="arbitrage_long_all",
                description=f"Buy all outcomes for {profit:.1%} profit",
                markets=group,
                expected_profit=profit
            )
```

#### Type B: Conditional Markets
When one outcome requires another to happen first.

**Example:**
- "Democrats win presidency" = 45¢
- "Harris is president Jan 20" = 47¢
- INVALID: Harris requires Democrat win, so can't be higher

**Detection Logic:**
```
For each conditional relationship (child depends on parent):
    if child.price > parent.price + THRESHOLD:
        create_alert(
            type="arbitrage_conditional",
            description="Child market exceeds parent - short child, long parent",
            parent_market=parent,
            child_market=child,
            price_difference=child.price - parent.price
        )
```

#### Type C: Time Sequence Markets
Same event with different deadlines. Later dates must be >= earlier dates.

**Example:**
- "BTC > $100k by March" = 35¢
- "BTC > $100k by June" = 30¢  ← INVALID: should be higher
- "BTC > $100k by December" = 50¢

**Detection Logic:**
```
For each time sequence group (sorted by date ascending):
    for i in range(len(markets) - 1):
        earlier = markets[i]
        later = markets[i + 1]

        if earlier.price > later.price + THRESHOLD:
            create_alert(
                type="arbitrage_time_inversion",
                description="Earlier deadline priced higher than later",
                earlier_market=earlier,
                later_market=later,
                inversion_amount=earlier.price - later.price
            )
```

#### Type D: Subset Relationships
Specific outcomes vs. general category.

**Example:**
- "Any tech CEO testifies in 2025" = 40¢
- "Zuckerberg testifies in 2025" = 45¢ ← INVALID: specific > general

**Detection Logic:**
```
For each subset relationship (specific is subset of general):
    if specific.price > general.price + THRESHOLD:
        create_alert(
            type="arbitrage_subset",
            description="Specific outcome exceeds general category",
            general_market=general,
            specific_market=specific
        )
```

### Configuration

```python
ARBITRAGE_CONFIG = {
    "fee_per_trade": 0.01,          # 1% fee assumption (adjust based on actual fees)
    "min_profit_threshold": 0.02,    # Only alert if profit > 2% after fees
    "min_liquidity": 1000,           # Only alert if at least $1000 available at these prices
    "check_interval_seconds": 60,    # How often to scan
}
```

### Identifying Related Markets

This is the hardest part. Options:

1. **Manual tagging** - Build an admin interface to tag relationships
2. **Keyword matching** - Group markets with similar titles
3. **Category-based** - Assume markets in same category may be related
4. **LLM-assisted** - Send market titles to Claude API to identify relationships

Start with manual tagging + simple keyword matching. Add LLM later.

```python
def find_potential_relationships(markets):
    """Group markets that might be related based on title similarity."""

    groups = []

    # Group by similar titles (e.g., all presidential election markets)
    for market in markets:
        title_words = extract_keywords(market.question)

        # Check if fits existing group
        matched = False
        for group in groups:
            if similarity(title_words, group.keywords) > 0.7:
                group.markets.append(market)
                matched = True
                break

        if not matched:
            groups.append(MarketGroup(keywords=title_words, markets=[market]))

    # Flag groups for human review
    return [g for g in groups if len(g.markets) > 1]
```

### Output

Dashboard showing:
- Active arbitrage opportunities with expected profit
- Amount of liquidity available at arbitrage prices
- Quick action: links to markets on Polymarket
- History of past arbitrage opportunities (did they resolve correctly?)

---

## Module 2: Order Book Analysis

### Purpose
Analyze the full order book to find trading opportunities invisible in the simple price display.

### Metrics to Calculate

#### 2.1 Bid-Ask Spread

```python
def calculate_spread(order_book):
    best_bid = order_book.bids[0].price if order_book.bids else 0
    best_ask = order_book.asks[0].price if order_book.asks else 1

    spread = best_ask - best_bid
    midpoint = (best_ask + best_bid) / 2
    spread_pct = (spread / midpoint) * 100 if midpoint > 0 else 0

    return {
        "best_bid": best_bid,
        "best_ask": best_ask,
        "spread": spread,
        "spread_pct": spread_pct,
        "midpoint": midpoint
    }
```

**Interpretation:**
- Spread > 5% = Wide, good for market making
- Spread 2-5% = Moderate
- Spread < 2% = Tight, competitive market

#### 2.2 Depth Analysis

```python
def calculate_depth(order_book, price_range_pct=0.05):
    """Calculate total liquidity within X% of best price."""

    best_bid = order_book.bids[0].price if order_book.bids else 0
    best_ask = order_book.asks[0].price if order_book.asks else 1

    # Sum all bids within range
    bid_depth = sum(
        level.size
        for level in order_book.bids
        if level.price >= best_bid * (1 - price_range_pct)
    )

    # Sum all asks within range
    ask_depth = sum(
        level.size
        for level in order_book.asks
        if level.price <= best_ask * (1 + price_range_pct)
    )

    return {
        "bid_depth": bid_depth,
        "ask_depth": ask_depth,
        "total_depth": bid_depth + ask_depth
    }
```

#### 2.3 Book Imbalance

```python
def calculate_imbalance(bid_depth, ask_depth):
    """
    Returns value from -1 to +1
    Positive = more bids = buying pressure
    Negative = more asks = selling pressure
    """
    total = bid_depth + ask_depth
    if total == 0:
        return 0
    return (bid_depth - ask_depth) / total
```

**Interpretation:**
- Imbalance > 0.3 = Strong buying pressure, price may rise
- Imbalance < -0.3 = Strong selling pressure, price may fall
- Near 0 = Balanced

#### 2.4 Slippage Calculator

```python
def calculate_slippage(order_book, trade_size, side):
    """
    Calculate average execution price and slippage for a given trade size.

    Args:
        order_book: Current order book
        trade_size: Dollar amount to trade
        side: 'buy' or 'sell'

    Returns:
        dict with average_price, slippage, levels_consumed
    """
    levels = order_book.asks if side == 'buy' else order_book.bids

    # Sort: best prices first
    if side == 'buy':
        levels = sorted(levels, key=lambda x: x.price)  # Lowest ask first
    else:
        levels = sorted(levels, key=lambda x: x.price, reverse=True)  # Highest bid first

    remaining = trade_size
    total_cost = 0
    levels_consumed = 0

    for level in levels:
        if remaining <= 0:
            break

        fill_amount = min(level.size, remaining)
        total_cost += fill_amount * level.price
        remaining -= fill_amount
        levels_consumed += 1

    if remaining > 0:
        # Not enough liquidity
        return {
            "error": "Insufficient liquidity",
            "available": trade_size - remaining,
            "shortfall": remaining
        }

    average_price = total_cost / trade_size
    best_price = levels[0].price
    slippage = abs(average_price - best_price)
    slippage_pct = (slippage / best_price) * 100

    return {
        "average_price": average_price,
        "best_price": best_price,
        "slippage": slippage,
        "slippage_pct": slippage_pct,
        "levels_consumed": levels_consumed,
        "total_cost": total_cost
    }
```

#### 2.5 Spread History Tracking

Store snapshots over time to identify patterns:

```python
def analyze_spread_patterns(market_id, hours=24):
    """Analyze spread patterns over time."""

    snapshots = db.query("""
        SELECT
            timestamp,
            spread_pct,
            EXTRACT(HOUR FROM timestamp) as hour
        FROM order_book_snapshots
        WHERE market_id = %s
        AND timestamp > NOW() - INTERVAL '%s hours'
        ORDER BY timestamp
    """, [market_id, hours])

    # Calculate average spread by hour
    hourly_spreads = {}
    for snap in snapshots:
        hour = snap.hour
        if hour not in hourly_spreads:
            hourly_spreads[hour] = []
        hourly_spreads[hour].append(snap.spread_pct)

    avg_by_hour = {
        hour: sum(spreads) / len(spreads)
        for hour, spreads in hourly_spreads.items()
    }

    # Find best/worst times to trade
    best_hour = min(avg_by_hour, key=avg_by_hour.get)
    worst_hour = max(avg_by_hour, key=avg_by_hour.get)

    return {
        "avg_spread_by_hour": avg_by_hour,
        "best_time_to_trade": best_hour,
        "worst_time_to_trade": worst_hour,
        "current_spread_vs_avg": calculate_current_vs_average(snapshots)
    }
```

### Configuration

```python
ORDER_BOOK_CONFIG = {
    "snapshot_interval_seconds": 30,
    "depth_ranges": [0.01, 0.05, 0.10],  # Calculate depth at 1%, 5%, 10% from best
    "spread_alert_threshold": 0.05,       # Alert if spread > 5%
    "imbalance_alert_threshold": 0.4,     # Alert if imbalance > 40%
}
```

### Output

For each market:
- Current spread (¢ and %)
- Depth chart: visual bar chart showing $ at each price level
- Imbalance indicator with arrow (↑ buying pressure, ↓ selling pressure)
- Slippage table: "To trade $100 / $500 / $1000 / $5000, your slippage is X"
- Best time to trade (based on historical spread patterns)
- Alert when spread is unusually wide or tight vs. history

---

## Module 3: Volume Anomaly Detection

### Purpose
Identify unusual trading activity that may signal informed trading or upcoming price moves.

### Metrics to Calculate

#### 3.1 Volume vs. Baseline

```python
def calculate_volume_ratio(market_id, lookback_hours=1):
    """Compare recent volume to historical baseline."""

    # Recent volume
    recent_volume = db.query_scalar("""
        SELECT COALESCE(SUM(size), 0)
        FROM trades
        WHERE market_id = %s
        AND timestamp > NOW() - INTERVAL '%s hours'
    """, [market_id, lookback_hours])

    # Baseline: same hour window, averaged over past 7 days
    baseline_volume = db.query_scalar("""
        SELECT COALESCE(AVG(period_volume), 0)
        FROM (
            SELECT DATE(timestamp), SUM(size) as period_volume
            FROM trades
            WHERE market_id = %s
            AND timestamp > NOW() - INTERVAL '7 days'
            AND EXTRACT(HOUR FROM timestamp) = EXTRACT(HOUR FROM NOW())
            GROUP BY DATE(timestamp)
        ) daily
    """, [market_id])

    if baseline_volume == 0:
        baseline_volume = 1  # Avoid division by zero

    volume_ratio = recent_volume / baseline_volume

    return {
        "recent_volume": recent_volume,
        "baseline_volume": baseline_volume,
        "volume_ratio": volume_ratio,
        "is_anomaly": volume_ratio > 2.0
    }
```

#### 3.2 Volume Acceleration

```python
def calculate_volume_acceleration(market_id):
    """Is volume increasing or decreasing?"""

    # Volume in last hour
    volume_current = db.query_scalar("""
        SELECT COALESCE(SUM(size), 0)
        FROM trades
        WHERE market_id = %s
        AND timestamp > NOW() - INTERVAL '1 hour'
    """, [market_id])

    # Volume in hour before that
    volume_previous = db.query_scalar("""
        SELECT COALESCE(SUM(size), 0)
        FROM trades
        WHERE market_id = %s
        AND timestamp BETWEEN NOW() - INTERVAL '2 hours' AND NOW() - INTERVAL '1 hour'
    """, [market_id])

    if volume_previous == 0:
        acceleration = volume_current  # Treat as infinite acceleration
    else:
        acceleration = (volume_current - volume_previous) / volume_previous

    return {
        "volume_current_hour": volume_current,
        "volume_previous_hour": volume_previous,
        "acceleration": acceleration,
        "accelerating": acceleration > 0.5  # 50% increase
    }
```

#### 3.3 Volume vs. Price Movement

```python
def analyze_volume_price_relationship(market_id, hours=1):
    """Check if volume is moving price or being absorbed."""

    # Get volume
    volume = db.query_scalar("""
        SELECT COALESCE(SUM(size), 0)
        FROM trades
        WHERE market_id = %s
        AND timestamp > NOW() - INTERVAL '%s hours'
    """, [market_id, hours])

    # Get price change
    prices = db.query("""
        SELECT price, timestamp
        FROM trades
        WHERE market_id = %s
        AND timestamp > NOW() - INTERVAL '%s hours'
        ORDER BY timestamp
    """, [market_id, hours])

    if len(prices) < 2:
        return {"insufficient_data": True}

    price_start = prices[0].price
    price_end = prices[-1].price
    price_change = abs(price_end - price_start)
    price_change_pct = (price_change / price_start) * 100 if price_start > 0 else 0

    # Calculate baseline for comparison
    baseline = calculate_volume_ratio(market_id, hours)

    return {
        "volume": volume,
        "volume_ratio": baseline["volume_ratio"],
        "price_change": price_change,
        "price_change_pct": price_change_pct,
        "high_volume_low_movement": baseline["volume_ratio"] > 2 and price_change_pct < 1,
        "interpretation": interpret_volume_price(baseline["volume_ratio"], price_change_pct)
    }

def interpret_volume_price(volume_ratio, price_change_pct):
    if volume_ratio > 2 and price_change_pct > 3:
        return "High volume driving price - likely informed trading"
    elif volume_ratio > 2 and price_change_pct < 1:
        return "High volume absorbed - two sides disagreeing, watch for breakout"
    elif volume_ratio < 0.5 and price_change_pct > 2:
        return "Price moving on low volume - may be unstable"
    else:
        return "Normal activity"
```

#### 3.4 Trade Size Distribution

```python
def analyze_trade_sizes(market_id, hours=24):
    """Look for unusual trade sizes that might indicate whale activity."""

    trades = db.query("""
        SELECT size, timestamp
        FROM trades
        WHERE market_id = %s
        AND timestamp > NOW() - INTERVAL '%s hours'
        ORDER BY size DESC
    """, [market_id, hours])

    if not trades:
        return {"insufficient_data": True}

    sizes = [t.size for t in trades]

    avg_size = sum(sizes) / len(sizes)
    median_size = sorted(sizes)[len(sizes) // 2]
    max_size = max(sizes)

    # Find trades > 5x average (potential whale activity)
    large_trades = [t for t in trades if t.size > avg_size * 5]

    return {
        "trade_count": len(trades),
        "average_size": avg_size,
        "median_size": median_size,
        "max_size": max_size,
        "large_trades": large_trades,
        "whale_activity": len(large_trades) > 0
    }
```

### Alert Logic

```python
def check_volume_alerts(market_id):
    """Run all volume checks and generate alerts."""

    alerts = []

    # Check volume ratio
    volume = calculate_volume_ratio(market_id)
    if volume["volume_ratio"] > 3:
        alerts.append({
            "type": "volume_spike",
            "severity": "high" if volume["volume_ratio"] > 5 else "medium",
            "title": f"Volume {volume['volume_ratio']:.1f}x normal",
            "data": volume
        })

    # Check acceleration
    accel = calculate_volume_acceleration(market_id)
    if accel["acceleration"] > 1.0:
        alerts.append({
            "type": "volume_accelerating",
            "severity": "medium",
            "title": f"Volume doubled vs previous hour",
            "data": accel
        })

    # Check volume/price relationship
    vol_price = analyze_volume_price_relationship(market_id)
    if vol_price.get("high_volume_low_movement"):
        alerts.append({
            "type": "volume_absorption",
            "severity": "high",
            "title": "High volume being absorbed - watch for breakout",
            "data": vol_price
        })

    # Check for whale activity
    sizes = analyze_trade_sizes(market_id)
    if sizes.get("whale_activity"):
        alerts.append({
            "type": "whale_trade",
            "severity": "medium",
            "title": f"Large trade detected: ${sizes['max_size']:.0f}",
            "data": sizes
        })

    return alerts
```

### Configuration

```python
VOLUME_CONFIG = {
    "check_interval_seconds": 300,          # Check every 5 minutes
    "baseline_days": 7,                     # Compare to 7-day average
    "volume_spike_threshold": 3.0,          # Alert if 3x normal
    "acceleration_threshold": 0.5,          # Alert if 50% increase
    "whale_threshold_multiplier": 5,        # Trades > 5x average = whale
    "min_trades_for_analysis": 10,          # Need at least 10 trades
}
```

### Output

- Volume chart over time with anomaly highlights (spikes marked)
- Alert feed showing recent volume anomalies
- Market ranking by unusual activity
- Correlation analysis: "Markets with volume spikes that preceded price moves"

---

## Module 4: Market Maker Activity Patterns

### Purpose
Understand when and how market makers provide liquidity. Use this to:
- Know when liquidity will be available
- Identify when MMs are nervous (pulling back)
- Find opportunities when MMs step away

### Patterns to Detect

#### 4.1 Spread Timeline Analysis

```python
def analyze_spread_timeline(market_id, hours=48):
    """Track how spread changes over time."""

    snapshots = db.query("""
        SELECT
            timestamp,
            spread_pct,
            bid_depth_1pct,
            ask_depth_1pct
        FROM order_book_snapshots
        WHERE market_id = %s
        AND timestamp > NOW() - INTERVAL '%s hours'
        ORDER BY timestamp
    """, [market_id, hours])

    # Group by hour of day
    by_hour = {}
    for snap in snapshots:
        hour = snap.timestamp.hour
        if hour not in by_hour:
            by_hour[hour] = []
        by_hour[hour].append({
            "spread": snap.spread_pct,
            "depth": snap.bid_depth_1pct + snap.ask_depth_1pct
        })

    # Calculate averages
    hourly_stats = {}
    for hour, data in by_hour.items():
        hourly_stats[hour] = {
            "avg_spread": sum(d["spread"] for d in data) / len(data),
            "avg_depth": sum(d["depth"] for d in data) / len(data),
            "sample_count": len(data)
        }

    # Identify MM active vs inactive periods
    avg_spread_overall = sum(h["avg_spread"] for h in hourly_stats.values()) / len(hourly_stats)

    mm_active_hours = [h for h, stats in hourly_stats.items() if stats["avg_spread"] < avg_spread_overall * 0.8]
    mm_inactive_hours = [h for h, stats in hourly_stats.items() if stats["avg_spread"] > avg_spread_overall * 1.2]

    return {
        "hourly_stats": hourly_stats,
        "mm_active_hours": sorted(mm_active_hours),
        "mm_inactive_hours": sorted(mm_inactive_hours),
        "best_trading_hours": mm_active_hours,
        "worst_trading_hours": mm_inactive_hours
    }
```

#### 4.2 Liquidity Provider Detection

```python
def detect_mm_behavior(market_id, minutes=30):
    """Identify market maker patterns from order book changes."""

    # Get recent book snapshots
    snapshots = db.query("""
        SELECT timestamp, full_book
        FROM order_book_snapshots
        WHERE market_id = %s
        AND timestamp > NOW() - INTERVAL '%s minutes'
        ORDER BY timestamp
    """, [market_id, minutes])

    if len(snapshots) < 2:
        return {"insufficient_data": True}

    patterns = {
        "symmetric_orders": 0,      # Same size on bid and ask
        "quick_refreshes": 0,       # Orders replaced quickly after fills
        "consistent_spread": 0,     # Spread maintained over time
    }

    for i in range(1, len(snapshots)):
        prev_book = snapshots[i-1].full_book
        curr_book = snapshots[i].full_book

        # Check for symmetric orders
        if prev_book and curr_book:
            prev_bid_sizes = [l["size"] for l in prev_book.get("bids", [])[:3]]
            prev_ask_sizes = [l["size"] for l in prev_book.get("asks", [])[:3]]

            # If top bid and ask sizes are within 20% of each other
            if prev_bid_sizes and prev_ask_sizes:
                top_bid = prev_bid_sizes[0]
                top_ask = prev_ask_sizes[0]
                if abs(top_bid - top_ask) / max(top_bid, top_ask) < 0.2:
                    patterns["symmetric_orders"] += 1

    total_checks = len(snapshots) - 1

    return {
        "symmetric_order_rate": patterns["symmetric_orders"] / total_checks if total_checks > 0 else 0,
        "mm_presence_score": calculate_mm_presence_score(patterns, total_checks),
        "interpretation": interpret_mm_patterns(patterns, total_checks)
    }

def calculate_mm_presence_score(patterns, total_checks):
    """Score from 0-100 indicating likely MM presence."""
    if total_checks == 0:
        return 0

    symmetric_score = (patterns["symmetric_orders"] / total_checks) * 50
    # Add other factors...

    return min(100, symmetric_score)

def interpret_mm_patterns(patterns, total_checks):
    score = calculate_mm_presence_score(patterns, total_checks)

    if score > 70:
        return "Strong MM presence - tight spreads, good liquidity expected"
    elif score > 40:
        return "Moderate MM presence - reasonable liquidity"
    else:
        return "Low MM presence - spreads may be wide, price can move easily"
```

#### 4.3 MM Pullback Detection

```python
def detect_mm_pullback(market_id):
    """Detect when market makers are pulling back."""

    # Compare recent spread to historical
    recent_spread = db.query_scalar("""
        SELECT AVG(spread_pct)
        FROM order_book_snapshots
        WHERE market_id = %s
        AND timestamp > NOW() - INTERVAL '1 hour'
    """, [market_id])

    historical_spread = db.query_scalar("""
        SELECT AVG(spread_pct)
        FROM order_book_snapshots
        WHERE market_id = %s
        AND timestamp BETWEEN NOW() - INTERVAL '7 days' AND NOW() - INTERVAL '1 hour'
    """, [market_id])

    if historical_spread is None or historical_spread == 0:
        return {"insufficient_data": True}

    spread_ratio = recent_spread / historical_spread

    # Compare recent depth to historical
    recent_depth = db.query_scalar("""
        SELECT AVG(bid_depth_1pct + ask_depth_1pct)
        FROM order_book_snapshots
        WHERE market_id = %s
        AND timestamp > NOW() - INTERVAL '1 hour'
    """, [market_id])

    historical_depth = db.query_scalar("""
        SELECT AVG(bid_depth_1pct + ask_depth_1pct)
        FROM order_book_snapshots
        WHERE market_id = %s
        AND timestamp BETWEEN NOW() - INTERVAL '7 days' AND NOW() - INTERVAL '1 hour'
    """, [market_id])

    depth_ratio = recent_depth / historical_depth if historical_depth else 1

    pullback_detected = spread_ratio > 1.5 or depth_ratio < 0.5

    return {
        "recent_spread": recent_spread,
        "historical_spread": historical_spread,
        "spread_ratio": spread_ratio,
        "recent_depth": recent_depth,
        "historical_depth": historical_depth,
        "depth_ratio": depth_ratio,
        "pullback_detected": pullback_detected,
        "interpretation": "MMs pulling back - expect volatility" if pullback_detected else "Normal MM activity"
    }
```

### Configuration

```python
MM_CONFIG = {
    "snapshot_interval_seconds": 30,
    "analysis_window_minutes": 30,
    "spread_widening_threshold": 1.5,    # Alert if spread 1.5x normal
    "depth_reduction_threshold": 0.5,     # Alert if depth drops to 50% of normal
    "symmetric_order_threshold": 0.2,     # Orders within 20% = symmetric
}
```

### Output

- MM presence indicator for each market (HIGH / MEDIUM / LOW)
- Best trading hours chart based on spread history
- Alert when MMs appear to be pulling back
- Spread timeline visualization

---

## System Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                               │
│  (Web Dashboard - can be simple HTML/JS or React)                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │  Arbitrage  │  │ Order Book  │  │   Volume    │  │     MM      │ │
│  │  Dashboard  │  │  Dashboard  │  │  Dashboard  │  │  Dashboard  │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                       ANALYSIS ENGINE                                │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐           │
│  │ Arbitrage │ │Order Book │ │  Volume   │ │    MM     │           │
│  │ Detector  │ │ Analyzer  │ │ Analyzer  │ │ Analyzer  │           │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘           │
├─────────────────────────────────────────────────────────────────────┤
│                       SCHEDULER / JOBS                               │
│  - Data collection: every 30s-1min                                  │
│  - Analysis runs: every 5 min                                       │
│  - Aggregation jobs: every hour                                     │
├─────────────────────────────────────────────────────────────────────┤
│                         API CLIENTS                                  │
│  ┌─────────────────┐    ┌─────────────────┐                         │
│  │   Gamma API     │    │    CLOB API     │                         │
│  │   (metadata)    │    │  (books/trades) │                         │
│  └─────────────────┘    └─────────────────┘                         │
├─────────────────────────────────────────────────────────────────────┤
│                         DATABASE                                     │
│  PostgreSQL: markets, relationships, snapshots, trades, alerts      │
└─────────────────────────────────────────────────────────────────────┘
```

### Technology Stack (Recommended)

```
Backend:
- Python 3.11+
- FastAPI (REST API framework)
- SQLAlchemy (database ORM)
- APScheduler (job scheduling)
- httpx (async HTTP client for API calls)

Database:
- PostgreSQL 15+ (production)
- SQLite (development/testing)

Frontend (simple option):
- HTML + Tailwind CSS + Alpine.js
- Charts: Chart.js or Plotly

Frontend (more interactive option):
- React + TypeScript
- Charts: Recharts or TradingView lightweight charts
```

### File Structure

```
polymarket-analyzer/
├── README.md
├── requirements.txt
├── .env.example
├── config.py                    # Configuration management
│
├── src/
│   ├── __init__.py
│   │
│   ├── api/                     # FastAPI routes
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app
│   │   ├── routes/
│   │   │   ├── markets.py
│   │   │   ├── arbitrage.py
│   │   │   ├── orderbook.py
│   │   │   ├── volume.py
│   │   │   ├── mm.py
│   │   │   └── alerts.py
│   │   └── schemas.py           # Pydantic models
│   │
│   ├── collectors/              # Data collection
│   │   ├── __init__.py
│   │   ├── base.py              # Base collector class
│   │   ├── gamma.py             # Gamma API client
│   │   ├── clob.py              # CLOB API client
│   │   └── scheduler.py         # Job scheduler
│   │
│   ├── analyzers/               # Analysis modules
│   │   ├── __init__.py
│   │   ├── arbitrage.py         # Module 1
│   │   ├── orderbook.py         # Module 2
│   │   ├── volume.py            # Module 3
│   │   └── mm_patterns.py       # Module 4
│   │
│   ├── db/                      # Database
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── models.py
│   │   └── helpers.py
│
├── frontend/                    # Web dashboard
│   ├── index.html
│   ├── css/
│   └── js/
│
├── scripts/
│   ├── init_db.py               # Database setup
│   ├── backfill.py              # Historical data backfill
│   └── test_apis.py             # API connectivity test
│
└── tests/
    ├── test_collectors.py
    ├── test_analyzers.py
    └── test_api.py
```

### API Client Implementation

```python
# src/collectors/gamma.py

import httpx
from typing import List, Optional
import asyncio

class GammaClient:
    """Client for Polymarket Gamma API."""

    BASE_URL = "https://gamma-api.polymarket.com"

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_markets(self, limit: int = 100, offset: int = 0) -> List[dict]:
        """Fetch list of markets."""
        response = await self.client.get(
            f"{self.BASE_URL}/markets",
            params={"limit": limit, "offset": offset}
        )
        response.raise_for_status()
        return response.json()

    async def get_market(self, market_id: str) -> dict:
        """Fetch single market details."""
        response = await self.client.get(f"{self.BASE_URL}/markets/{market_id}")
        response.raise_for_status()
        return response.json()

    async def get_all_markets(self) -> List[dict]:
        """Fetch all active markets with pagination."""
        all_markets = []
        offset = 0
        limit = 100

        while True:
            markets = await self.get_markets(limit=limit, offset=offset)
            if not markets:
                break
            all_markets.extend(markets)
            offset += limit
            await asyncio.sleep(0.5)  # Rate limiting

        return all_markets

    async def close(self):
        await self.client.aclose()


# src/collectors/clob.py

class CLOBClient:
    """Client for Polymarket CLOB API."""

    BASE_URL = "https://clob.polymarket.com"

    def __init__(self, api_key: Optional[str] = None):
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self.client = httpx.AsyncClient(timeout=30.0, headers=headers)

    async def get_order_book(self, token_id: str) -> dict:
        """Fetch order book for a token."""
        response = await self.client.get(
            f"{self.BASE_URL}/book",
            params={"token_id": token_id}
        )
        response.raise_for_status()
        return response.json()

    async def get_trades(self, token_id: str, limit: int = 100) -> List[dict]:
        """Fetch recent trades."""
        response = await self.client.get(
            f"{self.BASE_URL}/trades",
            params={"token_id": token_id, "limit": limit}
        )
        response.raise_for_status()
        return response.json()

    async def get_price(self, token_id: str) -> dict:
        """Fetch current price."""
        response = await self.client.get(
            f"{self.BASE_URL}/price",
            params={"token_id": token_id}
        )
        response.raise_for_status()
        return response.json()

    async def close(self):
        await self.client.aclose()
```

### Scheduler Implementation

```python
# src/collectors/scheduler.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging

logger = logging.getLogger(__name__)

class DataScheduler:
    """Manages scheduled data collection and analysis jobs."""

    def __init__(self, db, gamma_client, clob_client, analyzers):
        self.db = db
        self.gamma = gamma_client
        self.clob = clob_client
        self.analyzers = analyzers
        self.scheduler = AsyncIOScheduler()

    def setup_jobs(self):
        """Configure all scheduled jobs."""

        # Sync market list every 15 minutes
        self.scheduler.add_job(
            self.sync_markets,
            IntervalTrigger(minutes=15),
            id="sync_markets",
            name="Sync market list from Gamma API"
        )

        # Collect order book snapshots every 30 seconds
        self.scheduler.add_job(
            self.collect_order_books,
            IntervalTrigger(seconds=30),
            id="collect_order_books",
            name="Snapshot order books"
        )

        # Collect trades every minute
        self.scheduler.add_job(
            self.collect_trades,
            IntervalTrigger(minutes=1),
            id="collect_trades",
            name="Collect recent trades"
        )

        # Run analysis every 5 minutes
        self.scheduler.add_job(
            self.run_analysis,
            IntervalTrigger(minutes=5),
            id="run_analysis",
            name="Run all analyzers"
        )

        # Aggregate volume stats every hour
        self.scheduler.add_job(
            self.aggregate_stats,
            IntervalTrigger(hours=1),
            id="aggregate_stats",
            name="Calculate hourly aggregates"
        )

        # Cleanup old data daily
        self.scheduler.add_job(
            self.cleanup_old_data,
            IntervalTrigger(days=1),
            id="cleanup",
            name="Remove data older than 30 days"
        )

    async def sync_markets(self):
        """Fetch and update market list."""
        logger.info("Syncing markets...")
        try:
            markets = await self.gamma.get_all_markets()
            await self.db.upsert_markets(markets)
            logger.info(f"Synced {len(markets)} markets")
        except Exception as e:
            logger.error(f"Market sync failed: {e}")

    async def collect_order_books(self):
        """Snapshot order books for all active markets."""
        markets = await self.db.get_active_markets()

        for market in markets:
            try:
                for token_id in market.token_ids:
                    book = await self.clob.get_order_book(token_id)
                    await self.db.save_order_book_snapshot(market.id, token_id, book)
            except Exception as e:
                logger.error(f"Order book collection failed for {market.id}: {e}")

    async def collect_trades(self):
        """Collect recent trades for all active markets."""
        markets = await self.db.get_active_markets()

        for market in markets:
            try:
                for token_id in market.token_ids:
                    trades = await self.clob.get_trades(token_id)
                    await self.db.save_trades(market.id, token_id, trades)
            except Exception as e:
                logger.error(f"Trade collection failed for {market.id}: {e}")

    async def run_analysis(self):
        """Run all analysis modules."""
        logger.info("Running analysis...")

        markets = await self.db.get_active_markets()

        # Run arbitrage detection
        arb_alerts = await self.analyzers.arbitrage.detect_all()

        # Run per-market analysis
        for market in markets:
            try:
                # Order book analysis
                book_alerts = await self.analyzers.orderbook.analyze(market.id)

                # Volume analysis
                vol_alerts = await self.analyzers.volume.analyze(market.id)

                # MM pattern analysis
                mm_alerts = await self.analyzers.mm.analyze(market.id)

                # Save all alerts
                all_alerts = book_alerts + vol_alerts + mm_alerts
                for alert in all_alerts:
                    await self.db.save_alert(market.id, alert)

            except Exception as e:
                logger.error(f"Analysis failed for {market.id}: {e}")

        # Save arbitrage alerts (cross-market)
        for alert in arb_alerts:
            await self.db.save_alert(None, alert)

        logger.info("Analysis complete")

    async def aggregate_stats(self):
        """Calculate hourly volume aggregates."""
        await self.db.calculate_volume_aggregates()

    async def cleanup_old_data(self):
        """Remove old snapshots and trades to save space."""
        await self.db.delete_old_data(days=30)

    def start(self):
        self.scheduler.start()

    def stop(self):
        self.scheduler.shutdown()
```

### Main Entry Point

```python
# src/api/main.py

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging

from src.db.database import Database
from src.collectors.gamma import GammaClient
from src.collectors.clob import CLOBClient
from src.collectors.scheduler import DataScheduler
from src.analyzers import ArbitrageAnalyzer, OrderBookAnalyzer, VolumeAnalyzer, MMAnalyzer
from src.api.routes import markets, arbitrage, orderbook, volume, mm, alerts
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global instances
db = None
scheduler = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    global db, scheduler

    # Startup
    logger.info("Starting Polymarket Analyzer...")

    # Initialize database
    db = Database(settings.DATABASE_URL)
    await db.connect()

    # Initialize API clients
    gamma = GammaClient()
    clob = CLOBClient(api_key=settings.CLOB_API_KEY)

    # Initialize analyzers
    analyzers = type('Analyzers', (), {
        'arbitrage': ArbitrageAnalyzer(db),
        'orderbook': OrderBookAnalyzer(db),
        'volume': VolumeAnalyzer(db),
        'mm': MMAnalyzer(db)
    })()

    # Initialize and start scheduler
    scheduler = DataScheduler(db, gamma, clob, analyzers)
    scheduler.setup_jobs()
    scheduler.start()

    # Initial data sync
    await scheduler.sync_markets()

    logger.info("Startup complete")

    yield

    # Shutdown
    logger.info("Shutting down...")
    scheduler.stop()
    await gamma.close()
    await clob.close()
    await db.disconnect()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Polymarket Analyzer",
    description="Analysis tool for Polymarket trading opportunities",
    version="1.0.0",
    lifespan=lifespan
)

# Include routers
app.include_router(markets.router, prefix="/api/markets", tags=["Markets"])
app.include_router(arbitrage.router, prefix="/api/arbitrage", tags=["Arbitrage"])
app.include_router(orderbook.router, prefix="/api/orderbook", tags=["Order Book"])
app.include_router(volume.router, prefix="/api/volume", tags=["Volume"])
app.include_router(mm.router, prefix="/api/mm", tags=["Market Makers"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["Alerts"])

# Serve frontend
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Configuration

```python
# config.py

from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://localhost/polymarket"

    # API Keys (optional, for higher rate limits)
    CLOB_API_KEY: Optional[str] = None

    # Collection intervals (seconds)
    MARKET_SYNC_INTERVAL: int = 900          # 15 minutes
    ORDER_BOOK_INTERVAL: int = 30            # 30 seconds
    TRADE_COLLECTION_INTERVAL: int = 60      # 1 minute
    ANALYSIS_INTERVAL: int = 300             # 5 minutes

    # Analysis thresholds
    ARB_MIN_PROFIT_THRESHOLD: float = 0.02   # 2%
    ARB_FEE_PER_TRADE: float = 0.01          # 1%
    VOLUME_SPIKE_THRESHOLD: float = 3.0      # 3x normal
    SPREAD_ALERT_THRESHOLD: float = 0.05     # 5%

    # Data retention
    DATA_RETENTION_DAYS: int = 30

    class Config:
        env_file = ".env"

settings = Settings()
```

```
# .env.example

DATABASE_URL=postgresql://user:password@localhost:5432/polymarket
CLOB_API_KEY=optional_api_key_for_higher_rate_limits
```

### Requirements

```
# requirements.txt

fastapi>=0.104.0
uvicorn>=0.24.0
httpx>=0.25.0
sqlalchemy>=2.0.0
asyncpg>=0.29.0
alembic>=1.12.0
apscheduler>=3.10.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-dotenv>=1.0.0
```

---

## Getting Started Instructions

### Step 1: Set up the environment

```bash
# Create project directory
mkdir polymarket-analyzer
cd polymarket-analyzer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Set up the database

```bash
# Create PostgreSQL database
createdb polymarket

# Or use SQLite for development
# Just set DATABASE_URL=sqlite:///./polymarket.db in .env
```

### Step 3: Create configuration

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your settings
```

### Step 4: Initialize database

```bash
# Run migrations
alembic upgrade head

# Or use the init script
python scripts/init_db.py
```

### Step 5: Test API connectivity

```bash
python scripts/test_apis.py
```

### Step 6: Start the application

```bash
# Development
uvicorn src.api.main:app --reload

# Production
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

### Step 7: Access the dashboard

Open http://localhost:8000 in your browser.

---

## Development Priorities

Build in this order:

1. **Data collection first** - Get markets, order books, and trades flowing into the database
2. **Simple dashboard** - Display current data to verify collection is working
3. **Volume analysis** - Easiest analysis module, good quick wins
4. **Order book analysis** - Useful metrics, relatively straightforward
5. **MM pattern analysis** - Builds on order book data
6. **Arbitrage detection** - Most complex, requires market relationship mapping

### MVP Features (Week 1)
- [ ] Market data collection from Gamma API
- [ ] Order book snapshots from CLOB API
- [ ] Trade history collection
- [ ] Basic dashboard showing markets and prices
- [ ] Volume spike detection

### Phase 2 (Week 2)
- [ ] Order book analysis (spread, depth, imbalance)
- [ ] Slippage calculator
- [ ] Spread history tracking
- [ ] Volume charts

### Phase 3 (Week 3)
- [ ] MM pattern detection
- [ ] Best trading hours analysis
- [ ] Alert system

### Phase 4 (Week 4)
- [ ] Market relationship mapping (manual tagging UI)
- [ ] Arbitrage detection
- [ ] Cross-market alerts

---

## Notes for Claude Code

1. **Start simple** - Get data flowing before adding complex analysis
2. **Add logging everywhere** - This will help debug issues
3. **Handle API rate limits** - Add delays between requests, implement retries
4. **Store raw data** - Keep the full order book JSON, you might need it later
5. **Test with a few markets first** - Don't try to collect all markets until the code is stable
6. **The user is not a developer** - All output should be clear, visual, and well-explained

If you need to check the actual Polymarket API responses, visit:
- https://docs.polymarket.com for CLOB API documentation
- The Gamma API doesn't have public docs, but the endpoints work as described

Ask the user if anything is unclear before starting implementation.
