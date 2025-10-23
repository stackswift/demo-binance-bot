import sys
import math
sys.path.append('/workspaces/demo-binance-bot/src')
from base_order import BaseOrder
import structlog

logger = structlog.get_logger()

class OCOOrder(BaseOrder):
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

    def place_order(self, symbol: str, side: str, quantity: str, price: str = None) -> dict:
        """
        Implement the abstract method from BaseOrder.
        For OCO orders, we don't use this method directly.
        """
        raise NotImplementedError("OCO orders require using place_oco_orders() method")

    def place_order(self, symbol: str, side: str, quantity: str, take_profit_price: float, stop_loss_price: float):
        """Place an OCO order with take profit and stop loss levels.

        Args:
            symbol (str): Trading pair symbol (e.g., 'BTCUSDT')
            side (str): Order side ('BUY' or 'SELL')
            quantity (str): Order quantity
            take_profit_price (float): Price level for take profit order
            stop_loss_price (float): Price level for stop loss order
        """
        # First cancel any existing orders
        logger.info("Cancelling existing orders before placing new ones")
        self.client.futures_cancel_all_open_orders(symbol=symbol)
        # Validate inputs
        if not self._validate_symbol(symbol):
            raise ValueError(f"Invalid symbol: {symbol}")
        
        if not self._validate_quantity(symbol, quantity):
            raise ValueError(f"Invalid quantity: {quantity}")

        # Check minimum notional value
        current_price = float(self.client.futures_symbol_ticker(symbol=symbol)['price'])
        notional_value = quantity * current_price
        min_notional = 100  # Minimum notional value in USDT for Binance Futures
        
        if notional_value < min_notional:
            min_qty = min_notional / current_price
            raise ValueError(f"Order value ({notional_value:.2f} USDT) is below minimum ({min_notional} USDT). " +
                           f"Minimum quantity at current price: {min_qty:.3f} {symbol[:-4]}")

        # Check position
        positions = self.client.futures_position_information(symbol=symbol)
        position = next((p for p in positions if p['symbol'] == symbol), None)
        if position:
            pos_amt = float(position['positionAmt'])
            if pos_amt == 0:
                raise ValueError("No position to close. Place a position first before setting OCO orders.")
            if (side == "SELL" and pos_amt < 0) or (side == "BUY" and pos_amt > 0):
                raise ValueError(f"Cannot place {side} OCO orders against an existing {side} position")

        # Format prices
        formatted_take_profit = self._format_price(symbol, take_profit_price)
        formatted_stop_loss = self._format_price(symbol, stop_loss_price)

        # Validate prices
        if not self._validate_price(symbol, formatted_take_profit):
            raise ValueError(f"Invalid take profit price: {take_profit_price}")
        if not self._validate_price(symbol, formatted_stop_loss):
            raise ValueError(f"Invalid stop loss price: {stop_loss_price}")

        # Get the current position
        position = next((p for p in self.client.futures_position_information(symbol=symbol) 
                        if p['symbol'] == symbol), None)
        
        if not position or float(position['positionAmt']) == 0:
            raise ValueError("No position to set OCO orders for. Open a position first.")

        current_price = float(self.client.futures_symbol_ticker(symbol=symbol)['price'])
        position_size = float(position['positionAmt'])
        
        # For long positions (position_size > 0):
        # - Take profit should be above entry for profit
        # - Stop loss should be below entry to limit losses
        if position_size > 0:  # Long position
            if side != "SELL":
                raise ValueError("Must use SELL orders to close a long position")
            if formatted_take_profit <= current_price:
                raise ValueError(f"For closing longs: take profit ({formatted_take_profit}) must be above current price ({current_price})")
            if formatted_stop_loss >= current_price:
                raise ValueError(f"For closing longs: stop loss ({formatted_stop_loss}) must be below current price ({current_price})")
        else:  # Short position
            if side != "BUY":
                raise ValueError("Must use BUY orders to close a short position")
            if formatted_take_profit >= current_price:
                raise ValueError(f"For closing shorts: take profit ({formatted_take_profit}) must be below current price ({current_price})")
            if formatted_stop_loss <= current_price:
                raise ValueError(f"For closing shorts: stop loss ({formatted_stop_loss}) must be above current price ({current_price})")

        order_params = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "timeInForce": "GTC"  # Good till cancel
        }

        try:
            # Cancel any existing orders before placing new ones
            logger.info("Cancelling existing orders")
            self.client.futures_cancel_all_open_orders(symbol=symbol)
            # Cancel any existing orders for this symbol first
            try:
                self.client.futures_cancel_all_open_orders(symbol=symbol)
                logger.info("cancelled_existing_orders", symbol=symbol)
            except Exception as e:
                logger.warning("failed_to_cancel_orders", error=str(e))

            # Get position details
            position = next(p for p in self.client.futures_position_information(symbol=symbol) 
                          if p['symbol'] == symbol)
            position_amount = float(position['positionAmt'])
            
            # Validate that we aren't trying to reduce more than our position
            if abs(float(quantity)) > abs(position_amount):
                raise ValueError(f"Order quantity {quantity} is larger than position size {position_amount}")

            position_side = "SELL" if position_amount > 0 else "BUY"

            # Verify we're closing in the right direction
            if position_side != side:
                raise ValueError(f"Order side {side} doesn't match position side {position_side}")

            # For a long position (pos_amt > 0):
            # - Take profit is a limit sell above entry
            # - Stop loss is a stop market below entry
            if position_amount > 0:
                try:
                    # Take profit: Limit SELL order above current price
                    tp_order = self.client.futures_create_order(
                        symbol=symbol,
                        side="SELL",
                        type="LIMIT",
                        timeInForce="GTC",
                        price=formatted_take_profit,
                        quantity=float(quantity),  # Use the specified quantity
                        reduceOnly=True
                    )
                    logger.info("take_profit_order_executed", order_id=tp_order['orderId'])

                    # Stop loss: Stop SELL order below current price
                    sl_order = self.client.futures_create_order(
                        symbol=symbol,
                        side="SELL",
                        type="STOP_MARKET",
                        timeInForce="GTC",
                        stopPrice=formatted_stop_loss,
                        quantity=float(quantity),  # Use the specified quantity
                        reduceOnly=True,
                        workingType="MARK_PRICE"
                    )
                    logger.info("stop_loss_order_executed", order_id=sl_order['orderId'])

                    result = {
                        "take_profit": tp_order,
                        "stop_loss": sl_order
                    }
                    print("OCO orders placed successfully:")
                    print(f"Take Profit Order: {tp_order}")
                    print(f"Stop Loss Order: {sl_order}")
                    return result
                except Exception as e:
                    # If either order fails, cancel any successful orders
                    self.client.futures_cancel_all_open_orders(symbol=symbol)
                    raise
            else:
                # For a short position (pos_amt < 0):
                try:
                    # Take profit: Limit BUY order below current price
                    tp_order = self.client.futures_create_order(
                        symbol=symbol,
                        side="BUY",
                        type="LIMIT",
                        timeInForce="GTC",
                        price=formatted_take_profit,
                        quantity=float(quantity),  # Use the specified quantity
                        reduceOnly=True
                    )
                    logger.info("take_profit_order_executed", order_id=tp_order['orderId'])

                    # Stop loss: Stop BUY order above current price
                    sl_order = self.client.futures_create_order(
                        symbol=symbol,
                        side="BUY",
                        type="STOP_MARKET",
                        timeInForce="GTC", 
                        stopPrice=formatted_stop_loss,
                        quantity=float(quantity),  # Use the specified quantity
                        reduceOnly=True,
                        workingType="MARK_PRICE"
                    )
                    logger.info("stop_loss_order_executed", order_id=sl_order['orderId'])

                    orders = {
                        "take_profit": tp_order,
                        "stop_loss": sl_order
                    }

                    print("OCO orders placed successfully:")
                    print(f"Take Profit Order: {tp_order}")
                    print(f"Stop Loss Order: {sl_order}")

                    return orders
                except Exception as e:
                    # If either order fails, cancel any successful orders
                    self.client.futures_cancel_all_open_orders(symbol=symbol)
                    raise

                result = {
                    "take_profit": tp_order,
                    "stop_loss": sl_order
                }
            logger.info("stop_loss_order_executed", order_id=stop_result['orderId'])

            return {
                "take_profit": result,
                "stop_loss": stop_result
            }

        except Exception as e:
            logger.error(f"Failed to place OCO order: {str(e)}")
            raise

        try:
            return self._execute_order(self.client.futures_create_oco_order, **order_params)
        except Exception as e:
            logger.error(f"Failed to place OCO order: {str(e)}")
            raise

def main():
    if len(sys.argv) != 6:
        print("Usage: python oco.py <symbol> <side> <quantity> <take_profit_price> <stop_loss_price>")
        print("Example: python oco.py BTCUSDT SELL 0.001 108000 110000")
        sys.exit(1)
        
    symbol = sys.argv[1].upper()
    side = sys.argv[2].upper()
    quantity = float(sys.argv[3])
    take_profit_price = float(sys.argv[4])
    stop_loss_price = float(sys.argv[5])
    
    try:
        oco = OCOOrder()
        result = oco.place_order(symbol, side, quantity, take_profit_price, stop_loss_price)
        print(f"OCO orders placed successfully:")
        print(f"Take Profit Order: {result['take_profit']}")
        print(f"Stop Loss Order: {result['stop_loss']}")
    except Exception as e:
        print(f"Error placing OCO orders: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()