"""CLI interface for MetalStack."""

from typing import Annotated, Optional

import typer
from rich.prompt import Confirm, FloatPrompt, IntPrompt, Prompt

from .api import MetalsAPI, MetalsAPIError
from .charts import calculate_change, show_price_chart
from .display import (
    console,
    display_collection_table,
    display_error,
    display_metal_detail,
    display_metals_bar,
    display_portfolio_summary,
    display_success,
)
from .models import MetalType, TimePeriod
from .portfolio import PortfolioManager
from .tui import run_interactive

app = typer.Typer(
    name="metalstack",
    help="Track your precious metals portfolio with real-time spot prices.",
    invoke_without_command=True,
)


def get_api() -> MetalsAPI:
    """Get API client, handling missing key gracefully."""
    try:
        return MetalsAPI()
    except MetalsAPIError as e:
        display_error(str(e))
        raise typer.Exit(1)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    metal: Annotated[
        MetalType,
        typer.Option("--metal", "-m", help="Metal to show in detail view"),
    ] = MetalType.GOLD,
    period: Annotated[
        TimePeriod,
        typer.Option("--period", "-p", help="Time period for changes"),
    ] = TimePeriod.DAY,
    chart: Annotated[
        bool,
        typer.Option("--chart", "-c", help="Show price chart"),
    ] = False,
    once: Annotated[
        bool,
        typer.Option("--once", "-1", help="Run once and exit (non-interactive)"),
    ] = False,
) -> None:
    """Display precious metals prices and portfolio summary."""
    if ctx.invoked_subcommand is not None:
        return

    api = get_api()
    portfolio = PortfolioManager()

    # Interactive mode (default)
    if not once and not chart:
        run_interactive(api, portfolio)
        return

    # Non-interactive mode (--once or --chart)
    try:
        # Get detailed spot prices for all metals (includes change data)
        with console.status("Fetching prices..."):
            prices = {}
            for m in MetalType:
                prices[m] = api.get_metal_spot(m)
            detail = prices[metal]

        # Display metals bar
        display_metals_bar(prices)

        # Display selected metal detail
        display_metal_detail(detail)

        # Get portfolio data
        items = portfolio.list_items()
        spot_prices = {m: p.spot for m, p in prices.items()}

        if items:
            summary = portfolio.get_summary(spot_prices)

            # For now, use 0 change (would need historical portfolio tracking)
            display_portfolio_summary(
                total_value=summary["total_value"],
                change=0.0,
                change_pct=0.0,
                by_metal=summary["by_metal"],
            )

            display_collection_table(items, spot_prices)
        else:
            console.print("\n[dim]No items in portfolio. Use 'metalstack add' to add items.[/dim]")

        # Show chart if requested
        if chart:
            console.print()
            show_price_chart(api, metal, period)

    except MetalsAPIError as e:
        display_error(str(e))
        raise typer.Exit(1)


@app.command()
def add() -> None:
    """Add an item to your collection interactively."""
    portfolio = PortfolioManager()

    console.print("\n[bold]Add Item to Collection[/bold]\n")

    # Prompt for item details
    name = Prompt.ask("Item name", default="American Gold Eagle")

    metal_choices = [m.value for m in MetalType]
    metal_str = Prompt.ask(
        "Metal type",
        choices=metal_choices,
        default="gold",
    )
    metal = MetalType(metal_str)

    weight = FloatPrompt.ask("Weight (troy oz)", default=1.0)
    quantity = IntPrompt.ask("Quantity", default=1)
    year_str = Prompt.ask("Year (optional, press Enter to skip)", default="")
    year = int(year_str) if year_str else None

    # Add the item
    item = portfolio.add_item(
        name=name,
        metal=metal,
        weight_oz=weight,
        quantity=quantity,
        year=year,
    )

    display_success(f"\nAdded: {item.quantity}x {item.name} ({item.weight_oz} oz {item.metal.value})")


