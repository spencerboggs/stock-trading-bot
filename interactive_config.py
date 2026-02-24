"""
Interactive configuration module for the trading bot.
Provides user-friendly prompts and preset mode selection.
"""

from colorama import Fore, Style
from config import TRADING_SYMBOLS_POOL, PRESET_MODES
from stock_discovery import get_top_volatile_stocks, get_top_popular_stocks, filter_valid_symbols
import sys


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{text.center(60)}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")


def print_section(text: str):
    """Print a section header."""
    print(f"\n{Fore.YELLOW}{text}{Style.RESET_ALL}")


def get_user_choice(prompt: str, choices: list, default: int = 0) -> int:
    """
    Get user choice from a list of options.
    
    Args:
        prompt: Prompt text
        choices: List of choice strings
        default: Default choice index
        
    Returns:
        Selected choice index
    """
    print(f"\n{prompt}")
    for i, choice in enumerate(choices, 1):
        marker = f"{Fore.GREEN}[{i}]{Style.RESET_ALL}" if i == default + 1 else f"[{i}]"
        print(f"  {marker} {choice}")
    
    while True:
        try:
            choice_input = input(f"\nEnter choice (1-{len(choices)}, default={default+1}): ").strip()
            if not choice_input:
                return default
            
            choice_num = int(choice_input)
            if 1 <= choice_num <= len(choices):
                return choice_num - 1
            else:
                print(f"{Fore.RED}Invalid choice. Please enter a number between 1 and {len(choices)}.{Style.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Configuration cancelled.{Style.RESET_ALL}")
            sys.exit(0)


def get_multi_choice(prompt: str, choices: list, min_selections: int = 1, max_selections: int = None) -> list:
    """
    Get multiple selections from a list.
    
    Args:
        prompt: Prompt text
        choices: List of choice strings
        min_selections: Minimum number of selections
        max_selections: Maximum number of selections (None = unlimited)
        
    Returns:
        List of selected indices
    """
    print(f"\n{prompt}")
    print(f"Available symbols ({len(choices)} total):")
    
    # Display in columns for better readability
    cols = 5
    for i, choice in enumerate(choices):
        marker = f"{Fore.GREEN}{choice:>6}{Style.RESET_ALL}" if i < 10 else f"{choice:>6}"
        print(marker, end="  " if (i + 1) % cols != 0 else "\n")
    if len(choices) % cols != 0:
        print()
    
    print(f"\n{Fore.YELLOW}Enter symbol codes separated by commas (e.g., AAPL,MSFT,GOOGL){Style.RESET_ALL}")
    if min_selections:
        print(f"Minimum: {min_selections} symbol(s)")
    if max_selections:
        print(f"Maximum: {max_selections} symbol(s)")
    
    while True:
        try:
            user_input = input("\nSymbols: ").strip().upper()
            if not user_input:
                print(f"{Fore.RED}Please enter at least one symbol.{Style.RESET_ALL}")
                continue
            
            selected = [s.strip() for s in user_input.split(",")]
            
            # Validate selections
            invalid = [s for s in selected if s not in choices]
            if invalid:
                print(f"{Fore.RED}Invalid symbols: {', '.join(invalid)}{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}Please choose from the available symbols.{Style.RESET_ALL}")
                continue
            
            if len(selected) < min_selections:
                print(f"{Fore.RED}Please select at least {min_selections} symbol(s).{Style.RESET_ALL}")
                continue
            
            if max_selections and len(selected) > max_selections:
                print(f"{Fore.RED}Please select at most {max_selections} symbol(s).{Style.RESET_ALL}")
                continue
            
            return selected
            
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Configuration cancelled.{Style.RESET_ALL}")
            sys.exit(0)


def get_number_input(prompt: str, default: float, min_val: float = None, max_val: float = None) -> float:
    """Get a number input from user."""
    while True:
        try:
            user_input = input(f"{prompt} (default: {default}): ").strip()
            if not user_input:
                return default
            
            value = float(user_input)
            
            if min_val is not None and value < min_val:
                print(f"{Fore.RED}Value must be at least {min_val}.{Style.RESET_ALL}")
                continue
            
            if max_val is not None and value > max_val:
                print(f"{Fore.RED}Value must be at most {max_val}.{Style.RESET_ALL}")
                continue
            
            return value
            
        except ValueError:
            print(f"{Fore.RED}Invalid number. Please enter a valid number.{Style.RESET_ALL}")
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Configuration cancelled.{Style.RESET_ALL}")
            sys.exit(0)


