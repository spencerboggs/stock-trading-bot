"""
Automated optimization and tuning module for the trading bot.
Tests multiple configurations to find the best performing strategies.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import logging
from colorama import Fore, Style
import json
import os
from itertools import product

from backtest import Backtest
from config import PRESET_MODES, INITIAL_CASH, BACKTEST_START_DATE, BACKTEST_END_DATE

logger = logging.getLogger(__name__)


class StrategyOptimizer:
    """Automated strategy optimization engine."""
    
    def __init__(self, symbols: List[str], start_date: str = None, end_date: str = None):
        self.symbols = symbols
        self.start_date = start_date or BACKTEST_START_DATE
        self.end_date = end_date or BACKTEST_END_DATE
        self.results = []
        self.best_config = None
        self.best_return = float('-inf')
    
    def evaluate_performance(self, results: Dict) -> Dict:
        """
        Evaluate backtest results and calculate performance metrics.
        
        Args:
            results: Backtest results dictionary
            
        Returns:
            Dictionary with performance metrics
        """
        if not results or 'total_return' not in results:
            return {
                'total_return': -100,
                'sharpe_ratio': 0,
                'max_drawdown': 100,
                'win_rate': 0,
                'profit_factor': 0,
                'score': -1000
            }
        
        total_return = results.get('total_return', 0)
        trades = results.get('trades', [])
        daily_results = results.get('daily_results', [])
        
        # Calculate metrics
        num_trades = len(trades)
        if num_trades == 0:
            return {
                'total_return': total_return,
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'num_trades': 0,
                'score': total_return
            }
        
        # Win rate
        winning_trades = 0
        total_profit = 0
        total_loss = 0
        
        # Analyze trades
        for i in range(len(trades) - 1):
            trade = trades[i]
            next_trade = trades[i + 1] if i + 1 < len(trades) else None
            
            if trade['action'] == 'BUY' and next_trade and next_trade['action'] == 'SELL':
                profit = (next_trade['price'] - trade['price']) * trade['quantity']
                if profit > 0:
                    winning_trades += 1
                    total_profit += profit
                else:
                    total_loss += abs(profit)
        
        win_rate = (winning_trades / num_trades * 100) if num_trades > 0 else 0
        
        # Profit factor
        profit_factor = (total_profit / total_loss) if total_loss > 0 else (total_profit if total_profit > 0 else 0)
        
        # Max drawdown
        if daily_results:
            df = pd.DataFrame(daily_results)
            df['cumulative'] = df['total_value']
            df['running_max'] = df['cumulative'].expanding().max()
            df['drawdown'] = (df['cumulative'] - df['running_max']) / df['running_max'] * 100
            max_drawdown = df['drawdown'].min()
        else:
            max_drawdown = 0
        
        # Sharpe ratio (simplified)
        if len(daily_results) > 1:
            returns = pd.Series([r['pnl_percent'] for r in daily_results])
            if returns.std() > 0:
                sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252)  # Annualized
            else:
                sharpe_ratio = 0
        else:
            sharpe_ratio = 0
        
        # Composite score (weighted combination of metrics)
        # Higher is better
        score = (
            total_return * 0.4 +  # 40% weight on total return
            sharpe_ratio * 10 * 0.2 +  # 20% weight on risk-adjusted return
            win_rate * 0.2 +  # 20% weight on win rate
            min(profit_factor, 5) * 10 * 0.1 +  # 10% weight on profit factor (capped at 5)
            max(max_drawdown, -50) * 0.1  # 10% weight on drawdown (penalty, capped at -50%)
        )
        
        return {
            'total_return': total_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'num_trades': num_trades,
            'total_profit': total_profit,
            'total_loss': total_loss,
            'score': score
        }
    
    def test_configuration(self, config: Dict, verbose: bool = False) -> Tuple[Dict, Dict]:
        """
        Test a single configuration.
        
        Args:
            config: Configuration dictionary
            verbose: Print detailed output
            
        Returns:
            Tuple of (results_dict, metrics_dict)
        """
        if verbose:
            print(f"\n{Fore.CYAN}[TEST]{Style.RESET_ALL} Testing configuration...")
            print(f"  Strategy: {config.get('strategy_type', 'N/A')}")
            print(f"  Max Position: {config.get('max_position_size', 'N/A')}")
            print(f"  Stop Loss: {config.get('stop_loss_percent', 0)*100:.1f}%")
            print(f"  Take Profit: {config.get('take_profit_percent', 0)*100:.1f}%")
        
        try:
            # Create backtest instance
            backtest = Backtest(
                symbols=self.symbols,
                strategy_type=config.get('strategy_type', 'SMA_CROSSOVER'),
                initial_cash=INITIAL_CASH,
                start_date=self.start_date,
                end_date=self.end_date
            )
            
            # Update strategy config temporarily
            from config import STRATEGY_CONFIG
            import config as cfg
            
            # Save original values
            original_strategy_config = STRATEGY_CONFIG.copy()
            original_stop_loss = cfg.STOP_LOSS_PERCENT
            original_take_profit = cfg.TAKE_PROFIT_PERCENT
            original_max_position = cfg.MAX_POSITION_SIZE
            
            # Update with test config
            strategy_config_update = config.get('strategy_config', {})
            for key, value in strategy_config_update.items():
                STRATEGY_CONFIG[key] = value
            
            cfg.STOP_LOSS_PERCENT = config.get('stop_loss_percent', cfg.STOP_LOSS_PERCENT)
            cfg.TAKE_PROFIT_PERCENT = config.get('take_profit_percent', cfg.TAKE_PROFIT_PERCENT)
            cfg.MAX_POSITION_SIZE = config.get('max_position_size', cfg.MAX_POSITION_SIZE)
            
            # Also update portfolio risk parameters
            from portfolio import STOP_LOSS_PERCENT as PORTFOLIO_SL, TAKE_PROFIT_PERCENT as PORTFOLIO_TP
            original_portfolio_sl = PORTFOLIO_SL if hasattr(cfg, 'STOP_LOSS_PERCENT') else None
            original_portfolio_tp = PORTFOLIO_TP if hasattr(cfg, 'TAKE_PROFIT_PERCENT') else None
            
            try:
                # Run backtest
                results = backtest.run(verbose=False)
            finally:
                # Always restore original config, even if backtest fails
                STRATEGY_CONFIG.clear()
                STRATEGY_CONFIG.update(original_strategy_config)
                cfg.STOP_LOSS_PERCENT = original_stop_loss
                cfg.TAKE_PROFIT_PERCENT = original_take_profit
                cfg.MAX_POSITION_SIZE = original_max_position
            
            # Evaluate performance
            metrics = self.evaluate_performance(results)
            
            if verbose:
                print(f"  {Fore.GREEN}Return: {metrics['total_return']:.2f}%{Style.RESET_ALL}")
                print(f"  Win Rate: {metrics['win_rate']:.1f}%")
                print(f"  Score: {metrics['score']:.2f}")
            
            return results, metrics
            
        except Exception as e:
            logger.error(f"Error testing configuration: {e}")
            if verbose:
                print(f"  {Fore.RED}Error: {e}{Style.RESET_ALL}")
            return {}, self.evaluate_performance({})
    
    def generate_configurations(self, mode: str = "grid") -> List[Dict]:
        """
        Generate configurations to test.
        
        Args:
            mode: "grid" for grid search, "random" for random search, "preset" for preset modes
            
        Returns:
            List of configuration dictionaries
        """
        configs = []
        
        if mode == "preset":
            # Test all preset modes
            for mode_key, preset in PRESET_MODES.items():
                config = {
                    'name': f"Preset_{mode_key}",
                    'strategy_type': preset['strategy_config']['type'],
                    'max_position_size': preset['max_position_size'],
                    'stop_loss_percent': preset['stop_loss_percent'],
                    'take_profit_percent': preset['take_profit_percent'],
                    'strategy_config': preset['strategy_config'].copy(),
                    'update_interval': preset['update_interval']
                }
                configs.append(config)
        
        elif mode == "grid":
            # Grid search over parameter space
            strategy_types = ["SMA_CROSSOVER", "EMA_CROSSOVER", "RSI", "BOLLINGER"]
            sma_shorts = [3, 5, 8, 10, 12]
            sma_longs = [15, 20, 25, 30]
            stop_losses = [0.01, 0.02, 0.03, 0.05]
            take_profits = [0.03, 0.05, 0.07, 0.10]
            max_positions = [5, 10, 15, 20]
            trend_following = [True, False]
            
            # Generate combinations (limit to avoid too many tests)
            count = 0
            max_configs = 100  # Limit grid search
            
            for strategy, short, long, sl, tp, max_pos, trend in product(
                strategy_types[:2],  # Limit to SMA and EMA for now
                sma_shorts[:3],
                sma_longs[:3],
                stop_losses[:2],
                take_profits[:2],
                max_positions[:2],
                trend_following
            ):
                if count >= max_configs:
                    break
                
                config = {
                    'name': f"Grid_{count}",
                    'strategy_type': strategy,
                    'max_position_size': max_pos,
                    'stop_loss_percent': sl,
                    'take_profit_percent': tp,
                    'strategy_config': {
                        'type': strategy,
                        'sma_short': short,
                        'sma_long': long,
                        'trend_following': trend,
                        'crossover_only': not trend
                    }
                }
                configs.append(config)
                count += 1
        
        elif mode == "focused":
            # Focused search around promising parameters
            base_configs = [
                {
                    'name': 'Focused_1',
                    'strategy_type': 'EMA_CROSSOVER',
                    'max_position_size': 10,
                    'stop_loss_percent': 0.02,
                    'take_profit_percent': 0.05,
                    'strategy_config': {
                        'type': 'EMA_CROSSOVER',
                        'ema_short': 8,
                        'ema_long': 15,
                        'trend_following': True
                    }
                },
                {
                    'name': 'Focused_2',
                    'strategy_type': 'SMA_CROSSOVER',
                    'max_position_size': 15,
                    'stop_loss_percent': 0.03,
                    'take_profit_percent': 0.07,
                    'strategy_config': {
                        'type': 'SMA_CROSSOVER',
                        'sma_short': 5,
                        'sma_long': 20,
                        'trend_following': True
                    }
                },
                {
                    'name': 'Focused_3',
                    'strategy_type': 'RSI',
                    'max_position_size': 10,
                    'stop_loss_percent': 0.02,
                    'take_profit_percent': 0.05,
                    'strategy_config': {
                        'type': 'RSI',
                        'rsi_period': 14,
                        'rsi_oversold': 30,
                        'rsi_overbought': 70
                    }
                }
            ]
            
            # Add variations
            for base in base_configs:
                configs.append(base)
                # Variation 1: Different stop loss
                var1 = base.copy()
                var1['name'] = base['name'] + '_var1'
                var1['stop_loss_percent'] = base['stop_loss_percent'] * 1.5
                configs.append(var1)
                
                # Variation 2: Different take profit
                var2 = base.copy()
                var2['name'] = base['name'] + '_var2'
                var2['take_profit_percent'] = base['take_profit_percent'] * 1.5
                configs.append(var2)
        
        return configs
    
    def optimize(self, mode: str = "focused", max_configs: int = 50, verbose: bool = True) -> Dict:
        """
        Run optimization to find best configuration.
        
        Args:
            mode: Optimization mode ("preset", "grid", "focused")
            max_configs: Maximum number of configurations to test
            verbose: Print progress
            
        Returns:
            Dictionary with best configuration and results
        """
        print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}STRATEGY OPTIMIZATION{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"Symbols: {', '.join(self.symbols)}")
        print(f"Date Range: {self.start_date} to {self.end_date}")
        print(f"Mode: {mode}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")
        
        # Generate configurations
        if verbose:
            print(f"{Fore.BLUE}[GENERATE]{Style.RESET_ALL} Generating configurations...")
        configs = self.generate_configurations(mode)
        configs = configs[:max_configs]  # Limit number of tests
        
        print(f"{Fore.GREEN}[FOUND]{Style.RESET_ALL} {len(configs)} configurations to test\n")
        
        # Test each configuration
        best_score = float('-inf')
        best_config = None
        best_metrics = None
        
        for i, config in enumerate(configs, 1):
            if verbose:
                print(f"{Fore.YELLOW}[{i}/{len(configs)}]{Style.RESET_ALL} Testing: {config.get('name', 'Config')}")
            
            results, metrics = self.test_configuration(config, verbose=False)
            
            # Store results
            self.results.append({
                'config': config,
                'results': results,
                'metrics': metrics
            })
            
            # Track best
            if metrics['score'] > best_score:
                best_score = metrics['score']
                best_config = config
                best_metrics = metrics
            
            # Print progress
            if verbose and i % 5 == 0:
                print(f"  {Fore.GREEN}Best so far: {best_metrics['total_return']:.2f}% return, Score: {best_score:.2f}{Style.RESET_ALL}")
        
        self.best_config = best_config
        self.best_return = best_metrics['total_return'] if best_metrics else 0
        
        # Print summary
        print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}BEST CONFIGURATION FOUND{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"Name: {best_config.get('name', 'N/A')}")
        print(f"Strategy: {best_config.get('strategy_type', 'N/A')}")
        print(f"Max Position: {best_config.get('max_position_size', 'N/A')}")
        print(f"Stop Loss: {best_config.get('stop_loss_percent', 0)*100:.1f}%")
        print(f"Take Profit: {best_config.get('take_profit_percent', 0)*100:.1f}%")
        print(f"\n{Fore.GREEN}Performance Metrics:{Style.RESET_ALL}")
        print(f"  Total Return: {best_metrics['total_return']:.2f}%")
        print(f"  Sharpe Ratio: {best_metrics['sharpe_ratio']:.2f}")
        print(f"  Max Drawdown: {best_metrics['max_drawdown']:.2f}%")
        print(f"  Win Rate: {best_metrics['win_rate']:.1f}%")
        print(f"  Profit Factor: {best_metrics['profit_factor']:.2f}")
        print(f"  Number of Trades: {best_metrics['num_trades']}")
        print(f"  Composite Score: {best_metrics['score']:.2f}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")
        
        return {
            'best_config': best_config,
            'best_metrics': best_metrics,
            'all_results': self.results
        }
    
    def save_results(self, filename: str = "optimization_results.json"):
        """Save optimization results to file."""
        output = {
            'timestamp': datetime.now().isoformat(),
            'symbols': self.symbols,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'best_config': self.best_config,
            'best_return': self.best_return,
            'results': []
        }
        
        for result in self.results:
            output['results'].append({
                'config_name': result['config'].get('name', 'Unknown'),
                'config': result['config'],
                'metrics': result['metrics']
            })
        
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"{Fore.GREEN}[SAVED]{Style.RESET_ALL} Results saved to {filename}")
    
    def get_top_configs(self, n: int = 5) -> List[Dict]:
        """Get top N configurations by score."""
        sorted_results = sorted(self.results, key=lambda x: x['metrics']['score'], reverse=True)
        return sorted_results[:n]
