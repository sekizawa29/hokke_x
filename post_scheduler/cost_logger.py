#!/usr/bin/env python3
"""
X API usage/cost logger.
Logs per-call usage in JSONL for later daily aggregation.
"""

import json
from pathlib import Path
from datetime import datetime, date
from typing import Any, Optional

PROJECT_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_DIR / "analytics"
LOG_FILE = LOG_DIR / "x_api_usage.jsonl"

# Unit prices are based on docs/X_API_PRICING.md
UNIT_PRICES = {
    "post_read": 0.005,
    "user_read": 0.010,
    "content_create": 0.010,
    "dm_read": 0.010,
    "user_interaction_create": 0.015,
}


def log_api_usage(
    usage_type: str,
    units: int,
    endpoint: str,
    *,
    request_count: int = 1,
    context: str = "",
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """Append one usage record to analytics/x_api_usage.jsonl."""
    unit_price = UNIT_PRICES.get(usage_type, 0.0)
    units = max(int(units), 0)
    request_count = max(int(request_count), 1)
    cost_usd = round(units * unit_price, 6)

    record = {
        "timestamp": datetime.now().isoformat(),
        "date": date.today().isoformat(),
        "usage_type": usage_type,
        "endpoint": endpoint,
        "units": units,
        "unit_price_usd": unit_price,
        "estimated_cost_usd": cost_usd,
        "request_count": request_count,
        "context": context,
        "metadata": metadata or {},
    }

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
