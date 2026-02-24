"""
Stock discovery module for finding volatile stocks and popular stocks.
Uses web scraping to find daily volatile stocks with potential.
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict
import logging
from colorama import Fore, Style
from datetime import datetime

logger = logging.getLogger(__name__)


def get_top_volatile_stocks(limit: int = 20) -> List[str]:
    """
    Scrape top volatile stocks from financial websites.
    Returns list of stock symbols that are currently volatile.
    
    Args:
        limit: Number of stocks to return
        
    Returns:
        List of stock symbols
    """
    stocks = []
    
    try:
        # Method 1: Yahoo Finance Most Active (high volume = often volatile)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.BLUE}[SCRAPE]{Style.RESET_ALL} Fetching most active stocks from Yahoo Finance...")
        
        url = "https://finance.yahoo.com/most-active"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Find stock symbols in the table
                # Yahoo Finance uses data-symbol attribute or links
                symbols = []
                for link in soup.find_all('a', href=True):
                    href = link.get('href', '')
                    if '/quote/' in href:
                        symbol = href.split('/quote/')[-1].split('?')[0].split('.')[0]
                        if symbol and len(symbol) <= 5 and symbol.isalpha():
                            symbols.append(symbol.upper())
                
                # Also try finding in data attributes
                for element in soup.find_all(attrs={'data-symbol': True}):
                    symbol = element.get('data-symbol', '').upper()
                    if symbol and len(symbol) <= 5:
                        symbols.append(symbol)
                
                # Remove duplicates and get unique symbols
                unique_symbols = list(dict.fromkeys(symbols))[:limit]
                stocks.extend(unique_symbols)
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.GREEN}[OK]{Style.RESET_ALL} Found {len(unique_symbols)} stocks from Yahoo Finance")
        except Exception as e:
            logger.warning(f"Error scraping Yahoo Finance: {e}")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.YELLOW}[WARN]{Style.RESET_ALL} Yahoo Finance scrape failed: {e}")
        
        # Method 2: MarketWatch Most Active
        if len(stocks) < limit:
            try:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.BLUE}[SCRAPE]{Style.RESET_ALL} Fetching from MarketWatch...")
                url = "https://www.marketwatch.com/tools/screener/most-active"
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    # MarketWatch uses different structure, look for stock symbols
                    for element in soup.find_all(['td', 'span', 'a']):
                        text = element.get_text(strip=True)
                        # Look for patterns like "AAPL" or "MSFT"
                        if text and len(text) <= 5 and text.isalpha() and text.isupper():
                            if text not in stocks:
                                stocks.append(text)
                                if len(stocks) >= limit:
                                    break
                    
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.GREEN}[OK]{Style.RESET_ALL} Found additional stocks from MarketWatch")
            except Exception as e:
                logger.warning(f"Error scraping MarketWatch: {e}")
        
        # Method 3: Fallback to known volatile stocks if scraping fails
        if len(stocks) < limit:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.YELLOW}[FALLBACK]{Style.RESET_ALL} Using known volatile stocks...")
            known_volatile = [
                "TSLA", "NVDA", "AMD", "MARA", "RIOT", "COIN", "SOFI", "PLTR",
                "RIVN", "LCID", "F", "NIO", "SNAP", "TWTR", "RBLX", "HOOD",
                "SPCE", "AMC", "GME", "BBBY", "CLOV", "WISH", "CLNE", "WKHS"
            ]
            for symbol in known_volatile:
                if symbol not in stocks and len(stocks) < limit:
                    stocks.append(symbol)
        
        # Filter to ensure we have valid symbols (basic validation)
        valid_stocks = [s for s in stocks[:limit] if s and len(s) <= 5 and s.isalpha()]
        
        if valid_stocks:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.GREEN}[DONE]{Style.RESET_ALL} Found {len(valid_stocks)} volatile stocks")
            return valid_stocks
        else:
            # Ultimate fallback
            return ["TSLA", "NVDA", "AMD", "MARA", "RIOT", "COIN", "SOFI", "PLTR", 
                   "RIVN", "LCID", "F", "NIO", "SNAP", "RBLX", "HOOD", "SPCE", 
                   "AMC", "GME", "CLOV", "WISH"]
            
    except Exception as e:
        logger.error(f"Error in get_top_volatile_stocks: {e}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {Fore.RED}[ERROR]{Style.RESET_ALL} Stock discovery failed, using fallback list")
        # Return known volatile stocks as fallback
        return ["TSLA", "NVDA", "AMD", "MARA", "RIOT", "COIN", "SOFI", "PLTR", 
               "RIVN", "LCID", "F", "NIO", "SNAP", "RBLX", "HOOD", "SPCE", 
               "AMC", "GME", "CLOV", "WISH"]


def get_top_popular_stocks(limit: int = 20) -> List[str]:
    """
    Get list of most popular/well-known stocks.
    These are typically large-cap, stable companies.
    
    Args:
        limit: Number of stocks to return
        
    Returns:
        List of stock symbols
    """
    # Top stocks by market cap and popularity
    popular_stocks = [
        # Tech Giants
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "NFLX",
        # Finance
        "JPM", "BAC", "WFC", "GS", "V", "MA",
        # Healthcare
        "JNJ", "PFE", "UNH", "ABBV",
        # Consumer
        "WMT", "HD", "MCD", "SBUX", "NKE", "DIS",
        # Industrial
        "BA", "CAT", "GE",
        # Energy
        "XOM", "CVX",
        # Communication
        "T", "VZ", "CMCSA"
    ]
    
    return popular_stocks[:limit]


def validate_stock_symbol(symbol: str) -> bool:
    """
    Validate if a stock symbol is likely valid.
    Basic validation - checks format, not existence.
    
    Args:
        symbol: Stock symbol to validate
        
    Returns:
        True if symbol format is valid
    """
    if not symbol:
        return False
    
    symbol = symbol.strip().upper()
    
    # Basic format checks
    if len(symbol) < 1 or len(symbol) > 5:
        return False
    
    # Should be alphanumeric (some symbols have numbers like BRK.B)
    if not symbol.replace('.', '').isalnum():
        return False
    
    return True


def filter_valid_symbols(symbols: List[str]) -> List[str]:
    """
    Filter list of symbols to only include valid ones.
    
    Args:
        symbols: List of symbols to filter
        
    Returns:
        List of valid symbols
    """
    return [s.upper().strip() for s in symbols if validate_stock_symbol(s)]
