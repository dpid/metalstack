"""Interactive TUI mode for MetalStack."""

import queue
import threading
import time
from datetime import datetime

import readchar
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .api import MetalsAPI, MetalsAPIError
from .display import (
    METAL_NAMES,
    format_change,
    format_change_compact,
    format_price,
)
from .models import MetalPrice, MetalType, TimePeriod
from .portfolio import PortfolioManager, SettingsManager

console = Console()

METAL_KEYS = {
    "1": MetalType.GOLD,
    "g": MetalType.GOLD,
    "2": MetalType.SILVER,
    "s": MetalType.SILVER,
    "3": MetalType.PLATINUM,
    "p": MetalType.PLATINUM,
    "4": MetalType.PALLADIUM,
    "d": MetalType.PALLADIUM,
}

CHART_PERIODS = [
    TimePeriod.WEEK,
    TimePeriod.MONTH,
    TimePeriod.YTD,
    TimePeriod.YEAR,
]


class InteractiveTUI:
    """Interactive terminal UI for MetalStack."""

    def __init__(self, api: MetalsAPI, portfolio: PortfolioManager, settings: SettingsManager):
        self.api = api
        self.portfolio = portfolio
        self.settings = settings
        self.selected_metal = settings.get_last_selected_metal()
        self.prices: dict[MetalType, MetalPrice] = {}
        self.running = False
        self.last_update: datetime | None = None
        self.next_refresh: datetime | None = None
        self.error_message: str | None = None
        self._key_queue: queue.Queue[str] = queue.Queue()
        self._display_dirty = threading.Event()
        # Chart state
        self.show_chart = False
        self.chart_period_index = settings.get_chart_period_index()
        self.chart_data: list[tuple[str, float]] = []
        self._chart_metal: MetalType | None = None
        self._chart_period: TimePeriod | None = None

    def fetch_prices(self) -> None:
        """Fetch current prices from API."""
        try:
            for metal in MetalType:
                self.prices[metal] = self.api.get_metal_spot(metal)
            self.last_update = datetime.now()
            self.next_refresh = datetime.fromtimestamp(
                self.last_update.timestamp() + self.api.cache_ttl
            )
            self.error_message = None
            self._display_dirty.set()
        except MetalsAPIError as e:
            self.error_message = str(e)
            self._display_dirty.set()

    def fetch_chart_data(self) -> None:
        """Fetch historical price data for chart."""
        period = CHART_PERIODS[self.chart_period_index]
        # Only fetch if metal or period changed
        if self._chart_metal == self.selected_metal and self._chart_period == period:
            return
        try:
            self.chart_data = self.api.get_historical_prices(self.selected_metal, period)
            self._chart_metal = self.selected_metal
            self._chart_period = period
            self.error_message = None
        except MetalsAPIError as e:
            self.chart_data = []
            self.error_message = str(e)

    def build_metals_bar(self) -> Panel:
        """Build the metals price bar."""
        table = Table(show_header=False, box=None, padding=(0, 1), expand=True)

        for _ in MetalType:
            table.add_column(justify="center", ratio=1)

        price_cells = []
        change_cells = []

        for metal in MetalType:
            price = self.prices.get(metal)
            if price:
                name = METAL_NAMES[metal]
                # Highlight selected metal
                if metal == self.selected_metal:
                    style = "bold reverse"
                elif metal == MetalType.GOLD:
                    style = "bold yellow"
                else:
                    style = "bold"

                price_text = Text()
                price_text.append(f"{name} ", style=style)
                price_text.append(format_price(price.spot))
                price_cells.append(price_text)
                change_cells.append(format_change_compact(price.change, price.change_pct))
            else:
                price_cells.append(Text("-"))
                change_cells.append(Text("-"))

        table.add_row(*price_cells)
        table.add_row(*change_cells)

        return Panel(
            table,
            title="Precious Metals Spot Prices",
            subtitle="[dim]1-4 or g/s/p/d: select | c: chart | r: refresh | q: quit[/dim]",
            border_style="blue",
            expand=True,
        )

    def build_detail_panel(self) -> Panel:
        """Build the detail panel for selected metal."""
        price = self.prices.get(self.selected_metal)

        table = Table(show_header=False, box=None)
        table.add_column("Label", style="dim")
        table.add_column("Value")

        if price:
            table.add_row("Spot Price", format_price(price.spot))
            if price.bid:
                table.add_row("Bid", format_price(price.bid))
            if price.ask:
                table.add_row("Ask", format_price(price.ask))
            table.add_row("24h Change", format_change(price.change, price.change_pct))
        else:
            table.add_row("Status", "Loading...")

        metal_name = self.selected_metal.value.title()
        return Panel(table, title=f"{metal_name} Detail", border_style="cyan")

    def _downsample(self, values: list[float], max_points: int) -> list[float]:
        """Downsample a list of values to fit within max_points."""
        if len(values) <= max_points:
            return values

        # Calculate step size and sample evenly
        step = len(values) / max_points
        return [values[int(i * step)] for i in range(max_points)]

    def build_chart_panel(self) -> Panel | None:
        """Build the price chart panel."""
        if not self.show_chart:
            return None

        period = CHART_PERIODS[self.chart_period_index]
        metal_name = self.selected_metal.value.title()

        if not self.chart_data:
            content = Text("Loading chart data...", style="dim")
        else:
            try:
                from asciichartpy import plot

                # Get terminal width and calculate max chart width
                # Account for panel borders (2), padding (2), and y-axis labels (~12)
                max_width = console.width - 16
                max_width = max(20, min(max_width, 120))  # Clamp between 20-120

                values = [p[1] for p in self.chart_data]
                values = self._downsample(values, max_width)
                chart = plot(values, {"height": 8})

                start_date = self.chart_data[0][0]
                end_date = self.chart_data[-1][0]

                content = Text(f"{chart}\n\n")
                content.append(f"{start_date} to {end_date}", style="dim")
            except ImportError:
                content = Text("Install asciichartpy: pip install asciichartpy", style="yellow")

        # Build period selector display
        period_display = []
        for i, p in enumerate(CHART_PERIODS):
            if i == self.chart_period_index:
                period_display.append(f"[reverse]{p.value}[/reverse]")
            else:
                period_display.append(f"[dim]{p.value}[/dim]")

        subtitle = f"[dim]c: hide | < >: period[/dim]  {' '.join(period_display)}"

        return Panel(
            content,
            title=f"{metal_name} Price Chart",
            subtitle=subtitle,
            border_style="magenta",
        )

    def build_portfolio_panel(self) -> Panel:
        """Build the portfolio summary panel."""
        items = self.portfolio.list_items()
        spot_prices = {m: p.spot for m, p in self.prices.items()}

        if not items:
            content = Text("No items in portfolio. Use 'metalstack add' to add items.", style="dim")
        else:
            summary = self.portfolio.get_summary(spot_prices)

            table = Table(show_header=False, box=None)
            table.add_column("Label", style="dim")
            table.add_column("Value")

            table.add_row("Total Value", Text(format_price(summary["total_value"]), style="bold"))
            table.add_row("Items", str(summary["total_items"]))

            # Add breakdown by metal
            for metal, data in summary["by_metal"].items():
                if data["weight_oz"] > 0:
                    metal_text = f"{metal.value.title()}: {data['weight_oz']:.2f} oz"
                    value_text = format_price(data["value"])
                    table.add_row(metal_text, value_text)

            content = table

        return Panel(content, title="Portfolio Summary", border_style="green")

    def build_items_table(self) -> Table | Text:
        """Build the portfolio items table."""
        items = self.portfolio.list_items()
        spot_prices = {m: p.spot for m, p in self.prices.items()}

        if not items:
            return Text("")

        table = Table(title="Portfolio Items")
        table.add_column("#", style="dim", width=3)
        table.add_column("Name")
        table.add_column("Metal")
        table.add_column("Year")
        table.add_column("Size", justify="right")
        table.add_column("Qty", justify="right")
        table.add_column("Value", justify="right")

        for i, item in enumerate(items):
            spot = spot_prices.get(item.metal, 0)
            value = item.spot_value(spot)

            table.add_row(
                str(i + 1),
                item.name,
                item.metal.value.title(),
                str(item.year) if item.year else "-",
                f"{item.weight_oz} oz",
                str(item.quantity),
                format_price(value),
            )

        return table

    def build_status_bar(self) -> Text:
        """Build the status bar."""
        status = Text()

        if self.error_message:
            status.append(f"Error: {self.error_message}", style="red")
        elif self.last_update:
            status.append(f"Updated: {self.last_update.strftime('%H:%M:%S')}", style="dim")
            if self.next_refresh:
                status.append(" • ", style="dim")
                status.append(f"Next: {self.next_refresh.strftime('%H:%M:%S')}", style="dim")

        return status

    def build_display(self) -> Group:
        """Build the complete display."""
        components = [
            self.build_metals_bar(),
            self.build_detail_panel(),
        ]

        chart_panel = self.build_chart_panel()
        if chart_panel:
            components.append(chart_panel)

        components.extend([
            self.build_portfolio_panel(),
            self.build_items_table(),
            self.build_status_bar(),
        ])

        return Group(*components)

    def handle_key(self, key: str) -> bool:
        """Handle a key press. Returns False to quit."""
        if key.lower() in ("q", "\x03"):  # q or Ctrl+C
            return False

        if key.lower() == "r":
            # Force refresh by clearing cache
            self.fetch_prices()

        if key.lower() in METAL_KEYS:
            self.selected_metal = METAL_KEYS[key.lower()]
            if self.show_chart:
                self.fetch_chart_data()
            self._display_dirty.set()

        if key.lower() == "c":
            self.show_chart = not self.show_chart
            if self.show_chart:
                self.fetch_chart_data()
            self._display_dirty.set()

        if key in ("<", ",") and self.show_chart:
            self.chart_period_index = (self.chart_period_index - 1) % len(CHART_PERIODS)
            self.fetch_chart_data()
            self._display_dirty.set()

        if key in (">", ".") and self.show_chart:
            self.chart_period_index = (self.chart_period_index + 1) % len(CHART_PERIODS)
            self.fetch_chart_data()
            self._display_dirty.set()

        return True

    def _key_reader_thread(self) -> None:
        """Background thread to read key presses."""
        while self.running:
            try:
                key = readchar.readkey()
                self._key_queue.put(key)
            except (OSError, Exception) as e:
                if "ioctl" in str(e).lower() or "termios" in str(type(e).__module__).lower():
                    self._key_queue.put("q")  # Signal quit on terminal error
                    break
                raise

    def _auto_refresh_thread(self) -> None:
        """Background thread to auto-refresh prices based on cache TTL."""
        while self.running:
            # Sleep in small increments to allow quick shutdown
            sleep_time = self.api.cache_ttl
            for _ in range(sleep_time):
                if not self.running:
                    return
                time.sleep(1)

            if self.running:
                self.fetch_prices()

    def run(self) -> None:
        """Run the interactive TUI."""
        self.running = True

        # Initial fetch
        self.fetch_prices()

        # Start background threads
        key_thread = threading.Thread(target=self._key_reader_thread, daemon=True)
        refresh_thread = threading.Thread(target=self._auto_refresh_thread, daemon=True)
        key_thread.start()
        refresh_thread.start()

        try:
            with Live(
                self.build_display(),
                console=console,
                refresh_per_second=2,
                screen=True,
                vertical_overflow="crop",
            ) as live:
                while self.running:
                    # Check for key press (non-blocking)
                    try:
                        key = self._key_queue.get(timeout=0.1)
                        if not self.handle_key(key):
                            break
                    except queue.Empty:
                        pass

                    # Update display if dirty
                    if self._display_dirty.is_set():
                        self._display_dirty.clear()
                        live.update(self.build_display())

        except KeyboardInterrupt:
            pass

        self.running = False
        self.settings.set_last_selected_metal(self.selected_metal)
        self.settings.set_chart_period_index(self.chart_period_index)


def run_interactive(api: MetalsAPI, portfolio: PortfolioManager) -> None:
    """Run the interactive TUI."""
    settings = SettingsManager()
    tui = InteractiveTUI(api, portfolio, settings)
    tui.run()
