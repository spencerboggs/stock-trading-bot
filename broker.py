"""
Broker integration module for order execution.
Currently supports Alpaca paper trading API with modular architecture for easy extension.
"""

import logging
from typing import Optional, Dict
from alpaca_trade_api.rest import REST, TimeFrame
from alpaca_trade_api.common import URL
from config import ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL, MAX_POSITION_SIZE
from utils import check_risk, log_trade

logger = logging.getLogger(__name__)


class Broker:
    """Base broker class for modular broker integration."""
    
    def __init__(self):
        self.api = None
    
    def get_position(self, symbol: str) -> int:
        """Get current position size for a symbol."""
        raise NotImplementedError
    
    def get_account_info(self) -> Dict:
        """Get account information (cash, equity, etc.)."""
        raise NotImplementedError
    
    def execute_order(self, symbol: str, qty: int, side: str, order_type: str = "market") -> bool:
        """Execute a trade order."""
        raise NotImplementedError
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current market price for a symbol."""
        raise NotImplementedError


class AlpacaBroker(Broker):
    """Alpaca paper trading broker implementation."""
    
    def __init__(self):
        super().__init__()
        try:
            self.api = REST(
                ALPACA_API_KEY,
                ALPACA_SECRET_KEY,
                base_url=ALPACA_BASE_URL,
                api_version='v2'
            )
            logger.info("Alpaca broker initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Alpaca broker: {e}")
            raise
    
    def get_position(self, symbol: str) -> int:
        """Get current position size for a symbol."""
        try:
            position = self.api.get_position(symbol)
            return int(position.qty)
        except Exception as e:
            # Position doesn't exist (no holdings)
            if "does not exist" in str(e) or "404" in str(e):
                return 0
            logger.warning(f"Error getting position for {symbol}: {e}")
            return 0
    
    def get_account_info(self) -> Dict:
        """Get account information."""
        try:
            account = self.api.get_account()
            return {
                "cash": float(account.cash),
                "equity": float(account.equity),
                "buying_power": float(account.buying_power),
                "portfolio_value": float(account.portfolio_value)
            }
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return {}
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current market price for a symbol."""
        try:
            bars = self.api.get_latest_bar(symbol)
            return float(bars.c)
        except Exception as e:
            logger.error(f"Error getting current price for {symbol}: {e}")
            return None
    
    def execute_order(self, symbol: str, qty: int, side: str, order_type: str = "market", 
                     time_in_force: str = "day") -> bool:
        """
        Execute a trade order with risk checks.
        
        Args:
            symbol: Stock symbol
            qty: Quantity of shares
            side: 'buy' or 'sell'
            order_type: Order type (default: 'market')
            time_in_force: Time in force (default: 'day')
            
        Returns:
            True if order executed successfully, False otherwise
        """
        try:
            # Get current position for risk check
            current_position = self.get_position(symbol)
            
            # Risk check: don't exceed max position size
            if not check_risk(current_position, MAX_POSITION_SIZE):
                logger.warning(f"Risk check failed for {symbol}: position {current_position}, max {MAX_POSITION_SIZE}")
                return False
            
            # Adjust quantity based on current position
            if side.lower() == "buy":
                new_position = current_position + qty
                if new_position > MAX_POSITION_SIZE:
                    qty = MAX_POSITION_SIZE - current_position
                    if qty <= 0:
                        logger.warning(f"Cannot buy {symbol}: would exceed max position")
                        return False
            elif side.lower() == "sell":
                # Can't sell more than we own
                if qty > current_position:
                    qty = current_position
                if qty <= 0:
                    logger.warning(f"Cannot sell {symbol}: no position to sell")
                    return False
            
            # Execute order
            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side=side.lower(),
                type=order_type.lower(),
                time_in_force=time_in_force
            )
            
            # Get execution price
            price = self.get_current_price(symbol)
            if price:
                log_trade(side.upper(), symbol, qty, price, f"Order ID: {order.id}")
            
            logger.info(f"Order executed: {side.upper()} {qty} {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error executing order for {symbol}: {e}")
            return False
    
    def get_historical_bars(self, symbol: str, timeframe: TimeFrame = TimeFrame.Minute, 
                           limit: int = 100) -> Optional:
        """Get historical bars for backtesting or analysis."""
        try:
            bars = self.api.get_bars(symbol, timeframe, limit=limit).df
            return bars
        except Exception as e:
            logger.error(f"Error getting historical bars for {symbol}: {e}")
            return None


# Factory function to get broker instance
def get_broker(broker_type: str = "alpaca") -> Broker:
    """
    Factory function to get broker instance.
    Easy to extend for other brokers (Interactive Brokers, TD Ameritrade, etc.)
    """
    if broker_type.lower() == "alpaca":
        return AlpacaBroker()
    else:
        raise ValueError(f"Unknown broker type: {broker_type}")
