"""
Example usage scripts for the trading bot.
Demonstrates different ways to use the bot.
"""

from main import TradingBot
from config import TRADING_SYMBOLS

# Example 1: Simple backtest
def example_backtest():
    """Run a simple backtest on historical data."""
    print("Example 1: Running Backtest")
    print("-" * 60)
    
    bot = TradingBot(
        symbols=["AAPL", "MSFT"],
        strategy_type="SMA_CROSSOVER",
        paper_trading=False  # No broker needed for backtest
    )
    
    results = bot.run_backtest_mode(
        start_date="2023-01-01",
        end_date="2024-01-01"
    )
    
    print(f"\nBacktest completed!")
    print(f"Total Return: {results.get('total_return', 0):.2f}%")
    print(f"Number of Trades: {results.get('num_trades', 0)}")


# Example 2: Live trading simulation (no broker)
def example_simulation():
    """Run bot in simulation mode without broker."""
    print("\nExample 2: Live Simulation (No Broker)")
    print("-" * 60)
    print("This will run for a few iterations then stop.")
    print("Press Ctrl+C to stop early.\n")
    
    bot = TradingBot(
        symbols=["AAPL"],
        strategy_type="RSI",
        paper_trading=False  # Simulation mode
    )
    
    # Note: This would run indefinitely in real usage
    # For demo, we'll just initialize
    if bot.initialize():
        print("Bot initialized. In real usage, call bot.run_live() to start trading.")
    else:
        print("Failed to initialize bot.")


# Example 3: Test different strategies
def example_strategy_comparison():
    """Compare different strategies via backtesting."""
    print("\nExample 3: Strategy Comparison")
    print("-" * 60)
    
    strategies = ["SMA_CROSSOVER", "EMA_CROSSOVER", "RSI"]
    symbols = ["AAPL"]
    
    for strategy in strategies:
        print(f"\nTesting {strategy}...")
        bot = TradingBot(
            symbols=symbols,
            strategy_type=strategy,
            paper_trading=False
        )
        
        results = bot.run_backtest_mode(
            start_date="2023-01-01",
            end_date="2024-01-01"
        )
        
        print(f"  Return: {results.get('total_return', 0):.2f}%")
        print(f"  Trades: {results.get('num_trades', 0)}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        example = sys.argv[1]
        if example == "backtest":
            example_backtest()
        elif example == "simulation":
            example_simulation()
        elif example == "compare":
            example_strategy_comparison()
        else:
            print(f"Unknown example: {example}")
            print("Available: backtest, simulation, compare")
    else:
        print("Trading Bot - Example Usage")
        print("=" * 60)
        print("\nAvailable examples:")
        print("  1. Backtest: python example_usage.py backtest")
        print("  2. Simulation: python example_usage.py simulation")
        print("  3. Strategy Comparison: python example_usage.py compare")
        print("\nOr run the main bot:")
        print("  python main.py --mode backtest")
        print("  python main.py --mode live")
