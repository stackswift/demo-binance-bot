import sys
import math
import time
sys.path.append('/workspaces/demo-binance-bot/src')
from base_order import BaseOrder
import structlog

logger = structlog.get_logger()

class StopLimitOrder(BaseOrder):
    def _validate_price(self, symbol: str, price: float) -> bool:
        """Validate if the price meets symbol's requirements."""
        try:
            info = self.client.futures_exchange_info()
            symbol_info = next(s for s in info['symbols'] if s['symbol'] == symbol)
            
            # Check against price filter
            price_filter = next(f for f in symbol_info['filters'] if f['filterType'] == 'PRICE_FILTER')
            min_price = float(price_filter['minPrice'])
            max_price = float(price_filter['maxPrice'])
            tick_size = float(price_filter['tickSize'])

            if not (min_price <= price <= max_price):
                logger.error("price_validation_failed_range",
                           min_price=min_price,
                           max_price=max_price,
                           given_price=price)
                return False

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
            logger.error("price_validation_failed", error=str(e))
            return False

    def _format_price(self, symbol: str, price: float) -> float:
        """Format price according to symbol's tick size."""
        info = self.client.futures_exchange_info()
        symbol_info = next(s for s in info['symbols'] if s['symbol'] == symbol)
        price_filter = next(f for f in symbol_info['filters'] if f['filterType'] == 'PRICE_FILTER')
        tick_size = float(price_filter['tickSize'])
        precision = int(round(-math.log10(tick_size)))
        rounded_price = round(price / tick_size) * tick_size
        return float(f"%.{precision}f" % rounded_price)

    def get_market_price(self, symbol: str) -> float:
        """Get current market price for a symbol."""
        ticker = self.client.futures_symbol_ticker(symbol=symbol)
        return float(ticker['price'])
    def place_order(self, symbol: str, side: str, quantity: float, stop_price: float = None, limit_price: float = None):
        """
        Place a stop-limit order

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            side: Order side ('BUY' or 'SELL')
            quantity: Order quantity
            stop_price: Price at which the limit order is triggered
            limit_price: Price for the limit order once triggered
        """
        # Validate inputs
        if not self._validate_symbol(symbol):
            raise ValueError(f"Invalid symbol: {symbol}")
        
        if not self._validate_quantity(symbol, quantity):
            raise ValueError(f"Invalid quantity: {quantity}")

        # Validate both prices are provided
        if stop_price is None or limit_price is None:
            raise ValueError("Both stop_price and limit_price must be provided for stop-limit orders")

        # Format prices to correct precision
        formatted_stop_price = self._format_price(symbol, stop_price)
        formatted_limit_price = self._format_price(symbol, limit_price)

        # Validate prices
        if not self._validate_price(symbol, formatted_stop_price):
            raise ValueError(f"Invalid stop price: {stop_price}")
        if not self._validate_price(symbol, formatted_limit_price):
            raise ValueError(f"Invalid limit price: {limit_price}")
        
        # Validate stop price is above limit price for sell orders and below for buy orders
        if side == "SELL" and formatted_stop_price > formatted_limit_price:
            raise ValueError(f"For SELL orders, stop price ({formatted_stop_price}) must be below limit price ({formatted_limit_price})")
        elif side == "BUY" and formatted_stop_price < formatted_limit_price:
            raise ValueError(f"For BUY orders, stop price ({formatted_stop_price}) must be above limit price ({formatted_limit_price})")

        order_params = {
            "symbol": symbol,
            "side": side,
            "type": "STOP",
            "timeInForce": "GTC",
            "quantity": quantity,
            "price": formatted_limit_price,  # Price for the limit order
            "stopPrice": formatted_stop_price  # Price to trigger the order
        }

        try:
            # Direct order placement without retry
            result = self.client.futures_create_order(**order_params)
            logger.info("order_executed", order_id=result.get('orderId'), symbol=symbol,
                       side=side, type="STOP", price=formatted_limit_price,
                       quantity=quantity, status=result.get('status'))
            return result
        except BinanceAPIException as e:
            logger.error("Failed to place stop-limit order", error_code=e.code,
                        error_message=e.message, parameters=order_params)
            raise
        except Exception as e:
            logger.error(f"Failed to place stop-limit order: {str(e)}")
            raise

def main():
    if len(sys.argv) != 6:
        print("Usage: python stop_limit.py <symbol> <side> <quantity> <stop_price> <limit_price>")
        print("Example: python stop_limit.py BTCUSDT SELL 0.01 35000 34800")
        sys.exit(1)

    symbol = sys.argv[1].upper()
    side = sys.argv[2].upper()
    quantity = float(sys.argv[3])
    stop_price = float(sys.argv[4])
    limit_price = float(sys.argv[5])

    order = StopLimitOrder()
    try:
        result = order.place_order(symbol, side, quantity, stop_price, limit_price)
        print(f"Order placed successfully: {result}")
    except Exception as e:
        print(f"Error placing order: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()