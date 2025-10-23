import os
import sys
import time
import logging
import requests
from abc import ABC, abstractmethod

import structlog
from binance.client import Client
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

# Load environment variables
load_dotenv()

# Configure logging
log_level = os.getenv('LOG_LEVEL', 'INFO')
log_file = os.getenv('LOG_FILE', 'bot.log')

# Configure standard logging
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Get logger instance
logger = structlog.get_logger()


class BaseOrder(ABC):

    def __init__(self):
        self.client = self._initialize_client()
        
    def _initialize_client(self):
        """Initialize Binance client with API credentials."""
        api_key = os.getenv('BINANCE_API_KEY')
        api_secret = os.getenv('BINANCE_API_SECRET')
        testnet = os.getenv('USE_TESTNET', 'false').lower() == 'true'
        
        if testnet:
            api_key = os.getenv('TESTNET_API_KEY', api_key)
            api_secret = os.getenv('TESTNET_API_SECRET', api_secret)
        
        if not api_key or not api_secret:
            raise ValueError("API credentials not found in environment variables")
        
        return Client(api_key, api_secret, testnet=testnet)

    def _validate_symbol(self, symbol: str) -> bool:
        """Validate if the trading pair exists."""
        try:
            info = self.client.futures_exchange_info()
            valid_symbols = [s['symbol'] for s in info['symbols']]
            return symbol in valid_symbols
        except Exception as e:
            logger.error("symbol_validation_failed", error=str(e))
            return False

    def _validate_quantity(self, symbol: str, quantity: float) -> bool:
        """Validate if the quantity meets symbol's requirements."""
        try:
            info = self.client.futures_exchange_info()
            symbol_info = next(s for s in info['symbols'] if s['symbol'] == symbol)
            
            # Check against lot size filter
            lot_size = next(f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE')
            min_qty = float(lot_size['minQty'])
            max_qty = float(lot_size['maxQty'])
            step_size = float(lot_size['stepSize'])

            if not (min_qty <= quantity <= max_qty):
                return False

            # Check if quantity is a multiple of step_size
            # Use precision check for floating point
            remainder = quantity % step_size
            return abs(remainder) < 1e-10
        
        except Exception as e:
            logger.error("quantity_validation_failed", error=str(e))
            return False

    def _log_order_success(self, response):
        """Log successful order execution."""
        logger.info(
            "order_executed",
            order_id=response.get('orderId'),
            symbol=response.get('symbol'),
            side=response.get('side'),
            type=response.get('type'),
            price=response.get('price'),
            quantity=response.get('origQty'),
            status=response.get('status'),
            timestamp=time.time()
        )
        
    def _log_order_error(self, error, params):
        """Log order execution error."""
        logger.error(
            "order_failed",
            error_code=error.code,
            error_message=error.message,
            parameters=params,
            timestamp=time.time()
        )

    def get_market_price(self, symbol):
        """Get current market price for a symbol"""
        try:
            ticker = self.client.futures_mark_price(symbol=symbol)
            logger.info(
                "price_fetch_success",
                symbol=symbol,
                price=ticker['markPrice']
            )
            return float(ticker['markPrice'])
        except BinanceAPIException as e:
            logger.error(
                "price_fetch_failed",
                symbol=symbol,
                error=str(e)
            )
            raise

    def calculate_order_prices(self, symbol, side, base_deviation=0.02):
        """
        Calculate appropriate prices for different order types based on current market price
        
        Args:
            symbol: Trading pair symbol
            side: BUY or SELL
            base_deviation: Price deviation from current price (default 2%)
        
        Returns:
            dict: Different price levels for various order types
        """
        current_price = self.get_market_price(symbol)
        
        # Calculate price levels based on side
        if side == "BUY":
            limit_price = round(current_price * (1 - base_deviation), 2)  # 2% below market
            stop_price = round(current_price * (1 + base_deviation), 2)   # 2% above market
            limit_maker_price = round(current_price * (1 - base_deviation * 1.5), 2)  # 3% below market
            stop_limit_price = round(current_price * (1 + base_deviation * 1.2), 2)   # 2.4% above market
        else:  # SELL
            limit_price = round(current_price * (1 + base_deviation), 2)  # 2% above market
            stop_price = round(current_price * (1 - base_deviation), 2)   # 2% below market
            limit_maker_price = round(current_price * (1 + base_deviation * 1.5), 2)  # 3% above market
            stop_limit_price = round(current_price * (1 - base_deviation * 1.2), 2)   # 2.4% below market

        logger.info(
            "price_levels_calculated",
            symbol=symbol,
            side=side,
            current_price=current_price,
            limit_price=limit_price,
            stop_price=stop_price,
            limit_maker_price=limit_maker_price,
            stop_limit_price=stop_limit_price
        )

        return {
            "current_price": current_price,
            "limit_price": limit_price,
            "stop_price": stop_price,
            "limit_maker_price": limit_maker_price,
            "stop_limit_price": stop_limit_price
        }

    def _execute_order(self, order_function, **kwargs):
        """Execute order without retry."""
        try:
            response = order_function(**kwargs)
            self._log_order_success(response)
            return response
        except BinanceAPIException as e:
            self._log_order_error(e, kwargs)
            raise
            
    @abstractmethod
    def place_order(self, *args, **kwargs):
        """Abstract method for placing orders. Must be implemented by subclasses."""
        pass