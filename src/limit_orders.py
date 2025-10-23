import sys
import math
import structlog
from base_order import BaseOrder

logger = structlog.get_logger()


class LimitOrder(BaseOrder):

    def _validate_price(self, symbol: str, price: float) -> bool:
        """Validate if the price meets symbol's range and tick size requirements."""
        try:
            info = self.client.futures_exchange_info()
            symbol_info = next(s for s in info['symbols'] if s['symbol'] == symbol)
            
            # Check against price filter
            price_filter = next(f for f in symbol_info['filters'] if f['filterType'] == 'PRICE_FILTER')
            min_price = float(price_filter['minPrice'])
            max_price = float(price_filter['maxPrice'])
            tick_size = float(price_filter['tickSize'])

            # 1. Check Price Range
            if not (min_price <= price <= max_price):
                logger.error("price_validation_failed_range",
                           min_price=min_price,
                           max_price=max_price,
                           given_price=price)
                return False

            # 2. Check Price Tick Size
            # Round to the nearest tick size
            precision = int(round(-math.log10(tick_size)))
            rounded_price = round(price / tick_size) * tick_size
            rounded_price = float(f"%.{precision}f" % rounded_price)

            if rounded_price != price:
                logger.error("price_validation_failed_tick_size",
                           tick_size=tick_size,
                           given_price=price,
                           suggested_price=rounded_price)
                return False

            return True

        except Exception as e:
            logger.error("price_validation_failed_exception", error=str(e))
            return False

    def _format_price(self, symbol: str, price: float) -> float:
        """Format price according to symbol's tick size."""
        try:
            info = self.client.futures_exchange_info()
            symbol_info = next(s for s in info['symbols'] if s['symbol'] == symbol)
            price_filter = next(f for f in symbol_info['filters'] if f['filterType'] == 'PRICE_FILTER')
            tick_size = float(price_filter['tickSize'])
            
            precision = int(round(-math.log10(tick_size)))
            rounded_price = round(price / tick_size) * tick_size
            formatted_price = float(f"%.{precision}f" % rounded_price)
            
            if price != formatted_price:
                logger.info("formatting_price",
                            original=price,
                            formatted=formatted_price,
                            tick_size=tick_size)
            
            return formatted_price
        except Exception as e:
            logger.error("price_formatting_failed", error=str(e))
            raise

    def place_order(self, symbol: str, side: str, quantity: float, price: float = None):
        """
        Place a limit order.
        Price will be auto-calculated if not provided, and
        auto-formatted to meet tick size requirements.
        """
        # Validate inputs
        if not self._validate_symbol(symbol):
            raise ValueError(f"Invalid symbol: {symbol}")

        if not self._validate_quantity(symbol, quantity):
            raise ValueError(f"Invalid quantity: {quantity}")

        # If price is not provided, calculate it
        if price is None:
            logger.info("Price not provided, calculating optimal limit price...")
            prices = self.calculate_order_prices(symbol, side)
            price = prices['limit_price']
            logger.info(f"Calculated limit price: {price}")
        
        # Format price according to tick size
        formatted_price = self._format_price(symbol, price)
        
        # Validate formatted price (checks min/max range and confirms tick size)
        if not self._validate_price(symbol, formatted_price):
            raise ValueError(f"Invalid price {formatted_price} (formatted from {price}) for {symbol}")

        order_params = {
            "symbol": symbol,
            "side": side,
            "type": "LIMIT",
            "timeInForce": "GTC",  # Good Till Cancel
            "quantity": quantity,
            "price": formatted_price
        }

        try:
            return self._execute_order(self.client.futures_create_order, **order_params)
        except Exception as e:
            logger.error(f"Failed to place limit order: {str(e)}")
            raise


def main():
    if len(sys.argv) < 4 or len(sys.argv) > 5:
        print("Usage: python limit_orders.py <symbol> <side> <quantity> [price]")
        print("Example (with price): python limit_orders.py BTCUSDT SELL 0.01 35000.123")
        print("Example (auto-price): python limit_orders.py BTCUSDT BUY 0.01")
        sys.exit(1)
        
    symbol = sys.argv[1].upper()
    side = sys.argv[2].upper()
    quantity = float(sys.argv[3])
    # Set price to None if not provided
    price = float(sys.argv[4]) if len(sys.argv) == 5 else None
    
    try:
        limit_order = LimitOrder()
        
        # Print helpful info about tick size
        info = limit_order.client.futures_exchange_info()
        symbol_info = next(s for s in info['symbols'] if s['symbol'] == symbol)
        price_filter = next(f for f in symbol_info['filters'] if f['filterType'] == 'PRICE_FILTER')
        print(f"--- Info: Price for {symbol} must be a multiple of {price_filter['tickSize']} (will be auto-formatted) ---")
        
        result = limit_order.place_order(symbol, side, quantity, price)
        print(f"Order placed successfully: {result}")
        
    except Exception as e:
        print(f"Error placing order: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()