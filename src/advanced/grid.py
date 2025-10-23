import sys
import time
from ..base_order import BaseOrder
import structlog
from threading import Thread
from typing import List, Dict
import json

logger = structlog.get_logger()

class GridOrder(BaseOrder):
    def __init__(self):
        super().__init__()
        self.active_grids = {}  # Track active grid orders

    def _calculate_grid_levels(self, lower_price: float, upper_price: float, num_grids: int) -> List[float]:
        """Calculate price levels for the grid"""
        grid_size = (upper_price - lower_price) / (num_grids - 1)
        return [lower_price + i * grid_size for i in range(num_grids)]

    def _place_grid_orders(self, symbol: str, levels: List[float], quantity: float, grid_id: str):
        """Place the initial grid orders"""
        current_price = self.get_market_price(symbol)
        orders = []

        try:
            for level in levels:
                # Determine order side based on price level
                side = "BUY" if level < current_price else "SELL"
                
                order_params = {
                    "symbol": symbol,
                    "side": side,
                    "type": "LIMIT",
                    "timeInForce": "GTC",
                    "quantity": quantity,
                    "price": level
                }
                
                response = self._execute_order(self.client.futures_create_order, **order_params)
                orders.append({
                    "orderId": response["orderId"],
                    "side": side,
                    "price": level,
                    "quantity": quantity
                })
                
                logger.info("Grid order placed", 
                          grid_id=grid_id,
                          price=level,
                          side=side)

            return orders
        except Exception as e:
            logger.error(f"Failed to place grid orders: {str(e)}")
            raise

    def _monitor_grid(self, symbol: str, grid_id: str, quantity: float):
        """Monitor and maintain the grid orders"""
        while grid_id in self.active_grids:
            try:
                # Get all open orders
                open_orders = self.client.futures_get_open_orders(symbol=symbol)
                filled_orders = []
                
                # Check for filled orders
                for grid_order in self.active_grids[grid_id]["orders"]:
                    order_id = grid_order["orderId"]
                    if not any(o["orderId"] == order_id for o in open_orders):
                        # Order was filled, place opposite order
                        new_side = "SELL" if grid_order["side"] == "BUY" else "BUY"
                        new_order_params = {
                            "symbol": symbol,
                            "side": new_side,
                            "type": "LIMIT",
                            "timeInForce": "GTC",
                            "quantity": quantity,
                            "price": grid_order["price"]
                        }
                        
                        response = self._execute_order(
                            self.client.futures_create_order,
                            **new_order_params
                        )
                        
                        # Update the grid orders
                        filled_orders.append(grid_order)
                        grid_order.update({
                            "orderId": response["orderId"],
                            "side": new_side
                        })
                        
                        logger.info("Grid order filled and replaced",
                                  grid_id=grid_id,
                                  filled_side=grid_order["side"],
                                  new_side=new_side,
                                  price=grid_order["price"])
                
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error monitoring grid: {str(e)}")
                time.sleep(10)  # Wait longer on error

        logger.info("Grid monitoring stopped", grid_id=grid_id)

    def place_order(self, symbol: str, lower_price: float, upper_price: float,
                   num_grids: int, quantity_per_grid: float) -> str:
        """
        Create a grid trading setup with multiple buy and sell orders at regular price intervals

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            lower_price: Lower price bound for the grid
            upper_price: Upper price bound for the grid
            num_grids: Number of price levels in the grid
            quantity_per_grid: Quantity for each grid order
        """
        # Validate inputs
        if not self._validate_symbol(symbol):
            raise ValueError(f"Invalid symbol: {symbol}")
        
        if not self._validate_quantity(symbol, quantity_per_grid):
            raise ValueError(f"Invalid quantity per grid: {quantity_per_grid}")
            
        # Generate grid levels
        price_levels = self._calculate_grid_levels(lower_price, upper_price, num_grids)
        
        # Validate each price level
        for price in price_levels:
            if not self._validate_price(symbol, price):
                raise ValueError(f"Invalid grid price level: {price}")

        # Generate unique grid ID
        grid_id = f"GRID_{int(time.time())}"
        
        # Place initial grid orders
        grid_orders = self._place_grid_orders(symbol, price_levels, quantity_per_grid, grid_id)
        
        # Store grid configuration
        self.active_grids[grid_id] = {
            "symbol": symbol,
            "lower_price": lower_price,
            "upper_price": upper_price,
            "num_grids": num_grids,
            "quantity_per_grid": quantity_per_grid,
            "orders": grid_orders
        }
        
        # Start grid monitoring in a separate thread
        monitor_thread = Thread(
            target=self._monitor_grid,
            args=(symbol, grid_id, quantity_per_grid)
        )
        monitor_thread.daemon = True
        monitor_thread.start()
        
        logger.info("Grid trading started",
                   grid_id=grid_id,
                   symbol=symbol,
                   lower_price=lower_price,
                   upper_price=upper_price,
                   num_grids=num_grids)
        
        return grid_id

    def cancel_grid(self, grid_id: str) -> bool:
        """Cancel all orders in a grid and stop monitoring"""
        if grid_id not in self.active_grids:
            return False
            
        grid = self.active_grids[grid_id]
        
        try:
            # Cancel all open orders for the symbol
            self.client.futures_cancel_all_open_orders(symbol=grid["symbol"])
            
            # Remove grid from active grids
            self.active_grids.pop(grid_id)
            
            logger.info("Grid trading cancelled", grid_id=grid_id)
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel grid: {str(e)}")
            return False

def main():
    if len(sys.argv) != 6:
        print("Usage: python grid.py <symbol> <lower_price> <upper_price> <num_grids> <quantity_per_grid>")
        print("Example: python grid.py BTCUSDT 30000 40000 10 0.001")
        sys.exit(1)
        
    symbol = sys.argv[1].upper()
    lower_price = float(sys.argv[2])
    upper_price = float(sys.argv[3])
    num_grids = int(sys.argv[4])
    quantity_per_grid = float(sys.argv[5])
    
    try:
        grid_order = GridOrder()
        grid_id = grid_order.place_order(
            symbol, lower_price, upper_price,
            num_grids, quantity_per_grid
        )
        print(f"Grid trading started with ID: {grid_id}")
        print("Grid orders are being monitored. Check bot.log for updates.")
        print(f"To cancel the grid, record this ID: {grid_id}")
    except Exception as e:
        print(f"Error setting up grid trading: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()