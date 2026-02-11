"""Disk-based cache with TTL for provider results."""

from __future__ import annotations

import json
import hashlib
import time
from pathlib import Path
from functools import wraps
from typing import Any

from stock_themes.config import CACHE_DIR


def disk_cache(provider_name: str, ttl_hours: int = 24):
    """Decorator for caching provider results to disk with TTL.

    Caches the return value as JSON. The decorated function must
    accept (self, ticker: str, ...) and return a serializable dict or dataclass.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, ticker: str, *args, **kwargs):
            cache_dir = CACHE_DIR / provider_name
            cache_dir.mkdir(parents=True, exist_ok=True)

            cache_key = hashlib.md5(ticker.upper().encode()).hexdigest()
            cache_file = cache_dir / f"{cache_key}.json"

            if cache_file.exists():
                try:
                    data = json.loads(cache_file.read_text())
                    cached_at = data.pop("_cached_at", 0)
                    if time.time() - cached_at < ttl_hours * 3600:
                        return data
                except (json.JSONDecodeError, KeyError):
                    pass

            result = func(self, ticker, *args, **kwargs)

            # Cache the result
            cache_data: dict[str, Any]
            if hasattr(result, "__dict__"):
                from dataclasses import asdict
                cache_data = asdict(result)
            elif isinstance(result, dict):
                cache_data = result.copy()
            else:
                return result

            cache_data["_cached_at"] = time.time()
            try:
                cache_file.write_text(json.dumps(cache_data, default=str))
            except (TypeError, OSError):
                pass

            return result
        return wrapper
    return decorator


def clear_cache(provider_name: str | None = None) -> int:
    """Clear cached data. Returns number of files deleted."""
    count = 0
    if provider_name:
        cache_dir = CACHE_DIR / provider_name
        if cache_dir.exists():
            for f in cache_dir.glob("*.json"):
                f.unlink()
                count += 1
    else:
        for cache_dir in CACHE_DIR.iterdir():
            if cache_dir.is_dir():
                for f in cache_dir.glob("*.json"):
                    f.unlink()
                    count += 1
    return count
