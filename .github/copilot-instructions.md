# Copilot Instructions for demo-binance-bot

This document provides essential context and guidance for AI coding agents working in this codebase.

## Project Overview

This is a CLI-based trading bot for Binance USDT-M Futures that supports multiple order types with robust logging, validation, and documentation. The bot implements both core and advanced order types for cryptocurrency futures trading.

## Key Concepts & Architecture

The project follows a modular architecture with clear separation of concerns:

### Core Components

1. Order Types:
   - Base order handling (`src/base_order.py`)
   - Market orders (`src/market_orders.py`)
   - Limit orders (`src/limit_orders.py`)
   - Advanced orders (`src/advanced/`)
     - Stop-Limit orders
     - OCO (One-Cancels-the-Other)
     - TWAP (Time-Weighted Average Price)
     - Grid Trading

2. Validation Layer:
   - Input validation (symbol, quantity, price)
   - Market data validation
   - Account balance checks

3. Logging System:
   - Structured logging with timestamps
   - Error tracing
   - Order execution tracking
   - API call logging

## Development Workflow

### Setup & Installation
1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure Binance API credentials in `.env`
4. Run tests: `pytest tests/`

### CLI Usage Patterns
```bash
# Market Orders
python src/market_orders.py BTCUSDT BUY 0.01

# Limit Orders
python src/limit_orders.py BTCUSDT SELL 0.01 35000

# Advanced Orders
python src/advanced/oco.py BTCUSDT BUY 0.01 34000 35000 33000
```

## Project-Specific Patterns

### Error Handling
1. All API interactions are wrapped in try-except blocks
2. Network errors trigger automatic retries with exponential backoff
3. Order validation failures are logged with detailed context

### Logging Pattern
```python
logger.info({
    "action": "place_order",
    "order_type": "MARKET",
    "symbol": symbol,
    "side": side,
    "quantity": quantity,
    "timestamp": timestamp
})
```

### Configuration Management
- Environment variables for sensitive data
- `config.py` for static configuration
- Runtime configuration via CLI arguments

## Integration Points

### Binance API
- Uses USDT-M Futures API endpoints
- Default testnet environment for development
- Production mode requires explicit configuration

### Data Sources
- Historical data from provided Google Drive link
- Fear & Greed Index integration (bonus feature)
- Real-time market data via WebSocket

## Files & Directories

```
src/                - Core source code
├── base_order.py   - Base class for all order types
├── market_orders.py- Market order implementation
├── limit_orders.py - Limit order implementation
├── advanced/       - Advanced order types
│   ├── oco.py     - One-Cancels-the-Other orders
│   ├── twap.py    - Time-Weighted Average Price
│   ├── grid.py    - Grid trading strategy
│   └── stop_limit.py - Stop-limit orders
├── utils/
│   ├── validation.py - Input validation
│   └── logging.py    - Logging configuration
tests/              - Test suite
bot.log             - Application logs
report.pdf          - Implementation analysis
README.md           - Setup and usage guide
```