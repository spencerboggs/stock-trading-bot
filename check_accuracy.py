"""Quick check of backtest accuracy"""
import json

# Load results
with open('optimization_results.json') as f:
    data = json.load(f)

# Get first result
result = data['results'][0]
metrics = result['metrics']
config = result['config']

print("=" * 60)
print("BACKTEST ACCURACY CHECK")
print("=" * 60)
print(f"\nConfig: {result['config_name']}")
print(f"Strategy: {config.get('strategy_type', 'N/A')}")
print(f"\nResults:")
print(f"  Return: {metrics['total_return']:.2f}%")
print(f"  Win Rate: {metrics['win_rate']:.1f}%")
print(f"  Trades: {metrics['num_trades']}")
print(f"  Profit Factor: {metrics['profit_factor']:.3f}")
print(f"  Total Profit: ${metrics['total_profit']:.2f}")
print(f"  Total Loss: ${metrics['total_loss']:.2f}")

# Check for red flags
print("\n" + "=" * 60)
print("ACCURACY CHECKS:")
print("=" * 60)

issues = []

if metrics['win_rate'] < 10:
    issues.append(f"WARNING: Win rate {metrics['win_rate']:.1f}% is extremely low - strategy may be broken")

if metrics['profit_factor'] < 0.5:
    issues.append(f"WARNING: Profit factor {metrics['profit_factor']:.3f} is terrible - losing way more than winning")

if metrics['num_trades'] < 10:
    issues.append(f"WARNING: Only {metrics['num_trades']} trades - sample size too small to trust")

if abs(metrics['total_return']) > 100:
    issues.append(f"WARNING: Return {metrics['total_return']:.2f}% seems extreme - possible calculation error")

if metrics['total_profit'] + metrics['total_loss'] == 0:
    issues.append("WARNING: No profit or loss calculated - possible bug")

if issues:
    print("\nISSUES FOUND:")
    for issue in issues:
        print(f"  {issue}")
    print("\nBACKTEST RESULTS ARE NOT RELIABLE")
    print("   The strategy is fundamentally broken or there's a bug.")
else:
    print("\nNo obvious calculation errors detected")
    print("   However, results may still not translate to live trading due to:")
    print("   - Slippage not modeled")
    print("   - Commission costs not included")
    print("   - Market impact not considered")
    print("   - Look-ahead bias possible")

print("\n" + "=" * 60)
print("VERDICT:")
print("=" * 60)
if metrics['total_return'] < 0 and metrics['win_rate'] < 20:
    print("DO NOT USE FOR LIVE TRADING")
    print("   Strategy is losing money with terrible win rate.")
    print("   Backtest is likely accurate - strategy is just bad.")
elif metrics['total_return'] > 0 and metrics['win_rate'] > 30:
    print("Results look reasonable")
    print("   But still test in paper trading first!")
else:
    print("Results are questionable")
    print("   Need more investigation before live trading.")
