class StockThemesError(Exception):
    """Base exception."""


class ProviderError(StockThemesError):
    """A data provider failed."""


class TickerNotFoundError(ProviderError):
    """Ticker symbol not found."""


class RateLimitError(ProviderError):
    """API rate limit hit."""


class ExtractionError(StockThemesError):
    """Theme extraction failed."""
