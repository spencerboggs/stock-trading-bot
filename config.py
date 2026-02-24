"""
Configuration file for the trading bot.
Contains all settings for symbols, APIs, risk parameters, and strategy configurations.
"""

# Alpaca Paper Trading API Configuration
ALPACA_API_KEY = "PKM7MZLSLOVL6VSQZEGIZH3KCR"
ALPACA_SECRET_KEY = "AWByQkkxoTQp8ahykedsEnKV4AfcAvW9CSGxYpeac7co"
ALPACA_BASE_URL = "https://paper-api.alpaca.markets/v2"

# Finnhub API (optional, for news/sentiment)
FINNHUB_API_KEY = ""  # Add your free API key if using sentiment analysis

# Extended Trading Symbols Pool (multi-symbol support)
# Popular stocks across different sectors for diversification
TRADING_SYMBOLS_POOL = [
    # Tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "NFLX", "AMD", "INTC",
    # Finance
    "JPM", "BAC", "WFC", "GS", "MS", "C", "V", "MA", "PYPL", "SQ",
    # Healthcare
    "JNJ", "PFE", "UNH", "ABBV", "MRK", "TMO", "ABT", "DHR", "BMY", "AMGN",
    # Consumer
    "WMT", "HD", "MCD", "SBUX", "NKE", "TGT", "COST", "LOW", "DIS", "NFLX",
    # Industrial
    "BA", "CAT", "GE", "HON", "MMM", "UPS", "RTX", "LMT", "DE", "EMR",
    # Energy
    "XOM", "CVX", "SLB", "EOG", "COP", "MPC", "VLO", "PSX", "HAL", "OXY",
    # Communication
    "T", "VZ", "CMCSA", "NFLX", "DIS", "FOX", "FOXA", "CHTR", "EA", "TTWO",
    # Materials
    "LIN", "APD", "ECL", "SHW", "PPG", "DD", "DOW", "FCX", "NEM", "VALE",
    # Utilities
    "NEE", "DUK", "SO", "D", "AEP", "EXC", "SRE", "XEL", "WEC", "ES",
    # Real Estate
    "AMT", "PLD", "EQIX", "PSA", "WELL", "SPG", "O", "AVB", "EQR", "VICI"
]

# Default symbols (will be overridden by user selection)
TRADING_SYMBOLS = ["AAPL", "MSFT", "GOOGL"]

# Risk Management Parameters (defaults - will be overridden by mode selection)
MAX_POSITION_SIZE = 10  # Max shares per symbol
MAX_PORTFOLIO_VALUE = 10000  # Max total portfolio value
STOP_LOSS_PERCENT = 0.02  # 2% stop loss
TAKE_PROFIT_PERCENT = 0.05  # 5% take profit

# Strategy Configuration (defaults - will be overridden by mode selection)
STRATEGY_CONFIG = {
    "type": "SMA_CROSSOVER",  # Options: SMA_CROSSOVER, EMA_CROSSOVER, RSI, BOLLINGER
    "sma_short": 5,
    "sma_long": 20,
    "ema_short": 12,
    "ema_long": 26,
    "rsi_period": 14,
    "rsi_oversold": 30,
    "rsi_overbought": 70,
    "bollinger_period": 20,
    "bollinger_std": 2,
    # Strategy behavior modes
    "trend_following": False,  # If True, buy when short > long (not just on crossover). More active trading.
    "crossover_only": True,  # If True, only signal on actual crossovers (more reliable and conservative)
    "min_price_change": 0.01,  # Minimum price change % to trigger signal (0.01 = 1%)
}

# Data Configuration
DATA_SOURCE = "yfinance"  # Options: yfinance, alpaca
HISTORICAL_DAYS = 100  # Days of historical data for backtesting
UPDATE_INTERVAL = 60  # Seconds between updates (60 = 1 minute)

# Backtesting Configuration
BACKTEST_START_DATE = "2025-01-01"
BACKTEST_END_DATE = "2025-12-31"
INITIAL_CASH = 10000

# Fast Test Mode (simulate minutes/seconds in seconds)
FAST_TEST_MODE = False
FAST_TEST_SPEED = 60  # 1 minute = 1 second in fast mode

# Logging Configuration
LOG_FILE = "trading_bot.log"
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
STATUS_UPDATE_INTERVAL = 10  # Print status update every N seconds (0 = every loop)

# Optional: LLM/Sentiment Integration
USE_SENTIMENT_ANALYSIS = False
SENTIMENT_WEIGHT = 0.3  # Weight of sentiment in final signal (0-1)

# Visualization
ENABLE_VISUALIZATION = False  # Set to True for matplotlib charts


# Preset Configuration Modes
PRESET_MODES = {
    "safe": {
        "name": "Safe Mode (Low Risk)",
        "description": "Conservative trading with strict risk management",
        "max_position_size": 5,
        "max_portfolio_value": 5000,
        "stop_loss_percent": 0.01,  # 1% stop loss
        "take_profit_percent": 0.03,  # 3% take profit
            "strategy_config": {
                "type": "SMA_CROSSOVER",
                "sma_short": 10,
                "sma_long": 30,
                "trend_following": False,
                "crossover_only": True,  # Only trade on crossovers (most reliable)
            },
        "update_interval": 120,  # 2 minutes
        "max_symbols": 5,  # Fewer symbols to focus on
    },
    "normal": {
        "name": "Normal Mode (Balanced)",
        "description": "Balanced risk/reward with moderate trading activity",
        "max_position_size": 10,
        "max_portfolio_value": 10000,
        "stop_loss_percent": 0.04,  # 4% stop loss (wider)
        "take_profit_percent": 0.08,  # 8% take profit (let winners run)
        "strategy_config": {
            "type": "SMA_CROSSOVER",
            "sma_short": 5,
            "sma_long": 20,
            "trend_following": False,
            "crossover_only": True,  # Crossover mode is more reliable
        },
        "update_interval": 60,  # 1 minute
        "max_symbols": 10,
    },
    "aggressive": {
        "name": "High Risk High Reward Mode",
        "description": "Aggressive trading with higher risk tolerance for maximum returns",
        "max_position_size": 20,
        "max_portfolio_value": 20000,
        "stop_loss_percent": 0.06,  # 6% stop loss (wider for volatile stocks)
        "take_profit_percent": 0.12,  # 12% take profit (let winners run)
        "strategy_config": {
            "type": "EMA_CROSSOVER",  # EMA is more responsive for aggressive trading
            "ema_short": 8,
            "ema_long": 15,
            "trend_following": False,
            "crossover_only": True,  # Crossover mode is more reliable
        },
        "update_interval": 30,  # 30 seconds (faster updates)
        "max_symbols": 20,  # More symbols for diversification
    }
}
