# MetalStack

A CLI app for tracking your precious metals portfolio with real-time spot prices.

## Features

- **Interactive TUI** - Live dashboard with keyboard controls and auto-refresh
- Real-time spot prices for gold, silver, platinum, and palladium
- Track your bullion collection (coins and bars)
- Portfolio value with 24h change tracking
- ASCII price charts with multiple time periods (1w, 1m, ytd, 1y, 5y)
- Persistent settings (remembers last selected metal and chart period)

## Installation

```bash
pip install -e .
```

## Setup

Get a free API key from [Metals.Dev](https://metals.dev) and set it:

```bash
export METALS_API_KEY="your-api-key"
```

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `METALS_API_KEY` | (required) | Your Metals.Dev API key |
| `METALS_CACHE_TTL` | `3600` | Cache duration in seconds (default: 1 hour) |

The free Metals.Dev tier has limited API requests, so responses are cached to minimize API calls.

## Usage

```bash
# Launch interactive dashboard (default)
metalstack

# Run once and exit (non-interactive)
metalstack --once

# Show price chart (non-interactive)
metalstack --chart --period 1m

# Add item to collection
metalstack add

# Edit an item
metalstack edit

# Remove item
metalstack remove

# List collection
metalstack list
```

## Interactive Mode

By default, `metalstack` launches an interactive dashboard that stays open until you quit.

**Key Bindings:**

| Key | Action |
|-----|--------|
| `1` or `g` | Select Gold |
| `2` or `s` | Select Silver |
| `3` or `p` | Select Platinum |
| `4` or `d` | Select Palladium |
| `c` | Toggle price chart |
| `<` or `,` | Previous chart period |
| `>` or `.` | Next chart period |
| `r` | Refresh prices |
| `q` | Quit |

Prices auto-refresh based on the cache TTL setting.

## Commands

| Command | Description |
|---------|-------------|
| `metalstack` | Main dashboard with prices and portfolio |
| `metalstack add` | Add item interactively |
| `metalstack edit` | Edit an existing item |
| `metalstack remove` | Remove item from collection |
| `metalstack list` | List all items |
| `metalstack chart` | Show price history chart |

## Data Storage

Your data is stored locally and never uploaded:

| Data | Location |
|------|----------|
| Portfolio | `~/.local/share/metalstack/collection.json` |
| Settings | `~/.local/share/metalstack/settings.json` |
| API Cache | `~/.cache/metalstack/` |

## Options

| Option | Description |
|--------|-------------|
| `--once`, `-1` | Run once and exit (non-interactive mode) |
| `--metal`, `-m` | Metal to focus on (gold, silver, platinum, palladium) |
| `--period`, `-p` | Time period (1w, 1m, ytd, 1y, 5y) |
| `--chart`, `-c` | Show price chart |
