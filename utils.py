"""
Utility functions for data fetching, logging, and general helpers.
Supports yfinance and optional Finnhub for news/sentiment.
"""

import logging
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import requests
from colorama import init, Fore, Style
import os
import pickle
import hashlib
from config import FINNHUB_API_KEY, USE_SENTIMENT_ANALYSIS, LOG_FILE, LOG_LEVEL

# Initialize colorama for Windows support
init(autoreset=True)

# Setup logging
log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(
    filename=LOG_FILE,
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# Data cache directory
CACHE_DIR = "data_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def _get_cache_key(symbols: List[str], days: int) -> str:
    """Generate cache key for symbols and days."""
    key_str = f"{sorted(symbols)}_{days}"
    return hashlib.md5(key_str.encode()).hexdigest()

def _load_from_cache(cache_key: str) -> Optional[Dict[str, pd.DataFrame]]:
    """Load data from cache if available."""
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.pkl")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'rb') as f:
                data = pickle.load(f)
                # Check if cache is recent (within 1 hour)
                cache_time = os.path.getmtime(cache_file)
                if (datetime.now().timestamp() - cache_time) < 3600:
                    return data
        except Exception as e:
            logger.warning(f"Error loading cache: {e}")
    return None

def _save_to_cache(cache_key: str, data: Dict[str, pd.DataFrame]):
    """Save data to cache."""
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.pkl")
    try:
        with open(cache_file, 'wb') as f:
            pickle.dump(data, f)
    except Exception as e:
        logger.warning(f"Error saving cache: {e}")


def fetch_historical_data(symbols: List[str], days: int = 100, use_cache: bool = True) -> Dict[str, pd.DataFrame]:
    """
    Fetch historical stock data for multiple symbols using yfinance.
    Uses caching to speed up repeated requests.
    
    Args:
        symbols: List of stock symbols
        days: Number of days of historical data
        use_cache: Whether to use cached data (default True)
        
    Returns:
        Dictionary mapping symbol to DataFrame with OHLCV data
    """
    # Try to load from cache first
    if use_cache:
        cache_key = _get_cache_key(symbols, days)
        cached_data = _load_from_cache(cache_key)
        if cached_data is not None:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.GREEN}[CACHE]{Style.RESET_ALL} Loaded historical data from cache for {len(symbols)} symbol(s)")
            return cached_data
    
    # Fetch fresh data
    data = {}
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.BLUE}[FETCH]{Style.RESET_ALL} Fetching historical data for {len(symbols)} symbol(s)...")
    for i, symbol in enumerate(symbols, 1):
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}]   [{i}/{len(symbols)}] Fetching {symbol}...")
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=f"{days}d")
            if not hist.empty:
                # Rename columns to lowercase for consistency
                hist.columns = [col.lower() for col in hist.columns]
                # Remove timezone info if present to avoid comparison issues
                if hist.index.tz is not None:
                    hist.index = hist.index.tz_convert('UTC').tz_localize(None)
                data[symbol] = hist
                print(f"[{datetime.now().strftime('%H:%M:%S')}]   {Fore.GREEN}[OK]{Style.RESET_ALL} {symbol}: {len(hist)} days of data fetched")
                logger.info(f"Fetched {len(hist)} days of data for {symbol}")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}]   {Fore.YELLOW}[WARN]{Style.RESET_ALL} {symbol}: No data returned")
                logger.warning(f"No data returned for {symbol}")
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}]   {Fore.RED}[ERROR]{Style.RESET_ALL} {symbol}: Error - {e}")
            logger.error(f"Error fetching historical data for {symbol}: {e}")
    
    # Save to cache
    if use_cache and data:
        cache_key = _get_cache_key(symbols, days)
        _save_to_cache(cache_key, data)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.GREEN}[CACHE]{Style.RESET_ALL} Saved data to cache")
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.GREEN}[DONE]{Style.RESET_ALL} Historical data fetch complete: {len(data)}/{len(symbols)} symbols")
    return data


