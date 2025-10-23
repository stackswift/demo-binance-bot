import sys
from ..base_order import BaseOrder
import structlog

logger = structlog.get_logger()

class OCOOrder(BaseOrder):
    def place_order(self, symbol: str, side: str, quantity: float, 
                   price: float = None, stop_price: float = None, stop_limit_price: float = None):
        """
        Place an OCO (One-Cancels-the-Other) order that combines a limit order with a stop-limit order

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            side: Order side ('BUY' or 'SELL')
            quantity: Order quantity
            price: Price for the limit order
            stop_price: Stop price to trigger the stop-limit order
            stop_limit_price: Limit price for the stop order
        """
        # Validate inputs
        if not self._validate_symbol(symbol):
            raise ValueError(f"Invalid symbol: {symbol}")
        
        if not self._validate_quantity(symbol, quantity):
            raise ValueError(f"Invalid quantity: {quantity}")

        # If prices not provided, calculate them based on current market price
        if price is None or stop_price is None or stop_limit_price is None:
            prices = self.calculate_order_prices(symbol, side)
            price = prices['limit_price'] if price is None else price
            stop_price = prices['stop_price'] if stop_price is None else stop_price
            stop_limit_price = prices['stop_limit_price'] if stop_limit_price is None else stop_limit_price

        # Validate prices
        if not self._validate_price(symbol, price):
            raise ValueError(f"Invalid price: {price}")
        if not self._validate_price(symbol, stop_limit_price):
            raise ValueError(f"Invalid stop limit price: {stop_limit_price}")

        order_params = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,  # Take profit price
            "stopPrice": stop_price,  # Stop loss trigger price
            "stopLimitPrice": stop_limit_price,  # Stop loss limit price
            "stopLimitTimeInForce": "GTC"  # Good till cancel
        }

        try:
            return self._execute_order(self.client.futures_create_oco_order, **order_params)
        except Exception as e:
            logger.error(f"Failed to place OCO order: {str(e)}")
            raise

def main():
    if len(sys.argv) != 7:
        print("Usage: python oco.py <symbol> <side> <quantity> <price> <stop_price> <stop_limit_price>")
        print("Example: python oco.py BTCUSDT BUY 0.01 34000 35000 35100")
        sys.exit(1)
        
    symbol = sys.argv[1].upper()
    side = sys.argv[2].upper()
    quantity = float(sys.argv[3])
    price = float(sys.argv[4])
    stop_price = float(sys.argv[5])
    stop_limit_price = float(sys.argv[6])
    
    try:
        oco_order = OCOOrder()
        result = oco_order.place_order(symbol, side, quantity, price, stop_price, stop_limit_price)
        print(f"Order placed successfully: {result}")
    except Exception as e:
        print(f"Error placing order: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()