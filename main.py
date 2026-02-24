"""
Main execution loop for the trading bot.
Supports live trading, backtesting, and fast-test mode.
"""

import time
import sys
from datetime import datetime
from typing import List, Dict
import logging
from colorama import init, Fore, Style

# Initialize colorama for Windows support
init(autoreset=True)

from config import (
    TRADING_SYMBOLS, UPDATE_INTERVAL, STRATEGY_CONFIG, FAST_TEST_MODE, FAST_TEST_SPEED,
    MAX_POSITION_SIZE, ENABLE_VISUALIZATION, STATUS_UPDATE_INTERVAL
)
from utils import (
    fetch_historical_data, fetch_current_prices, log_signal, log_trade,
    check_risk, calculate_pnl
)
from strategies import generate_signal, calculate_atr
from broker import get_broker
from portfolio import Portfolio
from backtest import run_backtest

logger = logging.getLogger(__name__)


class TradingBot:
    """Main trading bot class that orchestrates all components."""
    
    def __init__(self, symbols: List[str] = None, strategy_type: str = None, 
                 broker_type: str = "alpaca", paper_trading: bool = True):
        self.symbols = symbols or TRADING_SYMBOLS
        self.strategy_type = strategy_type or STRATEGY_CONFIG.get("type", "SMA_CROSSOVER")
        self.broker = None
        if paper_trading:
            try:
                self.broker = get_broker(broker_type)
            except Exception as e:
                logger.warning(f"Failed to initialize broker: {e}. Running in simulation mode.")
                print(f"Warning: Broker initialization failed. Running in simulation mode.")
        self.portfolio = Portfolio()
        self.running = False
        self.fast_test_mode = FAST_TEST_MODE
        self.fast_test_speed = FAST_TEST_SPEED
    
    def initialize(self):
        """Initialize the bot and fetch initial data."""
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {Fore.CYAN}[INIT]{Style.RESET_ALL} Initializing Trading Bot...")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.CYAN}[CONFIG]{Style.RESET_ALL} Configuration:")
        print(f"  • Symbols: {', '.join(self.symbols)}")
        print(f"  • Strategy: {self.strategy_type}")
        print(f"  • Broker: {'Connected' if self.broker else 'Simulation Mode (No Broker)'}")
        
        logger.info(f"Initializing trading bot for symbols: {self.symbols}")
        logger.info(f"Strategy: {self.strategy_type}")
        
        # Fetch initial historical data for indicators
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {Fore.BLUE}[DATA]{Style.RESET_ALL} Fetching initial historical data...")
        self.historical_data = fetch_historical_data(self.symbols, days=100)
        
        if not self.historical_data:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.RED}[ERROR]{Style.RESET_ALL} Failed to fetch historical data")
            logger.error("Failed to fetch historical data")
            return False
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.GREEN}[OK]{Style.RESET_ALL} Historical data loaded: {len(self.historical_data)} symbols")
        
        # Initialize portfolio with broker positions if available
        if self.broker:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.YELLOW}[BROKER]{Style.RESET_ALL} Connecting to broker...")
            account_info = self.broker.get_account_info()
            if account_info:
                self.portfolio.cash = account_info.get("cash", 0)
                equity = account_info.get("equity", 0)
                buying_power = account_info.get("buying_power", 0)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.GREEN}[ACCOUNT]{Style.RESET_ALL} Account Information:")
                print(f"  • Cash: ${self.portfolio.cash:,.2f}")
                print(f"  • Equity: ${equity:,.2f}")
                print(f"  • Buying Power: ${buying_power:,.2f}")
            
            # Sync positions from broker
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.YELLOW}[SYNC]{Style.RESET_ALL} Syncing existing positions...")
            for symbol in self.symbols:
                position_qty = self.broker.get_position(symbol)
                if position_qty != 0:
                    current_price = self.broker.get_current_price(symbol)
                    if current_price:
                        self.portfolio.add_position(symbol, position_qty, current_price)
                        print(f"[{datetime.now().strftime('%H:%M:%S')}]   {Fore.GREEN}[OK]{Style.RESET_ALL} Synced: {symbol} - {position_qty} shares @ ${current_price:.2f}")
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}]   • {symbol}: No existing position")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.YELLOW}[INFO]{Style.RESET_ALL} Running in simulation mode (no broker connection)")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.GREEN}[CASH]{Style.RESET_ALL} Starting with ${self.portfolio.cash:,.2f} cash")
        
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {Fore.GREEN}[READY]{Style.RESET_ALL} Bot initialized successfully!")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.CYAN}[START]{Style.RESET_ALL} Ready to start trading\n")
        return True
    
    def process_symbol(self, symbol: str) -> Dict:
        """
        Process a single symbol: generate signal and execute trades.
        
        Returns:
            Dictionary with signal and execution info
        """
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.CYAN}[PROCESS]{Style.RESET_ALL} Processing {symbol}...")
        
        if symbol not in self.historical_data:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.YELLOW}[WARN]{Style.RESET_ALL} {symbol}: No historical data available")
            return {"symbol": symbol, "status": "no_data"}
        
        data = self.historical_data[symbol]
        if len(data) < 20:  # Need enough data for indicators
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.YELLOW}[WARN]{Style.RESET_ALL} {symbol}: Insufficient data ({len(data)} days, need 20+)")
            return {"symbol": symbol, "status": "insufficient_data"}
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.BLUE}[ANALYZE]{Style.RESET_ALL} {symbol}: Analyzing {len(data)} days of data...")
        
        # Generate signal
        signal, indicators = generate_signal(data, symbol, self.strategy_type)
        
        # Get current price
        current_price = data['close'].iloc[-1]
        
        # Get current position
        if self.broker:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.YELLOW}[POSITION]{Style.RESET_ALL} {symbol}: Checking broker position...")
            current_position = self.broker.get_position(symbol)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.YELLOW}[POSITION]{Style.RESET_ALL} {symbol}: Current position = {current_position} shares")
        else:
            current_position = self.portfolio.get_position_quantity(symbol)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.YELLOW}[POSITION]{Style.RESET_ALL} {symbol}: Portfolio position = {current_position} shares")
        
        # Log signal with reason
        reason = indicators.get("reason", "")
        if reason:
            log_signal(symbol, signal, current_price, {k: v for k, v in indicators.items() if k != "reason"})
            if signal == "HOLD":
                # For HOLD signals, print the reason so user knows why
                print(f"  → {reason}")
        else:
            log_signal(symbol, signal, current_price, indicators)
        
        result = {
            "symbol": symbol,
            "signal": signal,
            "price": current_price,
            "position": current_position,
            "indicators": indicators
        }
        
        # Execute trades if broker is available
        if self.broker and signal in ["BUY", "SELL"]:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.MAGENTA}[RISK]{Style.RESET_ALL} {symbol}: Performing risk check...")
            # Risk check
            if not check_risk(current_position, MAX_POSITION_SIZE):
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.RED}[FAIL]{Style.RESET_ALL} {symbol}: Risk check FAILED (position: {current_position}, max: {MAX_POSITION_SIZE})")
                logger.warning(f"Risk check failed for {symbol}")
                result["status"] = "risk_check_failed"
                return result
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.GREEN}[PASS]{Style.RESET_ALL} {symbol}: Risk check PASSED")
            
            # Execute trade with ATR-based position sizing
            if signal == "BUY" and current_position == 0:
                # Calculate ATR for risk-based position sizing
                if len(data) >= 14:
                    atr_series = calculate_atr(data, period=14)
                    current_atr = atr_series.iloc[-1] if not atr_series.empty else current_price * 0.02
                else:
                    current_atr = current_price * 0.02  # Default 2% if not enough data
                
                # RISK-BASED POSITION SIZING: Risk 1% of portfolio per trade
                # BUT cap position size to prevent over-concentration
                prices = {s: self.broker.get_current_price(s) or data['close'].iloc[-1] for s in self.symbols}
                portfolio_value = self.portfolio.get_total_value(prices)
                risk_per_trade = portfolio_value * 0.01  # Risk 1% per trade
                
                # Stop loss distance = 2.5× ATR
                stop_distance = current_atr * 2.5
                
                # Calculate position size: risk_amount / stop_distance
                if stop_distance > 0:
                    qty_by_risk = int(risk_per_trade / stop_distance)
                else:
                    qty_by_risk = 1
                
                # CAP POSITION SIZE: Don't use more than 20% of portfolio per position
                max_position_value = portfolio_value * 0.20  # Max 20% of portfolio
                qty_by_cap = int(max_position_value / current_price) if current_price > 0 else 0
                
                # Take minimum of all constraints
                qty = min(qty_by_risk, qty_by_cap, MAX_POSITION_SIZE)
                qty = max(1, qty)  # At least 1 share
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.CYAN}[BUY]{Style.RESET_ALL} {symbol}: Executing BUY order for {qty} share(s) at ${current_price:.2f} (ATR=${current_atr:.2f}, Risk=1%)...")
                success = self.broker.execute_order(symbol, qty, "buy")
                if success:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.GREEN}[SUCCESS]{Style.RESET_ALL} {symbol}: BUY order EXECUTED successfully!")
                    result["executed"] = True
                    result["action"] = "BUY"
                    result["quantity"] = qty
                    # Update portfolio with ATR
                    self.portfolio.add_position(symbol, qty, current_price, atr=current_atr)
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.RED}[FAIL]{Style.RESET_ALL} {symbol}: BUY order FAILED")
            
            elif signal == "SELL" and current_position > 0:
                qty = current_position
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.CYAN}[SELL]{Style.RESET_ALL} {symbol}: Executing SELL order for {qty} share(s) at ${current_price:.2f}...")
                success = self.broker.execute_order(symbol, qty, "sell")
                if success:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.GREEN}[SUCCESS]{Style.RESET_ALL} {symbol}: SELL order EXECUTED successfully!")
                    result["executed"] = True
                    result["action"] = "SELL"
                    result["quantity"] = qty
                    # Update portfolio
                    self.portfolio.remove_position(symbol, -qty, current_price)
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.RED}[FAIL]{Style.RESET_ALL} {symbol}: SELL order FAILED")
            else:
                if signal == "BUY":
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.YELLOW}[INFO]{Style.RESET_ALL} {symbol}: BUY signal but already have position ({current_position} shares)")
                elif signal == "SELL":
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.YELLOW}[INFO]{Style.RESET_ALL} {symbol}: SELL signal but no position to sell")
        elif not self.broker:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.YELLOW}[INFO]{Style.RESET_ALL} {symbol}: No broker connected (simulation mode) - signal: {signal}")
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.GREEN}[DONE]{Style.RESET_ALL} {symbol}: Processing complete")
        result["status"] = "processed"
        return result
    
    def update_data(self):
        """Update historical data with latest prices."""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.BLUE}[DATA]{Style.RESET_ALL} Fetching current prices...")
        # Fetch current prices
        current_prices = fetch_current_prices(self.symbols)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.GREEN}[OK]{Style.RESET_ALL} Prices fetched: {', '.join([f'{s}=${p:.2f}' for s, p in current_prices.items()])}")
        
        # Update historical data (append latest prices)
        for symbol in self.symbols:
            if symbol in current_prices and symbol in self.historical_data:
                price = current_prices[symbol]
                # In a real implementation, you'd append this to the historical data
                # For now, we'll refetch periodically
                pass
        
        # Refetch historical data periodically (every 10 updates)
        if not hasattr(self, 'update_count'):
            self.update_count = 0
        self.update_count += 1
        
        if self.update_count % 10 == 0:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.BLUE}[REFRESH]{Style.RESET_ALL} Refreshing historical data (update #{self.update_count})...")
            self.historical_data = fetch_historical_data(self.symbols, days=100)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.GREEN}[OK]{Style.RESET_ALL} Historical data refreshed")
    
    def run_live(self):
        """Run the bot in live trading mode."""
        if not self.initialize():
            logger.error("Failed to initialize bot")
            return
        
        self.running = True
        print(f"\n{'='*60}")
        print("TRADING BOT - LIVE MODE")
        print(f"{'='*60}")
        print(f"Symbols: {', '.join(self.symbols)}")
        print(f"Strategy: {self.strategy_type}")
        print(f"Update Interval: {UPDATE_INTERVAL} seconds")
        print(f"Status Updates: Every {STATUS_UPDATE_INTERVAL} seconds" if STATUS_UPDATE_INTERVAL > 0 else "Status Updates: Every loop")
        print(f"{'='*60}\n")
        
        last_status_time = time.time()
        loop_count = 0
        
        try:
            while self.running:
                start_time = time.time()
                loop_count += 1
                
                print(f"\n{'='*60}")
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.CYAN}[LOOP]{Style.RESET_ALL} Starting Loop #{loop_count}")
                print(f"{'='*60}")
                
                # Update data
                self.update_data()
                
                # Process each symbol
                for symbol in self.symbols:
                    try:
                        result = self.process_symbol(symbol)
                        
                        # Check for risk alerts
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.YELLOW}[RISK]{Style.RESET_ALL} {symbol}: Checking risk limits...")
                        if self.broker:
                            prices = {s: self.broker.get_current_price(s) or 0 for s in self.symbols}
                        else:
                            prices = fetch_current_prices(self.symbols)
                        
                        risk_alerts = self.portfolio.check_risk_limits(symbol, prices)
                        if risk_alerts:
                            for alert in risk_alerts:
                                print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.RED}[ALERT]{Style.RESET_ALL} {alert}")
                                # Auto-execute stop loss / take profit if broker available
                                if self.broker and "STOP_LOSS" in alert:
                                    symbol_alert = alert.split(":")[0]
                                    pos = self.portfolio.get_position(symbol_alert)
                                    if pos:
                                        print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.RED}[STOP]{Style.RESET_ALL} {symbol_alert}: Executing STOP LOSS...")
                                        self.broker.execute_order(symbol_alert, pos.quantity, "sell")
                        else:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.GREEN}[OK]{Style.RESET_ALL} {symbol}: No risk alerts")
                    
                    except Exception as e:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.RED}[ERROR]{Style.RESET_ALL} ERROR processing {symbol}: {e}")
                        logger.error(f"Error processing {symbol}: {e}", exc_info=True)
                        continue
                
                # Always print status update (even if delayed)
                current_time = time.time()
                time_since_status = current_time - last_status_time
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.BLUE}[STATUS]{Style.RESET_ALL} Generating status update...")
                # Print status update
                prices = fetch_current_prices(self.symbols)
                if self.broker:
                    # Use broker prices if available
                    for symbol in self.symbols:
                        broker_price = self.broker.get_current_price(symbol)
                        if broker_price:
                            prices[symbol] = broker_price
                
                # Quick status summary
                total_value = self.portfolio.get_total_value(prices)
                total_pnl = self.portfolio.get_total_pnl(prices)
                total_pnl_pct = self.portfolio.get_total_pnl_percent(prices)
                
                pnl_color = Fore.GREEN if total_pnl >= 0 else Fore.RED
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {Fore.CYAN}[UPDATE]{Style.RESET_ALL} Status Update #{loop_count} (Loop took {time.time() - start_time:.1f}s)")
                print(f"  {Fore.GREEN}[VALUE]{Style.RESET_ALL} Portfolio Value: ${total_value:,.2f}")
                print(f"  {pnl_color}[PnL]{Style.RESET_ALL} Total PnL: ${total_pnl:,.2f} ({total_pnl_pct:+.2f}%)")
                print(f"  {Fore.BLUE}[POS]{Style.RESET_ALL} Active Positions: {len(self.portfolio.positions)}")
                if len(self.portfolio.positions) > 0:
                    for symbol, pos in self.portfolio.positions.items():
                        pnl = pos.get_pnl()
                        pnl_pct = pos.get_pnl_percent()
                        status_color = Fore.GREEN if pnl >= 0 else Fore.RED
                        status_text = "PROFIT" if pnl >= 0 else "LOSS"
                        print(f"    {status_color}[{status_text}]{Style.RESET_ALL} {symbol}: {pos.quantity} shares @ ${pos.entry_price:.2f} → ${pos.current_price:.2f} ({pnl_pct:+.2f}%)")
                else:
                    print(f"    (No active positions)")
                
                last_status_time = current_time
                
                # Print full portfolio summary less frequently
                if hasattr(self, 'summary_count'):
                    self.summary_count += 1
                else:
                    self.summary_count = 0
                
                if self.summary_count % 5 == 0:  # Every 5 updates
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {Fore.CYAN}[SUMMARY]{Style.RESET_ALL} Full Portfolio Summary:")
                    prices = fetch_current_prices(self.symbols)
                    if self.broker:
                        # Use broker prices if available
                        for symbol in self.symbols:
                            broker_price = self.broker.get_current_price(symbol)
                            if broker_price:
                                prices[symbol] = broker_price
                    
                    print(self.portfolio.get_summary(prices))
                
                # Calculate sleep time
                elapsed = time.time() - start_time
                sleep_time = max(0, UPDATE_INTERVAL - elapsed)
                
                if self.fast_test_mode:
                    sleep_time = sleep_time / self.fast_test_speed
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.YELLOW}[WAIT]{Style.RESET_ALL} Waiting {sleep_time:.1f} seconds until next update...")
                print(f"{'='*60}\n")
                
                time.sleep(sleep_time)
        
        except KeyboardInterrupt:
            print("\n\nStopping bot...")
            self.running = False
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Fatal error in main loop: {e}", exc_info=True)
            self.running = False
    
    def run_backtest_mode(self, start_date: str = None, end_date: str = None):
        """Run the bot in backtesting mode."""
        print(f"\n{'='*60}")
        print("TRADING BOT - BACKTEST MODE")
        print(f"{'='*60}")
        print(f"Symbols: {', '.join(self.symbols)}")
        print(f"Strategy: {self.strategy_type}")
        if start_date:
            print(f"Start Date: {start_date}")
        if end_date:
            print(f"End Date: {end_date}")
        print(f"{'='*60}\n")
        
        results = run_backtest(
            self.symbols,
            self.strategy_type,
            start_date=start_date,
            end_date=end_date,
            verbose=True
        )
        
        return results


