"""
Automated optimization script for the trading bot.
Runs multiple optimization passes to find the best configuration.
"""

import sys
from colorama import init, Fore, Style
from optimizer import StrategyOptimizer
from stock_discovery import get_top_volatile_stocks, get_top_popular_stocks
from config import BACKTEST_START_DATE, BACKTEST_END_DATE

init(autoreset=True)


def main():
    """Main optimization entry point."""
    print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}  AUTOMATED STRATEGY OPTIMIZATION{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")
    
    # Step 1: Select symbols
    print(f"{Fore.YELLOW}Step 1: Select Stocks for Testing{Style.RESET_ALL}")
    print("1. Top Volatile Stocks (High potential)")
    print("2. Top Popular Stocks (Stable)")
    print("3. Custom Selection")
    
    choice = input("\nEnter choice (1-3, default=1): ").strip() or "1"
    
    if choice == "1":
        print(f"\n{Fore.BLUE}[DISCOVERY]{Style.RESET_ALL} Finding volatile stocks...")
        symbols = get_top_volatile_stocks(limit=10)  # Test with 10 stocks
        print(f"{Fore.GREEN}[FOUND]{Style.RESET_ALL} {', '.join(symbols)}")
    elif choice == "2":
        symbols = get_top_popular_stocks(limit=10)
        print(f"\n{Fore.GREEN}[POPULAR]{Style.RESET_ALL} {', '.join(symbols)}")
    else:
        custom = input("Enter stock symbols (comma-separated): ").strip().upper()
        symbols = [s.strip() for s in custom.split(",") if s.strip()]
    
    if not symbols:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} No symbols selected")
        return
    
    # Step 2: Select optimization mode
    print(f"\n{Fore.YELLOW}Step 2: Optimization Mode{Style.RESET_ALL}")
    print("1. Preset Modes Only (Fast - 3 tests)")
    print("2. Focused Search (Medium - ~20 tests)")
    print("3. Grid Search (Slow - ~100 tests)")
    print("4. All Modes (Very Slow - ~120 tests)")
    
    mode_choice = input("\nEnter choice (1-4, default=2): ").strip() or "2"
    
    mode_map = {
        "1": "preset",
        "2": "focused",
        "3": "grid",
        "4": "all"
    }
    
    mode = mode_map.get(mode_choice, "focused")
    max_configs = {"preset": 3, "focused": 20, "grid": 100, "all": 120}.get(mode, 20)
    
    # Step 3: Date range
    print(f"\n{Fore.YELLOW}Step 3: Date Range{Style.RESET_ALL}")
    start_date = input(f"Start date (YYYY-MM-DD, default={BACKTEST_START_DATE}): ").strip() or BACKTEST_START_DATE
    end_date = input(f"End date (YYYY-MM-DD, default={BACKTEST_END_DATE}): ").strip() or BACKTEST_END_DATE
    
    # Create optimizer
    optimizer = StrategyOptimizer(symbols, start_date=start_date, end_date=end_date)
    
    # Run optimization
    if mode == "all":
        # Run all modes sequentially
        print(f"\n{Fore.CYAN}[MODE 1/3]{Style.RESET_ALL} Testing Preset Modes...")
        optimizer.optimize("preset", max_configs=3, verbose=True)
        
        print(f"\n{Fore.CYAN}[MODE 2/3]{Style.RESET_ALL} Testing Focused Search...")
        optimizer.optimize("focused", max_configs=20, verbose=True)
        
        print(f"\n{Fore.CYAN}[MODE 3/3]{Style.RESET_ALL} Testing Grid Search...")
        optimizer.optimize("grid", max_configs=50, verbose=True)
    else:
        optimizer.optimize(mode, max_configs=max_configs, verbose=True)
    
    # Show top configurations
    print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}TOP 5 CONFIGURATIONS{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    
    top_configs = optimizer.get_top_configs(5)
    for i, result in enumerate(top_configs, 1):
        config = result['config']
        metrics = result['metrics']
        print(f"\n{Fore.YELLOW}[#{i}]{Style.RESET_ALL} {config.get('name', 'Unknown')}")
        print(f"  Strategy: {config.get('strategy_type', 'N/A')}")
        print(f"  Return: {Fore.GREEN}{metrics['total_return']:.2f}%{Style.RESET_ALL}")
        print(f"  Score: {metrics['score']:.2f}")
        print(f"  Win Rate: {metrics['win_rate']:.1f}%")
        print(f"  Trades: {metrics['num_trades']}")
    
    # Save results
    optimizer.save_results()
    
    # Ask if user wants to use best config
    print(f"\n{Fore.YELLOW}Would you like to use the best configuration?{Style.RESET_ALL}")
    use_best = input("(y/n): ").strip().lower()
    
    if use_best == 'y':
        best = optimizer.best_config
        print(f"\n{Fore.GREEN}Best Configuration:{Style.RESET_ALL}")
        print(f"  Strategy: {best.get('strategy_type')}")
        print(f"  Max Position: {best.get('max_position_size')}")
        print(f"  Stop Loss: {best.get('stop_loss_percent')*100:.1f}%")
        print(f"  Take Profit: {best.get('take_profit_percent')*100:.1f}%")
        print(f"\n{Fore.YELLOW}You can manually update config.py with these values.{Style.RESET_ALL}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Optimization cancelled.{Style.RESET_ALL}")
        sys.exit(0)
