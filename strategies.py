"""
Strategy module with technical indicators and signal generation.
Supports SMA, EMA, RSI, Bollinger Bands, and modular strategy framework.
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
from config import STRATEGY_CONFIG, SENTIMENT_WEIGHT, USE_SENTIMENT_ANALYSIS
from utils import fetch_news_sentiment


def calculate_sma(data: pd.DataFrame, period: int) -> pd.Series:
    """Calculate Simple Moving Average."""
    return data['close'].rolling(window=period).mean()


def calculate_ema(data: pd.DataFrame, period: int) -> pd.Series:
    """Calculate Exponential Moving Average."""
    return data['close'].ewm(span=period, adjust=False).mean()


def calculate_rsi(data: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index (RSI).
    
    Args:
        data: DataFrame with 'close' column
        period: RSI period (default 14)
        
    Returns:
        RSI values as Series
    """
    delta = data['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_atr(data: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Average True Range (ATR) for volatility-based stops.
    
    Args:
        data: DataFrame with 'high', 'low', 'close' columns
        period: ATR period (default 14)
        
    Returns:
        ATR values as Series
    """
    high = data['high']
    low = data['low']
    close = data['close']
    
    # Calculate True Range
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Calculate ATR as moving average of TR
    atr = tr.rolling(window=period).mean()
    return atr


def calculate_bollinger_bands(data: pd.DataFrame, period: int = 20, std_dev: int = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate Bollinger Bands.
    
    Args:
        data: DataFrame with 'close' column
        period: Moving average period
        std_dev: Standard deviation multiplier
        
    Returns:
        Tuple of (upper_band, middle_band, lower_band)
    """
    middle_band = calculate_sma(data, period)
    std = data['close'].rolling(window=period).std()
    upper_band = middle_band + (std * std_dev)
    lower_band = middle_band - (std * std_dev)
    return upper_band, middle_band, lower_band


def sma_crossover_strategy(data: pd.DataFrame, short_window: int = None, long_window: int = None) -> Tuple[str, Dict]:
    """
    SIMPLIFIED SMA Crossover Strategy - Proven approach:
    - BUY when short SMA crosses ABOVE long SMA (golden cross)
    - SELL when short SMA crosses BELOW long SMA (death cross)
    - Uses RSI filter to avoid buying in overbought conditions
    - Only trades on actual crossovers (more reliable)
    
    Args:
        data: DataFrame with 'close' column
        short_window: Short SMA period
        long_window: Long SMA period
        
    Returns:
        Tuple of (signal, indicators_dict)
    """
    if short_window is None:
        short_window = STRATEGY_CONFIG.get("sma_short", 5)
    if long_window is None:
        long_window = STRATEGY_CONFIG.get("sma_long", 20)
    
    if len(data) < long_window:
        return "HOLD", {"reason": "Insufficient data"}
    
    data = data.copy()
    data['sma_short'] = calculate_sma(data, short_window)
    data['sma_long'] = calculate_sma(data, long_window)
    
    # Calculate RSI for filter
    rsi_period = STRATEGY_CONFIG.get("rsi_period", 14)
    if len(data) >= rsi_period:
        data['rsi'] = calculate_rsi(data, rsi_period)
        current_rsi = data['rsi'].iloc[-1]
    else:
        current_rsi = 50  # Neutral if not enough data
    
    # Get current and previous values
    current_short = data['sma_short'].iloc[-1]
    current_long = data['sma_long'].iloc[-1]
    prev_short = data['sma_short'].iloc[-2] if len(data) > 1 else current_short
    prev_long = data['sma_long'].iloc[-2] if len(data) > 1 else current_long
    current_price = data['close'].iloc[-1]
    
    # Check strategy mode
    trend_following = STRATEGY_CONFIG.get("trend_following", False)  # Default to crossover only
    crossover_only = STRATEGY_CONFIG.get("crossover_only", True)  # Default to crossover only
    
    signal = "HOLD"
    reason = "No signal"
    
    if crossover_only or not trend_following:
        # STRICT CROSSOVER MODE - Only trade on actual crossovers (most reliable)
        # Golden cross: short crosses above long
        if current_short > current_long and prev_short <= prev_long:
            # Additional filter: Don't buy if RSI is overbought (>70)
            if current_rsi < 70:
                signal = "BUY"
                reason = f"Golden cross: Short({current_short:.2f}) crossed above Long({current_long:.2f}), RSI={current_rsi:.1f}"
            else:
                signal = "HOLD"
                reason = f"Golden cross but RSI overbought ({current_rsi:.1f}) - waiting"
        # Death cross: short crosses below long
        elif current_short < current_long and prev_short >= prev_long:
            # Additional filter: Don't sell if RSI is oversold (<30)
            if current_rsi > 30:
                signal = "SELL"
                reason = f"Death cross: Short({current_short:.2f}) crossed below Long({current_long:.2f}), RSI={current_rsi:.1f}"
            else:
                signal = "HOLD"
                reason = f"Death cross but RSI oversold ({current_rsi:.1f}) - waiting"
        else:
            if current_short > current_long:
                reason = f"Uptrend (Short > Long) but no crossover yet"
            elif current_short < current_long:
                reason = f"Downtrend (Short < Long) but no crossover yet"
            else:
                reason = "SMAs equal"
    else:
        # TREND FOLLOWING MODE - More active trading
        # Buy when in uptrend (short > long) and price is reasonable
        if current_short > current_long:
            # Only buy if RSI is not overbought
            if current_rsi < 70:
                signal = "BUY"
                reason = f"Uptrend: Short({current_short:.2f}) > Long({current_long:.2f}), RSI={current_rsi:.1f}"
            else:
                signal = "HOLD"
                reason = f"Uptrend but RSI overbought ({current_rsi:.1f})"
        elif current_short < current_long:
            # Only sell if RSI is not oversold
            if current_rsi > 30:
                signal = "SELL"
                reason = f"Downtrend: Short({current_short:.2f}) < Long({current_long:.2f}), RSI={current_rsi:.1f}"
            else:
                signal = "HOLD"
                reason = f"Downtrend but RSI oversold ({current_rsi:.1f})"
        else:
            reason = "SMAs equal - no trend"
    
    indicators = {
        "SMA_short": current_short,
        "SMA_long": current_long,
        "RSI": current_rsi,
        "Price": current_price,
        "reason": reason
    }
    
    return signal, indicators


def ema_crossover_strategy(data: pd.DataFrame, short_window: int = None, long_window: int = None) -> Tuple[str, Dict]:
    """
    SIMPLIFIED EMA Crossover Strategy - Similar to SMA but more responsive:
    - BUY when short EMA crosses ABOVE long EMA (golden cross)
    - SELL when short EMA crosses BELOW long EMA (death cross)
    - Uses RSI filter to avoid buying in overbought conditions
    
    Args:
        data: DataFrame with 'close' column
        short_window: Short EMA period
        long_window: Long EMA period
        
    Returns:
        Tuple of (signal, indicators_dict)
    """
    if short_window is None:
        short_window = STRATEGY_CONFIG.get("ema_short", 12)
    if long_window is None:
        long_window = STRATEGY_CONFIG.get("ema_long", 26)
    
    if len(data) < long_window:
        return "HOLD", {"reason": "Insufficient data"}
    
    data = data.copy()
    data['ema_short'] = calculate_ema(data, short_window)
    data['ema_long'] = calculate_ema(data, long_window)
    
    # Calculate RSI for filter
    rsi_period = STRATEGY_CONFIG.get("rsi_period", 14)
    if len(data) >= rsi_period:
        data['rsi'] = calculate_rsi(data, rsi_period)
        current_rsi = data['rsi'].iloc[-1]
    else:
        current_rsi = 50  # Neutral if not enough data
    
    current_short = data['ema_short'].iloc[-1]
    current_long = data['ema_long'].iloc[-1]
    prev_short = data['ema_short'].iloc[-2] if len(data) > 1 else current_short
    prev_long = data['ema_long'].iloc[-2] if len(data) > 1 else current_long
    current_price = data['close'].iloc[-1]
    
    # Check strategy mode
    trend_following = STRATEGY_CONFIG.get("trend_following", False)
    crossover_only = STRATEGY_CONFIG.get("crossover_only", True)
    
    signal = "HOLD"
    reason = "No signal"
    
    if crossover_only or not trend_following:
        # STRICT CROSSOVER MODE
        if current_short > current_long and prev_short <= prev_long:
            if current_rsi < 70:
                signal = "BUY"
                reason = f"EMA Golden cross: Short({current_short:.2f}) crossed above Long({current_long:.2f}), RSI={current_rsi:.1f}"
            else:
                signal = "HOLD"
                reason = f"EMA Golden cross but RSI overbought ({current_rsi:.1f})"
        elif current_short < current_long and prev_short >= prev_long:
            if current_rsi > 30:
                signal = "SELL"
                reason = f"EMA Death cross: Short({current_short:.2f}) crossed below Long({current_long:.2f}), RSI={current_rsi:.1f}"
            else:
                signal = "HOLD"
                reason = f"EMA Death cross but RSI oversold ({current_rsi:.1f})"
        else:
            if current_short > current_long:
                reason = f"EMA Uptrend but no crossover yet"
            elif current_short < current_long:
                reason = f"EMA Downtrend but no crossover yet"
            else:
                reason = "EMAs equal"
    else:
        # TREND FOLLOWING MODE
        if current_short > current_long:
            if current_rsi < 70:
                signal = "BUY"
                reason = f"EMA Uptrend: Short({current_short:.2f}) > Long({current_long:.2f}), RSI={current_rsi:.1f}"
            else:
                signal = "HOLD"
                reason = f"EMA Uptrend but RSI overbought ({current_rsi:.1f})"
        elif current_short < current_long:
            if current_rsi > 30:
                signal = "SELL"
                reason = f"EMA Downtrend: Short({current_short:.2f}) < Long({current_long:.2f}), RSI={current_rsi:.1f}"
            else:
                signal = "HOLD"
                reason = f"EMA Downtrend but RSI oversold ({current_rsi:.1f})"
        else:
            reason = "EMAs equal - no trend"
    
    indicators = {
        "EMA_short": current_short,
        "EMA_long": current_long,
        "RSI": current_rsi,
        "Price": current_price,
        "reason": reason
    }
    
    return signal, indicators


def rsi_strategy(data: pd.DataFrame, period: int = None, oversold: int = None, overbought: int = None) -> Tuple[str, Dict]:
    """
    RSI Strategy: BUY when RSI < oversold, SELL when RSI > overbought.
    
    Args:
        data: DataFrame with 'close' column
        period: RSI period
        oversold: Oversold threshold
        overbought: Overbought threshold
        
    Returns:
        Tuple of (signal, indicators_dict)
    """
    if period is None:
        period = STRATEGY_CONFIG.get("rsi_period", 14)
    if oversold is None:
        oversold = STRATEGY_CONFIG.get("rsi_oversold", 30)
    if overbought is None:
        overbought = STRATEGY_CONFIG.get("rsi_overbought", 70)
    
    if len(data) < period:
        return "HOLD", {}
    
    data = data.copy()
    data['rsi'] = calculate_rsi(data, period)
    current_rsi = data['rsi'].iloc[-1]
    
    if current_rsi < oversold:
        signal = "BUY"
    elif current_rsi > overbought:
        signal = "SELL"
    else:
        signal = "HOLD"
    
    indicators = {
        "RSI": current_rsi,
        "Price": data['close'].iloc[-1]
    }
    
    return signal, indicators


def bollinger_bands_strategy(data: pd.DataFrame, period: int = None, std_dev: int = None) -> Tuple[str, Dict]:
    """
    Bollinger Bands Strategy: BUY when price touches lower band, SELL when price touches upper band.
    
    Args:
        data: DataFrame with 'close' column
        period: Moving average period
        std_dev: Standard deviation multiplier
        
    Returns:
        Tuple of (signal, indicators_dict)
    """
    if period is None:
        period = STRATEGY_CONFIG.get("bollinger_period", 20)
    if std_dev is None:
        std_dev = STRATEGY_CONFIG.get("bollinger_std", 2)
    
    if len(data) < period:
        return "HOLD", {}
    
    data = data.copy()
    upper, middle, lower = calculate_bollinger_bands(data, period, std_dev)
    
    current_price = data['close'].iloc[-1]
    current_upper = upper.iloc[-1]
    current_lower = lower.iloc[-1]
    current_middle = middle.iloc[-1]
    
    # Price touches or goes below lower band (oversold)
    if current_price <= current_lower:
        signal = "BUY"
    # Price touches or goes above upper band (overbought)
    elif current_price >= current_upper:
        signal = "SELL"
    else:
        signal = "HOLD"
    
    indicators = {
        "BB_Upper": current_upper,
        "BB_Middle": current_middle,
        "BB_Lower": current_lower,
        "Price": current_price
    }
    
    return signal, indicators


def generate_signal(data: pd.DataFrame, symbol: str, strategy_type: str = None) -> Tuple[str, Dict]:
    """
    Main signal generation function that routes to appropriate strategy.
    Optionally incorporates sentiment analysis if enabled.
    
    Args:
        data: DataFrame with 'close' column
        symbol: Stock symbol (for sentiment lookup)
        strategy_type: Strategy type to use (defaults to config)
        
    Returns:
        Tuple of (signal, indicators_dict)
    """
    if strategy_type is None:
        strategy_type = STRATEGY_CONFIG.get("type", "SMA_CROSSOVER")
    
    # Generate base signal from technical indicators
    if strategy_type == "SMA_CROSSOVER":
        signal, indicators = sma_crossover_strategy(data)
    elif strategy_type == "EMA_CROSSOVER":
        signal, indicators = ema_crossover_strategy(data)
    elif strategy_type == "RSI":
        signal, indicators = rsi_strategy(data)
    elif strategy_type == "BOLLINGER":
        signal, indicators = bollinger_bands_strategy(data)
    else:
        # Default to SMA crossover
        signal, indicators = sma_crossover_strategy(data)
    
    # Optional: Incorporate sentiment analysis
    if USE_SENTIMENT_ANALYSIS:
        sentiment = fetch_news_sentiment(symbol)
        if sentiment is not None:
            indicators["Sentiment"] = sentiment
            
            # Adjust signal based on sentiment
            if sentiment > 0.2 and signal == "HOLD":
                signal = "BUY"  # Positive sentiment can trigger buy
            elif sentiment < -0.2 and signal == "HOLD":
                signal = "SELL"  # Negative sentiment can trigger sell
            elif sentiment > 0.5 and signal == "SELL":
                signal = "HOLD"  # Strong positive sentiment can prevent sell
            elif sentiment < -0.5 and signal == "BUY":
                signal = "HOLD"  # Strong negative sentiment can prevent buy
    
    return signal, indicators
