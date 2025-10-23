import sys
from base_order import BaseOrder
import structlog

logger = structlog.get_logger()

class MarketOrder(BaseOrder):
    def place_order(self, symbol: str, side: str, quantity: float):
        """
        Place a market order

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            side: Order side ('BUY' or 'SELL')
            quantity: Order quantity
        """
        # Validate inputs
        if not self._validate_symbol(symbol):
            raise ValueError(f"Invalid symbol: {symbol}")
        
        if not self._validate_quantity(symbol, quantity):
            raise ValueError(f"Invalid quantity: {quantity}")
            
        order_params = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": quantity
        }

        try:
            return self._execute_order(self.client.futures_create_order, **order_params)
        except Exception as e:
            logger.error(f"Failed to place market order: {str(e)}")
            raise

def main():
    if len(sys.argv) != 4:
        print("Usage: python market_orders.py <symbol> <side> <quantity>")
        print("Example: python market_orders.py BTCUSDT BUY 0.01")
        sys.exit(1)
        
    symbol = sys.argv[1].upper()
    side = sys.argv[2].upper()
    quantity = float(sys.argv[3])
    
    try:
        market_order = MarketOrder()
        result = market_order.place_order(symbol, side, quantity)
        print(f"Order placed successfully: {result}")
    except Exception as e:
        print(f"Error placing order: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()