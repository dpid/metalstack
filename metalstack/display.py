"""Rich-based terminal display for MetalStack."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import CollectionItem, MetalPrice, MetalType, TimePeriod

console = Console()

METAL_NAMES = {
    MetalType.GOLD: "Gold",
    MetalType.SILVER: "Silver",
    MetalType.PLATINUM: "Plat",
    MetalType.PALLADIUM: "Pall",
}


def format_price(value: float, precision: int = 2) -> str:
    """Format a price value with commas and fixed precision."""
    return f"${value:,.{precision}f}"


def format_change(change: float, change_pct: float) -> Text:
    """Format price change with color coding."""
    if change >= 0:
        style = "green"
        sign = "+"
    else:
        style = "red"
        sign = ""

    text = Text()
    text.append(f"{sign}{format_price(change)} ", style=style)
    text.append(f"({sign}{change_pct:.2f}%)", style=style)
    return text


def format_change_compact(change: float, change_pct: float) -> Text:
    """Format price and percentage change compactly for the top bar."""
    if change >= 0:
        style = "green"
        sign = "+"
    else:
        style = "red"
        sign = ""
    return Text(f"{sign}${abs(change):.2f} ({sign}{change_pct:.2f}%)", style=style)


def display_metals_bar(prices: dict[MetalType, MetalPrice]) -> None:
    """Display top bar with all metal prices."""
    table = Table(show_header=False, box=None, padding=(0, 1), expand=True)

    for _ in MetalType:
        table.add_column(justify="center", ratio=1)

    # Row 1: Symbol and price
    price_cells = []
    # Row 2: Change
    change_cells = []

    for metal in MetalType:
        price = prices.get(metal)
        if price:
            name = METAL_NAMES[metal]
            price_text = Text()
            price_text.append(f"{name} ", style="bold yellow" if metal == MetalType.GOLD else "bold")
            price_text.append(format_price(price.spot))
            price_cells.append(price_text)
            change_cells.append(format_change_compact(price.change, price.change_pct))
        else:
            price_cells.append(Text("-"))
            change_cells.append(Text("-"))

    table.add_row(*price_cells)
    table.add_row(*change_cells)
    console.print(Panel(table, title="Precious Metals Spot Prices", border_style="blue", expand=True))


def display_metal_detail(price: MetalPrice) -> None:
    """Display detailed view for selected metal."""
    table = Table(show_header=False, box=None)
    table.add_column("Label", style="dim")
    table.add_column("Value")

    table.add_row("Spot Price", format_price(price.spot))

    if price.bid:
        table.add_row("Bid", format_price(price.bid))
    if price.ask:
        table.add_row("Ask", format_price(price.ask))

    table.add_row("24h Change", format_change(price.change, price.change_pct))

    metal_name = price.metal.value.title()
    console.print(Panel(table, title=f"{metal_name} Detail", border_style="cyan"))


def display_portfolio_summary(
    total_value: float,
    change: float,
    change_pct: float,
    by_metal: dict[MetalType, dict],
) -> None:
    """Display portfolio summary panel."""
    table = Table(show_header=False, box=None)
    table.add_column("Label", style="dim")
    table.add_column("Value")

    table.add_row("Total Value", Text(format_price(total_value), style="bold"))
    table.add_row("Change", format_change(change, change_pct))

    # Add breakdown by metal
    table.add_row("", "")
    for metal, data in by_metal.items():
        if data["weight_oz"] > 0:
            metal_text = f"{metal.value.title()}: {data['weight_oz']:.2f} oz"
            value_text = format_price(data["value"])
            table.add_row(metal_text, value_text)

    console.print(Panel(table, title="Portfolio Summary", border_style="green"))


def display_collection_table(
    items: list[CollectionItem],
    prices: dict[MetalType, float],
) -> None:
    """Display table of collection items."""
    if not items:
        console.print("[dim]No items in collection. Use 'metalstack add' to add items.[/dim]")
        return

    table = Table(title="Portfolio Items")
    table.add_column("#", style="dim", width=3)
    table.add_column("Name")
    table.add_column("Metal")
    table.add_column("Year")
    table.add_column("Size", justify="right")
    table.add_column("Qty", justify="right")
    table.add_column("Value", justify="right")

    for i, item in enumerate(items):
        spot = prices.get(item.metal, 0)
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

    console.print(table)


def display_chart(
    title: str,
    prices: list[tuple[str, float]],
    period: TimePeriod,
) -> None:
    """Display ASCII price chart."""
    if not prices:
        console.print("[dim]No historical data available.[/dim]")
        return

    try:
        from asciichartpy import plot

        values = [p[1] for p in prices]
        chart = plot(values, {"height": 10})

        # Add date range info
        start_date = prices[0][0]
        end_date = prices[-1][0]

        console.print(Panel(
            f"{chart}\n\n[dim]{start_date} to {end_date}[/dim]",
            title=f"{title} ({period.value})",
            border_style="magenta",
        ))
    except ImportError:
        console.print("[yellow]Install asciichartpy for charts: pip install asciichartpy[/yellow]")


def display_error(message: str) -> None:
    """Display error message."""
    console.print(f"[red]Error:[/red] {message}")


def display_success(message: str) -> None:
    """Display success message."""
    console.print(f"[green]{message}[/green]")
