"""Data models for MetalStack."""

from enum import Enum
from pydantic import BaseModel, Field


class MetalType(str, Enum):
    """Supported precious metals."""

    GOLD = "gold"
    SILVER = "silver"
    PLATINUM = "platinum"
    PALLADIUM = "palladium"


class MetalPrice(BaseModel):
    """Current price data for a precious metal."""

    metal: MetalType
    spot: float = Field(description="Current spot price per troy oz in USD")
    bid: float | None = Field(default=None, description="Current bid price")
    ask: float | None = Field(default=None, description="Current ask price")
    change: float = Field(default=0.0, description="Price change in USD")
    change_pct: float = Field(default=0.0, description="Price change percentage")


class CollectionItem(BaseModel):
    """An item in the user's precious metals collection."""

    name: str = Field(description="Item name, e.g., 'American Gold Eagle'")
    metal: MetalType = Field(description="Type of precious metal")
    weight_oz: float = Field(description="Weight in troy ounces")
    quantity: int = Field(default=1, description="Number of items")
    year: int | None = Field(default=None, description="Year of minting")

    @property
    def total_weight_oz(self) -> float:
        """Total weight of all items in troy ounces."""
        return self.weight_oz * self.quantity

    def spot_value(self, spot_price: float) -> float:
        """Calculate current spot value based on given spot price."""
        return self.total_weight_oz * spot_price


class Portfolio(BaseModel):
    """User's complete precious metals portfolio."""

    items: list[CollectionItem] = Field(default_factory=list)

    def total_weight_by_metal(self, metal: MetalType) -> float:
        """Get total weight for a specific metal type."""
        return sum(item.total_weight_oz for item in self.items if item.metal == metal)

    def total_value(self, prices: dict[MetalType, float]) -> float:
        """Calculate total portfolio value given current spot prices."""
        return sum(item.spot_value(prices.get(item.metal, 0)) for item in self.items)


class TimePeriod(str, Enum):
    """Time periods for historical data."""

    DAY = "24h"
    THREE_DAYS = "3d"
    WEEK = "1w"
    MONTH = "1m"
    YTD = "ytd"
    YEAR = "1y"
    FIVE_YEARS = "5y"
    ALL = "all"