def fetch_current_prices(symbols: List[str]) -> Dict[str, float]:
    """
    Fetch near real-time stock prices for multiple symbols using yfinance.
    
    Args:
        symbols: List of stock symbols
        
    Returns:
        Dictionary mapping symbol to current price
    """
    prices = {}
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.history(period="1d", interval="1m")
            if not info.empty:
                current_price = info['Close'].iloc[-1]
                prices[symbol] = float(current_price)
            else:
                # Fallback to regular history
                hist = ticker.history(period="1d")
                if not hist.empty:
                    prices[symbol] = float(hist['Close'].iloc[-1])
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.RED}[ERROR]{Style.RESET_ALL} Error fetching price for {symbol}: {e}")
            logger.error(f"Error fetching current price for {symbol}: {e}")
    return prices


def fetch_news_sentiment(symbol: str) -> Optional[float]:
    """
    Fetch news sentiment for a symbol using Finnhub API (optional).
    Returns sentiment score between -1 (negative) and 1 (positive).
    
    Args:
        symbol: Stock symbol
        
    Returns:
        Sentiment score or None if unavailable
    """
    if not USE_SENTIMENT_ANALYSIS or not FINNHUB_API_KEY:
        return None
    
    try:
        url = f"https://finnhub.io/api/v1/news-sentiment?symbol={symbol}&token={FINNHUB_API_KEY}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            # Extract sentiment score if available
            if 'sentiment' in data and 'score' in data['sentiment']:
                return float(data['sentiment']['score'])
    except Exception as e:
        logger.warning(f"Error fetching sentiment for {symbol}: {e}")
    
    return None


def log_trade(action: str, symbol: str, qty: int, price: float, reason: str = ""):
    """
    Log trade execution to both console and file.
    
    Args:
        action: BUY, SELL, or HOLD
        symbol: Stock symbol
        qty: Quantity of shares
        price: Execution price
        reason: Optional reason for the trade
    """
    message = f"{action} {qty} shares of {symbol} at ${price:.2f}"
    if reason:
        message += f" | Reason: {reason}"
    
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")
    logger.info(message)


def log_signal(symbol: str, signal: str, price: float, indicators: Dict = None):
    """
    Log trading signal to console and file.
    
    Args:
        symbol: Stock symbol
        signal: BUY, SELL, or HOLD
        price: Current price
        indicators: Optional dictionary of indicator values
    """
    message = f"{symbol} | Signal: {signal} | Price: ${price:.2f}"
    if indicators:
        indicator_str = " | ".join([f"{k}: {v:.2f}" for k, v in indicators.items()])
        message += f" | {indicator_str}"
    
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")
    logger.info(message)


def check_risk(current_position: int, max_position: int, 
               portfolio_value: float = None, max_portfolio_value: float = None) -> bool:
    """
    Check if a trade passes risk management rules.
    
    Args:
        current_position: Current position size
        max_position: Maximum allowed position size
        portfolio_value: Current portfolio value (optional)
        max_portfolio_value: Maximum portfolio value (optional)
        
    Returns:
        True if trade passes risk checks, False otherwise
    """
    if abs(current_position) >= max_position:
        logger.warning(f"Risk check failed: Position size {current_position} exceeds max {max_position}")
        return False
    
    if portfolio_value and max_portfolio_value:
        if portfolio_value > max_portfolio_value:
            logger.warning(f"Risk check failed: Portfolio value {portfolio_value} exceeds max {max_portfolio_value}")
            return False
    
    return True


def calculate_pnl(entry_price: float, current_price: float, quantity: int) -> float:
    """
    Calculate profit and loss for a position.
    
    Args:
        entry_price: Entry price per share
        current_price: Current price per share
        quantity: Number of shares (positive for long, negative for short)
        
    Returns:
        PnL in dollars
    """
    return (current_price - entry_price) * quantity


def format_currency(value: float) -> str:
    """Format a float as currency string."""
    return f"${value:,.2f}"
