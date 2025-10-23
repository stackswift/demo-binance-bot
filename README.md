# Binance Futures Order Bot

A CLI-based trading bot for Binance USDT-M Futures that supports multiple order types with robust logging, validation, and documentation.

## Features

### Core Orders
- Market Orders - Instant execution at market price
- Limit Orders - Set your desired entry price

### Advanced Orders (Bonus Features)
- Stop-Limit Orders - Trigger limit orders at specified price points
- OCO (One-Cancels-the-Other) - Place take-profit and stop-loss simultaneously
- TWAP (Time-Weighted Average Price) - Split large orders over time
- Grid Trading - Automated buy-low/sell-high within a price range

## Installation

1. Clone the repository:
```bash
git clone https://github.com/[your-username]/demo-binance-bot.git
cd demo-binance-bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure your Binance API credentials:
   - Copy `.env.example` to `.env`
   - Add your Binance API key and secret
   - Optional: Configure testnet credentials for development

## Usage

### Market Orders
```bash
# Format: python src/market_orders.py <symbol> <side> <quantity>
python src/market_orders.py BTCUSDT BUY 0.01
```

### Limit Orders
```bash
# Format: python src/limit_orders.py <symbol> <side> <quantity> <price>
python src/limit_orders.py BTCUSDT SELL 0.01 35000
```

### Advanced Orders

#### OCO (One-Cancels-the-Other)
```bash
# Format: python src/advanced/oco.py <symbol> <side> <quantity> <limit_price> <stop_price> <stop_limit_price>
python src/advanced/oco.py BTCUSDT BUY 0.01 34000 35000 33000
```

#### TWAP (Time-Weighted Average Price)
```bash
# Format: python src/advanced/twap.py <symbol> <side> <total_quantity> <num_chunks> <interval_minutes>
python src/advanced/twap.py BTCUSDT BUY 0.1 10 5
```

#### Grid Trading
```bash
# Format: python src/advanced/grid.py <symbol> <lower_price> <upper_price> <num_grids> <quantity_per_grid>
python src/advanced/grid.py BTCUSDT 30000 40000 10 0.001
```

## Development

### Testing
Run the test suite:
```bash
pytest tests/
```

### Logging
All actions are logged to `bot.log` with timestamps and structured data.

### Configuration
- Environment variables in `.env`
- Static configuration in `config.py`
- CLI arguments for order parameters

## Resources
- [Binance Futures API Documentation](https://binance-docs.github.io/apidocs/futures/en/)
- [Historical Data (Google Drive)](https://drive.google.com/file/d/1IAfLZwu6rJzyWKgBToqwSmmVYU6VbjVs/view)
- [Fear & Greed Index Data](https://drive.google.com/file/d/1PgQC0tO8XN-wqkNyghWc_-mnrYv_nhSf/view)

## License
MIT License