def main():
    """Main entry point with interactive configuration."""
    from interactive_config import configure_interactive
    from config import MAX_POSITION_SIZE, STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT, UPDATE_INTERVAL, STRATEGY_CONFIG
    
    # Get configuration from user
    user_config = configure_interactive()
    
    # Apply configuration to global config
    import config as cfg
    cfg.TRADING_SYMBOLS = user_config["symbols"]
    cfg.MAX_POSITION_SIZE = user_config.get("max_position_size", MAX_POSITION_SIZE)
    cfg.STOP_LOSS_PERCENT = user_config.get("stop_loss_percent", STOP_LOSS_PERCENT)
    cfg.TAKE_PROFIT_PERCENT = user_config.get("take_profit_percent", TAKE_PROFIT_PERCENT)
    cfg.UPDATE_INTERVAL = user_config.get("update_interval", UPDATE_INTERVAL)
    
    # Update strategy config
    if "strategy_config" in user_config:
        cfg.STRATEGY_CONFIG.update(user_config["strategy_config"])
    
    # Create bot instance
    bot = TradingBot(
        symbols=user_config["symbols"],
        strategy_type=cfg.STRATEGY_CONFIG.get("type", "SMA_CROSSOVER"),
        paper_trading=user_config.get("use_broker", True)
    )
    
    # Run in appropriate mode
    if user_config["trading_mode"] == "backtest":
        bot.run_backtest_mode(
            start_date=user_config.get("backtest_start_date"),
            end_date=user_config.get("backtest_end_date")
        )
    else:
        bot.run_live()


if __name__ == "__main__":
    main()
