"""
Portfolio management module for tracking positions, cash, and PnL across multiple symbols.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from config import INITIAL_CASH, STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT
from utils import calculate_pnl, format_currency

logger = logging.getLogger(__name__)


class Position:
    """
    Represents a position in a single symbol.
    Uses ATR-based stops and trailing stops for better risk management.
    """
    
    def __init__(self, symbol: str, quantity: int, entry_price: float, atr: float = None):
        self.symbol = symbol
        self.quantity = quantity
        self.entry_price = entry_price
        self.entry_time = datetime.now()
        self.current_price = entry_price
        
        # ATR-based stop loss (2-4× ATR from entry)
        self.atr = atr or (entry_price * 0.02)  # Default to 2% if no ATR
        self.atr_multiplier = 2.5  # Use 2.5× ATR for stop (research says 2-4×)
        
        # Trailing stop (moves up as price moves in our favor)
        if quantity > 0:  # Long position
            self.stop_loss_price = entry_price - (self.atr * self.atr_multiplier)
            self.highest_price = entry_price  # Track highest price for trailing stop
        else:  # Short position
            self.stop_loss_price = entry_price + (self.atr * self.atr_multiplier)
            self.lowest_price = entry_price  # Track lowest price for trailing stop
    
    def update_price(self, price: float):
        """Update current price and trailing stop."""
        self.current_price = price
        
        if self.quantity > 0:  # Long position
            # Update highest price
            if price > self.highest_price:
                self.highest_price = price
                # Trail stop loss: keep it 2× ATR below highest price
                new_stop = self.highest_price - (self.atr * self.atr_multiplier)
                # Only move stop up, never down
                if new_stop > self.stop_loss_price:
                    self.stop_loss_price = new_stop
        else:  # Short position
            # Update lowest price
            if price < self.lowest_price:
                self.lowest_price = price
                # Trail stop loss: keep it 2× ATR above lowest price
                new_stop = self.lowest_price + (self.atr * self.atr_multiplier)
                # Only move stop down, never up
                if new_stop < self.stop_loss_price:
                    self.stop_loss_price = new_stop
    
    def get_pnl(self) -> float:
        """Calculate current profit/loss."""
        return calculate_pnl(self.entry_price, self.current_price, self.quantity)
    
    def get_pnl_percent(self) -> float:
        """Calculate PnL as percentage."""
        if self.entry_price == 0:
            return 0.0
        return ((self.current_price - self.entry_price) / self.entry_price) * 100
    
    def check_stop_loss(self) -> bool:
        """
        Check if ATR-based stop loss is triggered.
        Uses trailing stop for long positions (stops move up as price rises).
        """
        if self.quantity > 0:  # Long position
            # Stop triggered if price falls below trailing stop
            return self.current_price <= self.stop_loss_price
        elif self.quantity < 0:  # Short position
            # Stop triggered if price rises above trailing stop
            return self.current_price >= self.stop_loss_price
        return False
    
    def check_take_profit(self) -> bool:
        """
        REMOVED: We don't use fixed take profit anymore.
        Trailing stops let winners run - we exit when stop is hit.
        This method kept for compatibility but always returns False.
        """
        # Trailing stops handle exits - no fixed take profit
        return False
    
    def __repr__(self):
        return f"Position({self.symbol}, qty={self.quantity}, entry=${self.entry_price:.2f}, current=${self.current_price:.2f}, stop=${self.stop_loss_price:.2f}, PnL={self.get_pnl():.2f})"


class Portfolio:
    """Manages portfolio of positions across multiple symbols."""
    
    def __init__(self, initial_cash: float = None):
        self.initial_cash = initial_cash or INITIAL_CASH
        self.cash = self.initial_cash
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[Dict] = []
    
    def add_position(self, symbol: str, quantity: int, price: float, atr: float = None):
        """Add or update a position with ATR for dynamic stops."""
        if symbol in self.positions:
            # Update existing position
            pos = self.positions[symbol]
            # Average entry price calculation
            total_cost = (pos.entry_price * pos.quantity) + (price * quantity)
            total_quantity = pos.quantity + quantity
            if total_quantity != 0:
                pos.entry_price = total_cost / total_quantity
            pos.quantity += quantity
            # Update ATR if provided (use average if both have ATR)
            if atr is not None:
                pos.atr = (pos.atr + atr) / 2
        else:
            # New position with ATR
            self.positions[symbol] = Position(symbol, quantity, price, atr=atr)
        
        # Update cash (simplified - assumes cash is managed externally in live trading)
        cost = quantity * price
        if quantity > 0:  # Buying
            self.cash -= cost
        else:  # Selling
            self.cash += abs(cost)
        
        # Log trade
        self.trade_history.append({
            "timestamp": datetime.now(),
            "symbol": symbol,
            "action": "BUY" if quantity > 0 else "SELL",
            "quantity": abs(quantity),
            "price": price
        })
    
    def remove_position(self, symbol: str, quantity: int, price: float):
        """Remove or reduce a position."""
        if symbol not in self.positions:
            logger.warning(f"Cannot remove position: {symbol} not in portfolio")
            return
        
        pos = self.positions[symbol]
        if abs(quantity) > abs(pos.quantity):
            quantity = pos.quantity  # Can't sell more than we have
        
        # Update cash
        proceeds = abs(quantity) * price
        if quantity < 0:  # Selling (reducing long position)
            self.cash += proceeds
        else:  # Buying (reducing short position)
            self.cash -= proceeds
        
        pos.quantity -= quantity
        
        # Remove position if fully closed
        if pos.quantity == 0:
            del self.positions[symbol]
        
        # Log trade
        self.trade_history.append({
            "timestamp": datetime.now(),
            "symbol": symbol,
            "action": "SELL" if quantity < 0 else "BUY",
            "quantity": abs(quantity),
            "price": price
        })
    
    def update_prices(self, prices: Dict[str, float]):
        """Update current prices for all positions."""
        for symbol, price in prices.items():
            if symbol in self.positions:
                self.positions[symbol].update_price(price)
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol."""
        return self.positions.get(symbol)
    
    def get_position_quantity(self, symbol: str) -> int:
        """Get position quantity for a symbol."""
        pos = self.positions.get(symbol)
        return pos.quantity if pos else 0
    
    def get_total_value(self, prices: Dict[str, float]) -> float:
        """Calculate total portfolio value (cash + positions)."""
        total = self.cash
        for symbol, pos in self.positions.items():
            if symbol in prices:
                pos.update_price(prices[symbol])
                total += pos.current_price * pos.quantity
            else:
                total += pos.current_price * pos.quantity
        return total
    
    def get_total_pnl(self, prices: Dict[str, float]) -> float:
        """Calculate total PnL across all positions."""
        self.update_prices(prices)
        total_pnl = 0
        for pos in self.positions.values():
            total_pnl += pos.get_pnl()
        return total_pnl
    
    def get_total_pnl_percent(self, prices: Dict[str, float]) -> float:
        """Calculate total PnL as percentage of initial cash."""
        total_value = self.get_total_value(prices)
        if self.initial_cash == 0:
            return 0.0
        return ((total_value - self.initial_cash) / self.initial_cash) * 100
    
    def check_risk_limits(self, symbol: str, prices: Dict[str, float]) -> List[str]:
        """
        Check if any risk limits are triggered for positions.
        Uses ATR-based trailing stops (no fixed take profit).
        Returns list of symbols that need action (stop loss only).
        """
        alerts = []
        self.update_prices(prices)
        
        for sym, pos in self.positions.items():
            # Only check stop loss (trailing stops handle exits)
            # Fixed take profit removed - trailing stops let winners run
            if pos.check_stop_loss():
                alerts.append(f"{sym}: STOP_LOSS triggered (ATR-based trailing stop)")
        
        return alerts
    
    def get_summary(self, prices: Dict[str, float]) -> str:
        """Get formatted portfolio summary."""
        self.update_prices(prices)
        total_value = self.get_total_value(prices)
        total_pnl = self.get_total_pnl(prices)
        total_pnl_percent = self.get_total_pnl_percent(prices)
        
        summary = f"\n{'='*60}\n"
        summary += f"PORTFOLIO SUMMARY\n"
        summary += f"{'='*60}\n"
        summary += f"Cash: {format_currency(self.cash)}\n"
        summary += f"Positions Value: {format_currency(total_value - self.cash)}\n"
        summary += f"Total Value: {format_currency(total_value)}\n"
        summary += f"Total PnL: {format_currency(total_pnl)} ({total_pnl_percent:.2f}%)\n"
        summary += f"\nPositions:\n"
        
        for symbol, pos in self.positions.items():
            pnl = pos.get_pnl()
            pnl_percent = pos.get_pnl_percent()
            summary += f"  {symbol}: {pos.quantity} shares @ ${pos.entry_price:.2f} "
            summary += f"(current: ${pos.current_price:.2f}) "
            summary += f"PnL: {format_currency(pnl)} ({pnl_percent:.2f}%)\n"
        
        summary += f"{'='*60}\n"
        return summary