@app.command()
def remove(
    index: Annotated[
        Optional[int],
        typer.Argument(help="Item number to remove (1-based)"),
    ] = None,
) -> None:
    """Remove an item from your collection."""
    portfolio = PortfolioManager()
    items = portfolio.list_items()

    if not items:
        display_error("No items in collection.")
        raise typer.Exit(1)

    # If no index provided, show list and ask
    if index is None:
        console.print("\n[bold]Remove Item from Collection[/bold]\n")

        for i, item in enumerate(items, 1):
            console.print(f"  {i}. {item.name} ({item.weight_oz} oz {item.metal.value})")

        console.print()
        index = IntPrompt.ask("Enter item number to remove")

    # Convert to 0-based index
    idx = index - 1

    if idx < 0 or idx >= len(items):
        display_error(f"Invalid item number. Choose 1-{len(items)}.")
        raise typer.Exit(1)

    item = items[idx]
    if Confirm.ask(f"Remove {item.name}?"):
        portfolio.remove_item(idx)
        display_success(f"Removed: {item.name}")
    else:
        console.print("Cancelled.")


@app.command()
def edit(
    index: Annotated[
        Optional[int],
        typer.Argument(help="Item number to edit (1-based)"),
    ] = None,
) -> None:
    """Edit an item in your collection."""
    portfolio = PortfolioManager()
    items = portfolio.list_items()

    if not items:
        display_error("No items in collection.")
        raise typer.Exit(1)

    # If no index provided, show list and ask
    if index is None:
        console.print("\n[bold]Edit Item in Collection[/bold]\n")

        for i, item in enumerate(items, 1):
            console.print(f"  {i}. {item.name} ({item.weight_oz} oz {item.metal.value})")

        console.print()
        index = IntPrompt.ask("Enter item number to edit")

    # Convert to 0-based index
    idx = index - 1

    if idx < 0 or idx >= len(items):
        display_error(f"Invalid item number. Choose 1-{len(items)}.")
        raise typer.Exit(1)

    item = items[idx]
    console.print(f"\n[bold]Editing: {item.name}[/bold]")
    console.print("[dim]Press Enter to keep current value[/dim]\n")

    # Prompt for each field with current value as default
    name = Prompt.ask("Name", default=item.name)

    metal_choices = [m.value for m in MetalType]
    metal_str = Prompt.ask(
        "Metal type",
        choices=metal_choices,
        default=item.metal.value,
    )
    metal = MetalType(metal_str)

    weight = FloatPrompt.ask("Weight (troy oz)", default=item.weight_oz)
    quantity = IntPrompt.ask("Quantity", default=item.quantity)

    year_default = str(item.year) if item.year else ""
    year_str = Prompt.ask("Year (optional)", default=year_default)
    year = int(year_str) if year_str else None

    # Update the item
    updated = portfolio.update_item(
        index=idx,
        name=name,
        metal=metal,
        weight_oz=weight,
        quantity=quantity,
        year=year,
    )

    if updated:
        display_success(f"\nUpdated: {updated.quantity}x {updated.name} ({updated.weight_oz} oz {updated.metal.value})")
    else:
        display_error("Failed to update item.")


@app.command(name="list")
def list_items() -> None:
    """List all items in your collection."""
    api = get_api()
    portfolio = PortfolioManager()

    items = portfolio.list_items()

    if not items:
        console.print("[dim]No items in collection. Use 'metalstack add' to add items.[/dim]")
        return

    try:
        with console.status("Fetching prices..."):
            prices = api.get_latest_prices()

        spot_prices = {m: p.spot for m, p in prices.items()}
        display_collection_table(items, spot_prices)

    except MetalsAPIError:
        # Show list without prices if API fails
        display_collection_table(items, {})


@app.command()
def chart(
    metal: Annotated[
        MetalType,
        typer.Option("--metal", "-m", help="Metal to chart"),
    ] = MetalType.GOLD,
    period: Annotated[
        TimePeriod,
        typer.Option("--period", "-p", help="Time period"),
    ] = TimePeriod.MONTH,
) -> None:
    """Show price chart for a metal."""
    api = get_api()

    try:
        with console.status(f"Fetching {metal.value} history..."):
            show_price_chart(api, metal, period)
    except MetalsAPIError as e:
        display_error(str(e))
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
