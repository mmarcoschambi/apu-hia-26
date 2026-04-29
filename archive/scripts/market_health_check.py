#!/usr/bin/env python3
"""
MARKET HEALTH CHECK - Pre-Trading Verification
Verifica condiciones del mercado ANTES de buscar setups

Usage:
    python market_health_check.py              # Check completo
    python market_health_check.py --quick      # Solo verdict
    python market_health_check.py --detail     # Análisis detallado
"""
import sys
import argparse
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.data.market_data import MarketDataProvider
from src.core.market_context import MarketContext


class MarketHealthChecker:
    """Verifica salud del mercado para trading"""
    
    def __init__(self):
        self.data_provider = MarketDataProvider()
        self.context_analyzer = MarketContext(self.data_provider)
    
    def check(self, detailed=False) -> dict:
        """Ejecuta chequeo completo de salud del mercado"""
        
        print("\n" + "="*80)
        print("🛡️  MARKET HEALTH CHECK")
        print("="*80)
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Analizar índices
        context = self.context_analyzer.analyze_indices()
        
        # Extract key metrics
        spy_price = context.get('spy_price', 0)
        spy_ema20 = context.get('spy_ema20', 0)
        spy_above_ema20 = context.get('spy_above_ema20', False)
        breadth_improving = context.get('breadth_improving', False)
        positive_gex = context.get('positive_gex', False)
        vix_favorable = context.get('vix_favorable', True)
        sector_leaders = context.get('sector_leaders', {})
        market_favorable = context.get('market_favorable_for_longs', False)
        market_weak = context.get('market_weak', False)
        
        # Calcular scores (ahora sobre 7 puntos)
        health_score = 0
        max_score = 7
        
        if spy_above_ema20:
            health_score += 2
        if breadth_improving:
            health_score += 2
        if positive_gex:
            health_score += 1
        if vix_favorable:
            health_score += 1
        if sector_leaders:
            health_score += 1
        
        # Display results
        print("📊 SPY TREND")
        print("-" * 80)
        print(f"   Current Price: ${spy_price:.2f}")
        print(f"   EMA 20:        ${spy_ema20:.2f}")
        print(f"   Distance:      {((spy_price - spy_ema20) / spy_ema20 * 100):+.2f}%")
        status = "✅ ABOVE" if spy_above_ema20 else "❌ BELOW"
        print(f"   Status:        {status}")
        
        print("\n📈 MARKET BREADTH")
        print("-" * 80)
        status = "✅ IMPROVING" if breadth_improving else "❌ NOT IMPROVING"
        print(f"   Breadth:       {status}")
        
        print("\n⚡ VOLATILITY REGIME")
        print("-" * 80)
        status = "✅ FAVORABLE (<20, stable)" if vix_favorable else "⚠️ ELEVATED (>20 or rising)"
        print(f"   VIX Status:    {status}")
        
        print("\n🎯 SECTOR LEADERSHIP")
        print("-" * 80)
        if sector_leaders:
            top_3 = list(sector_leaders.items())[:3]
            print(f"   Top Sectors Today:")
            for sector, data in top_3:
                print(f"      {sector:25s} {data['change_pct']:+6.2f}%")
        else:
            print(f"   Sector data:   Not available")
        
        print("\n💎 GAMMA EXPOSURE (GEX)")
        print("-" * 80)
        status = "✅ POSITIVE (Low Vol Grind)" if positive_gex else "⚠️ NEUTRAL/NEGATIVE"
        print(f"   GEX Estimate:  {status}")
        
        if market_weak:
            print("\n⚠️  WARNING: Market weakness detected")
            print("   - Gap down or significant intraday weakness")
        
        # Detailed analysis
        if detailed:
            self._show_detailed_analysis(context)
        
        # Final verdict
        print("\n" + "="*80)
        print("🎯 TRADING VERDICT")
        print("="*80)
        print(f"\n   Health Score: {health_score}/{max_score} {'🟢' * health_score}{'⚪' * (max_score - health_score)}\n")
        
        if not market_favorable:
            print("   ❌ MARKET NOT FAVORABLE FOR LONGS")
            print("   📋 Action: GO TO CASH or PAPER TRADE ONLY")
            reasons = []
            if not spy_above_ema20:
                reasons.append("SPY below EMA20")
            if not breadth_improving:
                reasons.append("Breadth not improving")
            if not vix_favorable:
                reasons.append("VIX elevated/rising")
            print(f"   💡 Why: {', '.join(reasons) if reasons else 'Multiple factors'}")
            print("   ⏰ When: Wait for conditions to improve")
            mode = "NO_TRADE"
            
        elif health_score >= 6:
            print("   🚀 EXCELLENT CONDITIONS - AGGRESSIVE MODE")
            print("   📋 Action: Full size positions (2% risk)")
            print("   💡 Setup: All 3 Caminos active")
            print("   🎯 Max: 5 concurrent positions")
            print("   ⚡ Bonus: Focus on leading sectors for best setups")
            mode = "AGGRESSIVE"
            
        elif health_score >= 4:
            print("   💪 GOOD CONDITIONS - STANDARD MODE")
            print("   📋 Action: Standard positions (1.5-2% risk)")
            print("   💡 Setup: Prefer Camino 1 (Blue Sky) in leading sectors")
            print("   🎯 Max: 3-4 concurrent positions")
            mode = "STANDARD"
            
        else:
            print("   ⚠️  DEFENSIVE CONDITIONS - SELECTIVE MODE")
            print("   📋 Action: Half size positions (0.5-1% risk)")
            print("   💡 Setup: Only perfect Blue Sky in top sectors")
            print("   🎯 Max: 1-2 concurrent positions")
            mode = "DEFENSIVE"
        
        print("="*80 + "\n")
        
        # Return structured data
        return {
            'timestamp': datetime.now().isoformat(),
            'market_favorable': market_favorable,
            'mode': mode,
            'health_score': health_score,
            'max_score': max_score,
            'spy_price': spy_price,
            'spy_ema20': spy_ema20,
            'spy_above_ema20': spy_above_ema20,
            'breadth_improving': breadth_improving,
            'positive_gex': positive_gex,
            'vix_favorable': vix_favorable,
            'sector_leaders': sector_leaders,
            'market_weak': market_weak
        }
    
    def _show_detailed_analysis(self, context):
        """Muestra análisis detallado de condiciones"""
        print("\n" + "="*80)
        print("🔍 DETAILED ANALYSIS")
        print("="*80)
        
        # SPY details
        spy_gap = context.get('spy_gap_pct', 0)
        spy_change = context.get('spy_change_pct', 0)
        
        print(f"\n📊 SPY Details:")
        print(f"   Open Gap:       {spy_gap*100:+.2f}%")
        print(f"   Intraday Move:  {spy_change*100:+.2f}%")
        print(f"   Gap Down:       {'YES ⚠️' if context.get('spy_gap_down') else 'NO ✅'}")
        
        # QQQ details
        qqq_gap = context.get('qqq_gap_pct', 0)
        qqq_change = context.get('qqq_change_pct', 0)
        
        print(f"\n📊 QQQ Details:")
        print(f"   Open Gap:       {qqq_gap*100:+.2f}%")
        print(f"   Intraday Move:  {qqq_change*100:+.2f}%")
        print(f"   Gap Down:       {'YES ⚠️' if context.get('qqq_gap_down') else 'NO ✅'}")
        
        # Get VIX if available
        try:
            vix_data = self.data_provider.get_daily_data('VIX', period='5d')
            if not vix_data.empty:
                vix = vix_data['Close'].iloc[-1]
                print(f"\n📉 VIX (Fear Index):")
                print(f"   Current:        ${vix:.2f}")
                
                if vix < 15:
                    print(f"   Status:         ✅ LOW (Complacency)")
                elif vix < 20:
                    print(f"   Status:         ⚠️  NORMAL")
                elif vix < 30:
                    print(f"   Status:         ⚠️  ELEVATED")
                else:
                    print(f"   Status:         🚨 HIGH (Fear)")
        except:
            pass
    
    def quick_check(self) -> str:
        """Quick check que retorna solo el veredicto"""
        context = self.context_analyzer.analyze_indices()
        market_favorable = context.get('market_favorable_for_longs', False)
        
        if market_favorable:
            return "✅ GO"
        else:
            return "❌ NO-GO"


def main():
    parser = argparse.ArgumentParser(description='Market Health Check')
    parser.add_argument('--quick', action='store_true', help='Quick verdict only')
    parser.add_argument('--detail', action='store_true', help='Detailed analysis')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    args = parser.parse_args()
    
    checker = MarketHealthChecker()
    
    if args.quick:
        verdict = checker.quick_check()
        print(verdict)
    else:
        result = checker.check(detailed=args.detail)
        
        if args.json:
            import json
            print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
