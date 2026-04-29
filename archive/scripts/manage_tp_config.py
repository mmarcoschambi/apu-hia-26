#!/usr/bin/env python3
"""
TP Configuration Management Utility
====================================
Utility to view, save, clear, and test TP configurations.

Usage:
    python3 manage_tp_config.py [command]
    
Commands:
    status  - Show current TP configuration status (default)
    clear   - Remove saved optimal configuration
    save    - Save a new optimal configuration interactively
    test    - Test loading configuration
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.utils.tp_config_manager import TPConfigManager
from datetime import datetime


def show_status():
    """Display current TP configuration status"""
    print("="*70)
    print("📊 TP CONFIGURATION STATUS")
    print("="*70)
    
    # Check if saved config exists
    if TPConfigManager.CONFIG_PATH.exists():
        with open(TPConfigManager.CONFIG_PATH, 'r') as f:
            config = json.load(f)
        
        print("\n✅ Saved Optimal Configuration:")
        print(f"   File: {TPConfigManager.CONFIG_PATH}")
        print(f"   TP Distribution: {config['tp1_pct']*100:.0f}% / {config['tp2_pct']*100:.0f}% / {config['runner_pct']*100:.0f}%")
        print(f"   Sharpe: {config.get('sharpe', 'N/A')}")
        print(f"   Trades: {config.get('trades', 'N/A')}")
        print(f"   Source: {config.get('source', 'unknown')}")
        
        # Calculate age
        saved_date = datetime.fromisoformat(config['timestamp'])
        days_old = (datetime.now() - saved_date).days
        print(f"   Created: {saved_date.strftime('%Y-%m-%d %H:%M')}")
        print(f"   Age: {days_old} days")
        
        if days_old > 7:
            print(f"   ⚠️  Configuration is {days_old} days old, consider re-optimizing")
        elif days_old > 30:
            print(f"   ❌ Configuration is outdated (>{days_old} days)")
    else:
        print("\n❌ No Saved Optimal Configuration")
        print(f"   Expected location: {TPConfigManager.CONFIG_PATH}")
        print("\n💡 To create one:")
        print("   • python3 optimize_tp_distributions.py --mode optimize")
        print("   • python3 manage_tp_config.py save")
    
    # Show available presets
    print("\n📋 Available Presets:")
    for name, values in TPConfigManager.PRESETS.items():
        print(f"   {name:20s}: {values['tp1_pct']*100:.0f}% / {values['tp2_pct']*100:.0f}% / {values['runner_pct']*100:.0f}%")
    
    # Show usage examples
    print("\n💡 Usage:")
    print("   • Use saved optimal:  --tp-preset optimize")
    print("   • Use preset:         --tp-preset balanced")
    print("   • Re-optimize:        python3 optimize_tp_distributions.py --mode optimize")


def clear_config():
    """Clear saved optimal configuration"""
    if TPConfigManager.CONFIG_PATH.exists():
        TPConfigManager.clear_saved_optimal()
        print("✅ Saved configuration cleared")
    else:
        print("ℹ️  No saved configuration to clear")


def save_config():
    """Interactive save of TP configuration"""
    print("="*70)
    print("💾 SAVE TP CONFIGURATION")
    print("="*70)
    print("\nEnter TP distribution percentages (must sum to 100):")
    
    try:
        tp1 = float(input("  TP1% (e.g., 40): ")) / 100
        tp2 = float(input("  TP2% (e.g., 30): ")) / 100
        runner = float(input("  Runner% (e.g., 30): ")) / 100
        
        # Validate sum
        total = tp1 + tp2 + runner
        if abs(total - 1.0) > 0.01:
            print(f"❌ Error: Percentages sum to {total*100:.1f}%, must be 100%")
            return
        
        # Optional metrics
        sharpe = input("  Sharpe (optional, press Enter to skip): ")
        sharpe = float(sharpe) if sharpe else 0
        
        trades = input("  Trades (optional, press Enter to skip): ")
        trades = int(trades) if trades else 0
        
        source = input("  Source (e.g., 'manual', 'backtest'): ")
        source = source if source else "manual"
        
        # Save
        TPConfigManager.save_optimal_tp(
            tp1, tp2, runner,
            sharpe=sharpe,
            trades=trades,
            source=source
        )
        
        print("\n✅ Configuration saved successfully")
        
    except ValueError as e:
        print(f"❌ Error: Invalid input - {e}")
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled")


def test_config():
    """Test loading configuration"""
    print("="*70)
    print("🧪 TESTING TP CONFIGURATION")
    print("="*70)
    
    # Test each preset
    print("\n1️⃣ Testing presets:")
    for preset_name in ['classic', 'balanced', 'aggressive_runner']:
        config = TPConfigManager.get_optimal_tp(preset_name)
        if config:
            print(f"   ✅ {preset_name:20s}: {config['tp1_pct']*100:.0f}%/{config['tp2_pct']*100:.0f}%/{config['runner_pct']*100:.0f}%")
        else:
            print(f"   ❌ {preset_name}: Failed to load")
    
    # Test optimize (saved optimal)
    print("\n2️⃣ Testing saved optimal:")
    config = TPConfigManager.get_optimal_tp('optimize')
    if config:
        print(f"   ✅ Loaded: {config['tp1_pct']*100:.0f}%/{config['tp2_pct']*100:.0f}%/{config['runner_pct']*100:.0f}%")
        print(f"   Source: {config.get('source', 'unknown')}")
    else:
        print(f"   ❌ No saved optimal found")
    
    print("\n✅ Test complete")


def main():
    commands = {
        'status': show_status,
        'clear': clear_config,
        'save': save_config,
        'test': test_config,
    }
    
    # Default to status if no command
    command = sys.argv[1] if len(sys.argv) > 1 else 'status'
    
    if command in commands:
        commands[command]()
    else:
        print(f"❌ Unknown command: {command}")
        print(f"Available: {', '.join(commands.keys())}")
        sys.exit(1)


if __name__ == "__main__":
    main()
