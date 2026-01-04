"""Portfolio management for precious metals collection."""

import json
from pathlib import Path

from .models import CollectionItem, MetalType, Portfolio

DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / "metalstack"
DEFAULT_COLLECTION_FILE = DEFAULT_DATA_DIR / "collection.json"
DEFAULT_SETTINGS_FILE = DEFAULT_DATA_DIR / "settings.json"


class PortfolioManager:
    """Manages loading, saving, and modifying the portfolio."""

    def __init__(self, collection_path: Path | None = None):
        self.collection_path = collection_path or DEFAULT_COLLECTION_FILE
        self.collection_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Portfolio:
        """Load portfolio from JSON file."""
        if not self.collection_path.exists():
            return Portfolio(items=[])

        try:
            data = json.loads(self.collection_path.read_text())
            return Portfolio.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            return Portfolio(items=[])

    def save(self, portfolio: Portfolio) -> None:
        """Save portfolio to JSON file."""
        self.collection_path.write_text(
            portfolio.model_dump_json(indent=2)
        )

    def add_item(
        self,
        name: str,
        metal: MetalType,
        weight_oz: float,
        quantity: int = 1,
        year: int | None = None,
    ) -> CollectionItem:
        """Add a new item to the portfolio."""
        portfolio = self.load()

        item = CollectionItem(
            name=name,
            metal=metal,
            weight_oz=weight_oz,
            quantity=quantity,
            year=year,
        )
        portfolio.items.append(item)
        self.save(portfolio)

        return item

    def remove_item(self, index: int) -> CollectionItem | None:
        """Remove an item by index. Returns the removed item or None."""
        portfolio = self.load()

        if 0 <= index < len(portfolio.items):
            removed = portfolio.items.pop(index)
            self.save(portfolio)
            return removed

        return None

    def update_quantity(self, index: int, quantity: int) -> CollectionItem | None:
        """Update the quantity of an item. Returns updated item or None."""
        portfolio = self.load()

        if 0 <= index < len(portfolio.items):
            portfolio.items[index].quantity = quantity
            self.save(portfolio)
            return portfolio.items[index]

        return None

    def update_item(
        self,
        index: int,
        name: str | None = None,
        metal: MetalType | None = None,
        weight_oz: float | None = None,
        quantity: int | None = None,
        year: int | None = None,
    ) -> CollectionItem | None:
        """Update an item's properties. Returns updated item or None."""
        portfolio = self.load()

        if 0 <= index < len(portfolio.items):
            item = portfolio.items[index]
            if name is not None:
                item.name = name
            if metal is not None:
                item.metal = metal
            if weight_oz is not None:
                item.weight_oz = weight_oz
            if quantity is not None:
                item.quantity = quantity
            if year is not None:
                item.year = year
            self.save(portfolio)
            return item

        return None

    def get_item(self, index: int) -> CollectionItem | None:
        """Get an item by index."""
        portfolio = self.load()
        if 0 <= index < len(portfolio.items):
            return portfolio.items[index]
        return None

    def list_items(self) -> list[CollectionItem]:
        """Get all items in the portfolio."""
        return self.load().items

    def get_summary(self, prices: dict[MetalType, float]) -> dict:
        """Get portfolio summary with current values."""
        portfolio = self.load()

        by_metal = {}
        for metal in MetalType:
            weight = portfolio.total_weight_by_metal(metal)
            price = prices.get(metal, 0)
            by_metal[metal] = {
                "weight_oz": weight,
                "value": weight * price,
            }

        return {
            "total_items": len(portfolio.items),
            "total_value": portfolio.total_value(prices),
            "by_metal": by_metal,
        }


class SettingsManager:
    """Manages application settings persistence."""

    def __init__(self, settings_path: Path | None = None):
        self.settings_path = settings_path or DEFAULT_SETTINGS_FILE
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        """Load settings from JSON file."""
        if not self.settings_path.exists():
            return {}
        try:
            return json.loads(self.settings_path.read_text())
        except (json.JSONDecodeError, ValueError):
            return {}

    def _save(self, settings: dict) -> None:
        """Save settings to JSON file."""
        self.settings_path.write_text(json.dumps(settings, indent=2))

    def get_last_selected_metal(self) -> MetalType:
        """Get the last selected metal, defaulting to GOLD."""
        settings = self._load()
        metal_value = settings.get("last_selected_metal")
        if metal_value:
            try:
                return MetalType(metal_value)
            except ValueError:
                pass
        return MetalType.GOLD

    def set_last_selected_metal(self, metal: MetalType) -> None:
        """Save the last selected metal."""
        settings = self._load()
        settings["last_selected_metal"] = metal.value
        self._save(settings)

    def get_chart_period_index(self) -> int:
        """Get the last selected chart period index, defaulting to 1 (month)."""
        settings = self._load()
        return settings.get("chart_period_index", 1)

    def set_chart_period_index(self, index: int) -> None:
        """Save the chart period index."""
        settings = self._load()
        settings["chart_period_index"] = index
        self._save(settings)
