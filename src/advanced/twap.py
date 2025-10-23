import sys
import time
from ..base_order import BaseOrder
import structlog
from threading import Thread
from typing import Optional

logger = structlog.get_logger()

class TWAPOrder(BaseOrder):
    def __init__(self):
        super().__init__()
        self.active_orders = {}  # Track running TWAP orders

    def _execute_twap_chunks(self, symbol: str, side: str, total_quantity: float,
                           num_chunks: int, interval_minutes: int,
                           order_id: str):
        """Execute TWAP order chunks at regular intervals"""
        chunk_quantity = total_quantity / num_chunks
        
        for i in range(num_chunks):
            if order_id not in self.active_orders:
                logger.info("TWAP order cancelled", order_id=order_id)
                break

            try:
                order_params = {
                    "symbol": symbol,
                    "side": side,
                    "type": "MARKET",
                    "quantity": chunk_quantity
                }
                
                # Place the chunk order
                response = self._execute_order(self.client.futures_create_order, **order_params)
                
                logger.info("TWAP chunk executed", 
                          chunk_number=i+1,
                          total_chunks=num_chunks,
                          quantity=chunk_quantity,
                          order_id=order_id)

                # Sleep for the interval if not the last chunk
                if i < num_chunks - 1:
                    time.sleep(interval_minutes * 60)
                    
            except Exception as e:
                logger.error(f"Failed to execute TWAP chunk: {str(e)}")
                self.active_orders.pop(order_id, None)
                raise

        # TWAP execution completed
        self.active_orders.pop(order_id, None)
        logger.info("TWAP order completed", order_id=order_id)

    def place_order(self, symbol: str, side: str, total_quantity: float,
                   num_chunks: int, interval_minutes: int) -> str:
        """
        Place a TWAP (Time-Weighted Average Price) order that splits a large order into smaller chunks
        executed at regular intervals

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            side: Order side ('BUY' or 'SELL')
            total_quantity: Total order quantity
            num_chunks: Number of chunks to split the order into
            interval_minutes: Minutes between each chunk execution
        """
        # Validate inputs
        if not self._validate_symbol(symbol):
            raise ValueError(f"Invalid symbol: {symbol}")
        
        if not self._validate_quantity(symbol, total_quantity):
            raise ValueError(f"Invalid total quantity: {total_quantity}")

        # Calculate chunk size and validate
        chunk_quantity = total_quantity / num_chunks
        if not self._validate_quantity(symbol, chunk_quantity):
            raise ValueError(f"Invalid chunk quantity: {chunk_quantity}. Try increasing num_chunks.")

        # Generate unique order ID
        order_id = f"TWAP_{int(time.time())}"
        self.active_orders[order_id] = True

        # Start TWAP execution in a separate thread
        twap_thread = Thread(
            target=self._execute_twap_chunks,
            args=(symbol, side, total_quantity, num_chunks, interval_minutes, order_id)
        )
        twap_thread.start()

        logger.info("TWAP order started", 
                   order_id=order_id,
                   total_quantity=total_quantity,
                   num_chunks=num_chunks,
                   interval_minutes=interval_minutes)
        
        return order_id

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a running TWAP order"""
        if order_id in self.active_orders:
            self.active_orders.pop(order_id)
            logger.info("TWAP order cancelled", order_id=order_id)
            return True
        return False

def main():
    if len(sys.argv) != 6:
        print("Usage: python twap.py <symbol> <side> <total_quantity> <num_chunks> <interval_minutes>")
        print("Example: python twap.py BTCUSDT BUY 0.1 10 5")
        sys.exit(1)
        
    symbol = sys.argv[1].upper()
    side = sys.argv[2].upper()
    total_quantity = float(sys.argv[3])
    num_chunks = int(sys.argv[4])
    interval_minutes = int(sys.argv[5])
    
    try:
        twap_order = TWAPOrder()
        order_id = twap_order.place_order(symbol, side, total_quantity, num_chunks, interval_minutes)
        print(f"TWAP order started with ID: {order_id}")
        print("Order will execute in chunks. Check bot.log for progress.")
    except Exception as e:
        print(f"Error placing TWAP order: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()