def configure_interactive() -> dict:
    """
    Interactive configuration wizard.
    
    Returns:
        Dictionary with configuration settings
    """
    print_header("TRADING BOT CONFIGURATION")
    
    # Step 1: Choose configuration mode
    print_section("Step 1: Configuration Mode")
    mode_choices = [
        f"{PRESET_MODES['safe']['name']} - {PRESET_MODES['safe']['description']}",
        f"{PRESET_MODES['normal']['name']} - {PRESET_MODES['normal']['description']}",
        f"{PRESET_MODES['aggressive']['name']} - {PRESET_MODES['aggressive']['description']}",
        "Custom Mode - Configure all settings manually"
    ]
    
    mode_choice = get_user_choice("Select configuration mode:", mode_choices, default=1)
    
    config = {}
    
    if mode_choice < 3:  # Preset mode
        mode_key = ["safe", "normal", "aggressive"][mode_choice]
        preset = PRESET_MODES[mode_key]
        
        print(f"\n{Fore.GREEN}Selected: {preset['name']}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Description: {preset['description']}{Style.RESET_ALL}")
        
        # Apply preset configuration
        config.update({
            "mode": mode_key,
            "max_position_size": preset["max_position_size"],
            "max_portfolio_value": preset["max_portfolio_value"],
            "stop_loss_percent": preset["stop_loss_percent"],
            "take_profit_percent": preset["take_profit_percent"],
            "strategy_config": preset["strategy_config"].copy(),
            "update_interval": preset["update_interval"],
            "max_symbols": preset["max_symbols"],
        })
        
        # Step 2: Select symbols
        print_section(f"Step 2: Select Trading Symbols (Recommended: {preset['max_symbols']} symbols)")
        print(f"{Fore.YELLOW}The {preset['name']} mode works best with {preset['max_symbols']} symbols.{Style.RESET_ALL}")
        
        symbols = get_multi_choice(
            "Which stocks would you like to trade?",
            TRADING_SYMBOLS_POOL,
            min_selections=1,
            max_selections=preset["max_symbols"]
        )
        config["symbols"] = symbols
        
    else:  # Custom mode
        print(f"\n{Fore.YELLOW}Custom Mode Selected{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}You will configure all settings manually.{Style.RESET_ALL}")
        
        config["mode"] = "custom"
        
        # Custom symbol selection
        print_section("Step 1: Select Trading Symbols")
        
        # Stock selection method
        stock_selection_choices = [
            "Top 20 Daily Volatile Stocks (High potential, higher risk)",
            "Top Popular Stocks (AAPL, MSFT, NVDA, etc. - Stable, well-known)",
            "Custom Selection (Manually enter stock symbols)"
        ]
        
        selection_method = get_user_choice(
            "How would you like to select stocks?",
            stock_selection_choices,
            default=2
        )
        
        if selection_method == 0:  # Volatile stocks
            print(f"\n{Fore.BLUE}[DISCOVERY]{Style.RESET_ALL} Discovering top volatile stocks...")
            volatile_stocks = get_top_volatile_stocks(limit=20)
            print(f"{Fore.GREEN}[FOUND]{Style.RESET_ALL} Top volatile stocks: {', '.join(volatile_stocks)}")
            
            confirm = input(f"Use these stocks? (y/n, default=y): ").strip().lower()
            if confirm in ['', 'y', 'yes']:
                config["symbols"] = volatile_stocks
            else:
                custom_input = input(f"Enter custom stock symbols (comma-separated): ").strip().upper()
                custom_symbols = [s.strip() for s in custom_input.split(",") if s.strip()]
                config["symbols"] = filter_valid_symbols(custom_symbols)
        
        elif selection_method == 1:  # Popular stocks
            popular_stocks = get_top_popular_stocks(limit=20)
            print(f"\n{Fore.GREEN}[POPULAR]{Style.RESET_ALL} Top popular stocks: {', '.join(popular_stocks)}")
            
            confirm = input(f"Use these stocks? (y/n, default=y): ").strip().lower()
            if confirm in ['', 'y', 'yes']:
                config["symbols"] = popular_stocks
            else:
                custom_input = input(f"Enter custom stock symbols (comma-separated): ").strip().upper()
                custom_symbols = [s.strip() for s in custom_input.split(",") if s.strip()]
                config["symbols"] = filter_valid_symbols(custom_symbols)
        
        else:  # Custom selection
            print(f"\n{Fore.YELLOW}Enter stock symbols manually.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}You can enter any valid stock symbol (e.g., AAPL, MSFT, TSLA, etc.){Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Separate multiple symbols with commas.{Style.RESET_ALL}")
            
            while True:
                custom_input = input(f"\nEnter stock symbols (comma-separated): ").strip().upper()
                if not custom_input:
                    print(f"{Fore.RED}Please enter at least one symbol.{Style.RESET_ALL}")
                    continue
                
                symbols = [s.strip() for s in custom_input.split(",") if s.strip()]
                valid_symbols = filter_valid_symbols(symbols)
                
                if len(valid_symbols) == 0:
                    print(f"{Fore.RED}No valid symbols found. Please check your input.{Style.RESET_ALL}")
                    continue
                
                print(f"{Fore.GREEN}[VALID]{Style.RESET_ALL} Valid symbols: {', '.join(valid_symbols)}")
                confirm = input(f"Use these symbols? (y/n): ").strip().lower()
                if confirm in ['y', 'yes']:
                    config["symbols"] = valid_symbols
                    break
        
        # Custom risk parameters
        print_section("Step 2: Risk Management")
        config["max_position_size"] = int(get_number_input(
            "Max position size (shares per symbol)",
            default=10,
            min_val=1,
            max_val=100
        ))
        
        config["max_portfolio_value"] = get_number_input(
            "Max portfolio value ($)",
            default=10000,
            min_val=1000
        )
        
        config["stop_loss_percent"] = get_number_input(
            "Stop loss percentage (e.g., 0.02 for 2%)",
            default=0.02,
            min_val=0.001,
            max_val=0.1
        )
        
        config["take_profit_percent"] = get_number_input(
            "Take profit percentage (e.g., 0.05 for 5%)",
            default=0.05,
            min_val=0.001,
            max_val=0.2
        )
        
        # Custom strategy
        print_section("Step 3: Strategy Configuration")
        strategy_choices = [
            "SMA Crossover - Simple Moving Average crossover",
            "EMA Crossover - Exponential Moving Average crossover",
            "RSI Strategy - Relative Strength Index",
            "Bollinger Bands - Mean reversion strategy"
        ]
        
        strategy_choice = get_user_choice("Select trading strategy:", strategy_choices, default=0)
        strategy_map = {
            0: "SMA_CROSSOVER",
            1: "EMA_CROSSOVER",
            2: "RSI",
            3: "BOLLINGER"
        }
        
        config["strategy_config"] = {
            "type": strategy_map[strategy_choice],
            "trend_following": True,
            "crossover_only": False,
        }
        
        if strategy_choice in [0, 1]:  # SMA or EMA
            trend_choice = get_user_choice(
                "Trend following mode?",
                ["Yes - More active trading (buy in uptrends)", "No - Only trade on crossovers (more conservative)"],
                default=0
            )
            config["strategy_config"]["trend_following"] = (trend_choice == 0)
            config["strategy_config"]["crossover_only"] = (trend_choice == 1)
        
        # Update interval
        config["update_interval"] = int(get_number_input(
            "Update interval (seconds)",
            default=60,
            min_val=10,
            max_val=300
        ))
    
    # Step 3: Trading mode
    print_section("Step 3: Trading Mode")
    mode_choices = [
        "Live Trading - Real-time paper trading",
        "Backtest Mode - Test on historical data"
    ]
    
    trading_mode = get_user_choice("Select trading mode:", mode_choices, default=0)
    config["trading_mode"] = "live" if trading_mode == 0 else "backtest"
    
    if config["trading_mode"] == "backtest":
        print_section("Step 4: Backtest Parameters")
        config["backtest_start_date"] = input("Start date (YYYY-MM-DD, default: 2025-01-01): ").strip() or "2025-01-01"
        config["backtest_end_date"] = input("End date (YYYY-MM-DD, default: 2025-12-31): ").strip() or "2025-12-31"
    
    # Step 4: Broker connection
    print_section("Step 4: Broker Connection")
    broker_choice = get_user_choice(
        "Broker connection:",
        ["Connect to Alpaca (Paper Trading)", "Simulation Mode (No Broker)"],
        default=0
    )
    config["use_broker"] = (broker_choice == 0)
    
    # Summary
    print_header("CONFIGURATION SUMMARY")
    print(f"{Fore.GREEN}Mode:{Style.RESET_ALL} {config.get('mode', 'custom').upper()}")
    print(f"{Fore.GREEN}Symbols:{Style.RESET_ALL} {', '.join(config['symbols'])} ({len(config['symbols'])} symbols)")
    print(f"{Fore.GREEN}Trading Mode:{Style.RESET_ALL} {config['trading_mode'].upper()}")
    print(f"{Fore.GREEN}Broker:{Style.RESET_ALL} {'Connected' if config['use_broker'] else 'Simulation'}")
    
    if config.get("mode") != "custom":
        preset = PRESET_MODES[config["mode"]]
        print(f"{Fore.GREEN}Max Position Size:{Style.RESET_ALL} {config['max_position_size']} shares")
        print(f"{Fore.GREEN}Stop Loss:{Style.RESET_ALL} {config['stop_loss_percent']*100:.1f}%")
        print(f"{Fore.GREEN}Take Profit:{Style.RESET_ALL} {config['take_profit_percent']*100:.1f}%")
        print(f"{Fore.GREEN}Update Interval:{Style.RESET_ALL} {config['update_interval']} seconds")
        print(f"{Fore.GREEN}Strategy:{Style.RESET_ALL} {config['strategy_config']['type']}")
    
    confirm = input(f"\n{Fore.YELLOW}Start bot with this configuration? (y/n): {Style.RESET_ALL}").strip().lower()
    if confirm not in ['y', 'yes']:
        print(f"{Fore.YELLOW}Configuration cancelled.{Style.RESET_ALL}")
        sys.exit(0)
    
    return config
