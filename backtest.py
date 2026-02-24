"""
Backtesting module for testing strategies on historical data.
Supports fast-test mode for simulating time periods quickly.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
from config import BACKTEST_START_DATE, BACKTEST_END_DATE, INITIAL_CASH, FAST_TEST_MODE, FAST_TEST_SPEED
from portfolio import Portfolio
from strategies import generate_signal, calculate_atr
from utils import fetch_historical_data, log_signal, log_trade

logger = logging.getLogger(__name__)


class Backtest:
    """Backtesting engine for strategy testing on historical data."""
    
    def __init__(self, symbols: List[str], strategy_type: str = "SMA_CROSSOVER", 
                 initial_cash: float = None, start_date: str = None, end_date: str = None):
        self.symbols = symbols
        self.strategy_type = strategy_type
        self.portfolio = Portfolio(initial_cash or INITIAL_CASH)
        self.start_date = start_date or BACKTEST_START_DATE
        self.end_date = end_date or BACKTEST_END_DATE
        self.results = []
        self.trades = []
    
    def run(self, verbose: bool = True) -> Dict:
        """
        Run backtest on historical data.
        
        Args:
            verbose: Print progress updates
            
        Returns:
            Dictionary with backtest results
        """
        logger.info(f"Starting backtest from {self.start_date} to {self.end_date}")
        
        # Fetch historical data
        if verbose:
            print(f"Fetching historical data for {len(self.symbols)} symbols...")
        historical_data = fetch_historical_data(self.symbols, days=365)
        
        if not historical_data:
            logger.error("No historical data available for backtesting")
            return {}
        
        # Prepare date range
        start = pd.to_datetime(self.start_date)
        end = pd.to_datetime(self.end_date)
        
        # Filter data to date range and normalize timezones
        for symbol in historical_data:
            data = historical_data[symbol]
            # Remove timezone info if present to avoid comparison issues
            if data.index.tz is not None:
                data.index = data.index.tz_convert('UTC').tz_localize(None)
            # Filter to date range
            data = data[(data.index >= start) & (data.index <= end)]
            historical_data[symbol] = data
        
        # Get all unique dates across all symbols
        all_dates = set()
        for data in historical_data.values():
            all_dates.update(data.index)
        all_dates = sorted(list(all_dates))
        
        if not all_dates:
            logger.error("No data in specified date range")
            return {}
        
        if verbose:
            print(f"Running backtest on {len(all_dates)} trading days...")
        
        # Simulate trading day by day
        for i, date in enumerate(all_dates):
            if verbose and i % 10 == 0:
                print(f"Processing day {i+1}/{len(all_dates)}: {date.strftime('%Y-%m-%d')}")
            
            # Get prices for this date
            prices = {}
            data_slices = {}
            
            for symbol in self.symbols:
                if symbol not in historical_data:
                    continue
                
                data = historical_data[symbol]
                # Get data up to and including current date
                data_slice = data[data.index <= date]
                
                if len(data_slice) == 0:
                    continue
                
                current_price = data_slice['close'].iloc[-1]
                prices[symbol] = current_price
                data_slices[symbol] = data_slice
            
            # Update portfolio prices
            self.portfolio.update_prices(prices)
            
            # Check risk limits (stop loss, take profit)
            risk_alerts = self.portfolio.check_risk_limits(self.symbols[0] if self.symbols else "", prices)
            for alert in risk_alerts:
                symbol = alert.split(":")[0]
                pos = self.portfolio.get_position(symbol)
                if pos:
                    # Execute stop loss or take profit
                    # For long positions, pass negative qty to sell
                    # For short positions, pass positive qty to buy back
                    qty = pos.quantity
                    price = prices.get(symbol, pos.current_price)
                    # Pass negative quantity to properly close long position (adds cash)
                    self.portfolio.remove_position(symbol, -qty, price)
                    self.trades.append({
                        "date": date,
                        "symbol": symbol,
                        "action": "SELL" if qty > 0 else "BUY",
                        "quantity": abs(qty),
                        "price": price,
                        "reason": alert
                    })
                    if verbose:
                        log_trade("SELL" if qty > 0 else "BUY", symbol, abs(qty), price, alert)
            
            # Generate signals and execute trades for each symbol
            for symbol in self.symbols:
                if symbol not in data_slices:
                    continue
                
                data_slice = data_slices[symbol]
                if len(data_slice) < 20:  # Need enough data for indicators
                    continue
                
                # Generate signal
                signal, indicators = generate_signal(data_slice, symbol, self.strategy_type)
                current_price = prices[symbol]
                current_position = self.portfolio.get_position_quantity(symbol)
                
                # Execute trades based on signal with proper risk-based position sizing
                if signal == "BUY" and current_position == 0:
                    # Calculate ATR for stop loss
                    if len(data_slice) >= 14:
                        atr_series = calculate_atr(data_slice, period=14)
                        current_atr = atr_series.iloc[-1] if not atr_series.empty else current_price * 0.02
                    else:
                        current_atr = current_price * 0.02  # Default 2% if not enough data
                    
                    # RISK-BASED POSITION SIZING: Risk 1% of portfolio per trade
                    # BUT cap position size to prevent over-concentration
                    portfolio_value = self.portfolio.get_total_value(prices)
                    risk_per_trade = portfolio_value * 0.01  # Risk 1% per trade
                    
                    # Stop loss distance = 2.5× ATR (research says 2-4×)
                    stop_distance = current_atr * 2.5
                    
                    # Calculate position size: risk_amount / stop_distance
                    # This ensures we always risk exactly 1% regardless of volatility
                    if stop_distance > 0:
                        qty_by_risk = int(risk_per_trade / stop_distance)
                    else:
                        qty_by_risk = 1
                    
                    # CAP POSITION SIZE: Don't use more than 20% of portfolio per position
                    # This prevents over-concentration with small ATR stocks
                    max_position_value = portfolio_value * 0.20  # Max 20% of portfolio
                    qty_by_cap = int(max_position_value / current_price) if current_price > 0 else 0
                    
                    # Also respect max position size and available cash
                    from config import MAX_POSITION_SIZE
                    available_cash = self.portfolio.cash
                    max_by_cash = int(available_cash / current_price) if current_price > 0 else 0
                    
                    # Take minimum of all constraints
                    qty = min(qty_by_risk, qty_by_cap, MAX_POSITION_SIZE, max_by_cash)
                    qty = max(1, qty)  # At least 1 share
                    
                    # Recalculate actual risk (may be less than 1% if capped)
                    actual_risk = qty * stop_distance
                    actual_risk_pct = (actual_risk / portfolio_value) * 100 if portfolio_value > 0 else 0
                    
                    if qty > 0 and self.portfolio.cash >= current_price * qty:
                        # Pass ATR to position for dynamic stops
                        self.portfolio.add_position(symbol, qty, current_price, atr=current_atr)
                        self.trades.append({
                            "date": date,
                            "symbol": symbol,
                            "action": "BUY",
                            "quantity": qty,
                            "price": current_price,
                            "reason": f"Signal (ATR=${current_atr:.2f}, Risk=1%)"
                        })
                        if verbose:
                            log_trade("BUY", symbol, qty, current_price, f"Signal (ATR=${current_atr:.2f})")
                
                elif signal == "SELL" and current_position > 0:
                    # Sell entire position
                    qty = current_position
                    self.portfolio.remove_position(symbol, -qty, current_price)
                    self.trades.append({
                        "date": date,
                        "symbol": symbol,
                        "action": "SELL",
                        "quantity": qty,
                        "price": current_price,
                        "reason": "Signal"
                    })
                    if verbose:
                        log_trade("SELL", symbol, qty, current_price, "Signal")
            
            # Record daily snapshot
            total_value = self.portfolio.get_total_value(prices)
            total_pnl = self.portfolio.get_total_pnl(prices)
            self.results.append({
                "date": date,
                "total_value": total_value,
                "cash": self.portfolio.cash,
                "pnl": total_pnl,
                "pnl_percent": self.portfolio.get_total_pnl_percent(prices)
            })
        
        # Calculate final statistics
        final_value = self.portfolio.get_total_value(prices)
        total_return = ((final_value - INITIAL_CASH) / INITIAL_CASH) * 100
        num_trades = len(self.trades)
        
        # Calculate buy-and-hold baseline for comparison
        buy_hold_returns = {}
        buy_hold_total = 0
        for symbol in self.symbols:
            if symbol in historical_data:
                data = historical_data[symbol]
                if len(data) > 0:
                    start_price = data['close'].iloc[0]
                    end_price = data['close'].iloc[-1]
                    symbol_return = ((end_price - start_price) / start_price) * 100
                    buy_hold_returns[symbol] = symbol_return
                    # Equal weight per symbol
                    buy_hold_total += symbol_return / len(self.symbols)
        
        results_summary = {
            "initial_cash": INITIAL_CASH,
            "final_value": final_value,
            "total_return": total_return,
            "total_pnl": final_value - INITIAL_CASH,
            "num_trades": num_trades,
            "trades": self.trades,
            "daily_results": self.results,
            "buy_hold_return": buy_hold_total,
            "buy_hold_returns": buy_hold_returns,
            "vs_buy_hold": total_return - buy_hold_total
        }
        
        if verbose:
            print("\n" + "="*60)
            print("BACKTEST RESULTS")
            print("="*60)
            print(f"Initial Cash: ${INITIAL_CASH:,.2f}")
            print(f"Final Value: ${final_value:,.2f}")
            print(f"Total Return: {total_return:.2f}%")
            print(f"Total PnL: ${final_value - INITIAL_CASH:,.2f}")
            print(f"Number of Trades: {num_trades}")
            print(f"\n{'='*60}")
            print("BASELINE COMPARISON (Buy & Hold)")
            print(f"{'='*60}")
            print(f"Buy & Hold Return: {buy_hold_total:.2f}%")
            print(f"Strategy vs Buy & Hold: {total_return - buy_hold_total:+.2f}%")
            if total_return > buy_hold_total:
                print(f"✓ Strategy BEATS buy-and-hold by {total_return - buy_hold_total:.2f}%")
            else:
                print(f"✗ Strategy UNDERPERFORMS buy-and-hold by {buy_hold_total - total_return:.2f}%")
            print("="*60)
        
        logger.info(f"Backtest completed: {total_return:.2f}% return, {num_trades} trades, vs buy-hold: {buy_hold_total:.2f}%")
        
        return results_summary
    
    def get_results_df(self) -> pd.DataFrame:
        """Get backtest results as DataFrame."""
        if not self.results:
            return pd.DataFrame()
        return pd.DataFrame(self.results)
    
    def get_trades_df(self) -> pd.DataFrame:
        """Get trades as DataFrame."""
        if not self.trades:
            return pd.DataFrame()
        return pd.DataFrame(self.trades)


def run_backtest(symbols: List[str], strategy_type: str = "SMA_CROSSOVER",
                 start_date: str = None, end_date: str = None, verbose: bool = True) -> Dict:
    """
    Convenience function to run a backtest.
    
    Args:
        symbols: List of stock symbols to test
        strategy_type: Strategy type to use
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        verbose: Print progress updates
        
    Returns:
        Dictionary with backtest results
    """
    backtest = Backtest(symbols, strategy_type, start_date=start_date, end_date=end_date)
    return backtest.run(verbose=verbose)
