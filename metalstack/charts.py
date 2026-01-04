"""Price history charting for MetalStack."""

from .api import MetalsAPI
from .display import display_chart
from .models import MetalType, TimePeriod


def show_price_chart(
    api: MetalsAPI,
    metal: MetalType,
    period: TimePeriod,
) -> None:
    """Fetch and display price chart for a metal."""
    prices = api.get_historical_prices(metal, period)
    title = f"{metal.value.title()} Price"
    display_chart(title, prices, period)


def calculate_change(prices: list[tuple[str, float]]) -> tuple[float, float]:
    """Calculate absolute and percentage change from historical data.

    Returns (change_amount, change_percentage).
    """
    if len(prices) < 2:
        return 0.0, 0.0

    start_price = prices[0][1]
    end_price = prices[-1][1]

    change = end_price - start_price
    change_pct = (change / start_price) * 100 if start_price else 0

    return change, change_pct
