#!/usr/bin/env python3
"""
Backtest Sector & Market Health Analytics
==========================================
Analiza correlación entre performance de trades y:
1. Sector del ticker
2. Market health en el momento de entrada
3. Momentum del sector durante el trade

Previene overfitting mostrando si tus ganancias vienen de:
- Skill (tu sistema) vs Luck (mercado alcista brutal)
- Sectores específicos vs diversificación real

USO:
    # Analizar backtest existente
    python3 analyze_backtest_sectors.py --results outputs/backtests/backtest_results.csv
    
    # Con periodo específico
    python3 analyze_backtest_sectors.py --results outputs/backtests/backtest_results.csv --year 2024
    
    # Generar report completo
    python3 analyze_backtest_sectors.py --results outputs/backtests/backtest_results.csv --full-report
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import argparse
import json
from collections import defaultdict
import matplotlib.pyplot as plt
import seaborn as sns

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))


# Sector Classification (expandible)
SECTOR_MAP = {
    # Technology
    'AAPL': 'Technology', 'NVDA': 'Technology', 'MSFT': 'Technology',
    'GOOGL': 'Technology', 'GOOG': 'Technology', 'META': 'Technology',
    'AMZN': 'Technology', 'TSLA': 'Technology', 'AMD': 'Technology',
    'AVGO': 'Technology', 'ORCL': 'Technology', 'CRM': 'Technology',
    'ADBE': 'Technology', 'NFLX': 'Technology', 'INTC': 'Technology',
    'QCOM': 'Technology', 'CSCO': 'Technology', 'SMCI': 'Technology',
    'PLTR': 'Technology', 'NOW': 'Technology', 'SNOW': 'Technology',
    'CRWD': 'Technology', 'PANW': 'Technology', 'FTNT': 'Technology',
    
    # Consumer Cyclical / Discretionary
    'TSLA': 'Consumer Cyclical', 'AMZN': 'Consumer Cyclical',
    'HD': 'Consumer Cyclical', 'NKE': 'Consumer Cyclical',
    'MCD': 'Consumer Cyclical', 'SBUX': 'Consumer Cyclical',
    'TGT': 'Consumer Cyclical', 'LOW': 'Consumer Cyclical',
    'BKNG': 'Consumer Cyclical', 'ABNB': 'Consumer Cyclical',
    
    # Energy
    'XOM': 'Energy', 'CVX': 'Energy', 'SLB': 'Energy',
    'COP': 'Energy', 'EOG': 'Energy', 'MPC': 'Energy',
    'PSX': 'Energy', 'VLO': 'Energy', 'DVN': 'Energy',
    'FANG': 'Energy', 'MRO': 'Energy', 'OXY': 'Energy',
    
    # Financial
    'JPM': 'Financial', 'BAC': 'Financial', 'WFC': 'Financial',
    'GS': 'Financial', 'MS': 'Financial', 'C': 'Financial',
    'BLK': 'Financial', 'SCHW': 'Financial', 'AXP': 'Financial',
    'V': 'Financial', 'MA': 'Financial', 'PYPL': 'Financial',
    
    # Healthcare
    'UNH': 'Healthcare', 'JNJ': 'Healthcare', 'LLY': 'Healthcare',
    'ABBV': 'Healthcare', 'MRK': 'Healthcare', 'TMO': 'Healthcare',
    'ABT': 'Healthcare', 'PFE': 'Healthcare', 'AMGN': 'Healthcare',
    'MRNA': 'Healthcare', 'GILD': 'Healthcare',
    
    # Industrial
    'BA': 'Industrial', 'CAT': 'Industrial', 'GE': 'Industrial',
    'UPS': 'Industrial', 'RTX': 'Industrial', 'HON': 'Industrial',
    
    # Materials
    'LIN': 'Materials', 'APD': 'Materials', 'NUE': 'Materials',
    'FCX': 'Materials',
    
    # Communication Services
    'GOOGL': 'Communication Services', 'META': 'Communication Services',
    'NFLX': 'Communication Services', 'DIS': 'Communication Services',
    'CMCSA': 'Communication Services', 'T': 'Communication Services',
}

SECTOR_ETFS = {
    'Technology': 'XLK',
    'Energy': 'XLE',
    'Financial': 'XLF',
    'Healthcare': 'XLV',
    'Industrial': 'XLI',
    'Consumer Cyclical': 'XLY',
    'Consumer Staples': 'XLP',
    'Materials': 'XLB',
    'Real Estate': 'XLRE',
    'Utilities': 'XLU',
    'Communication Services': 'XLC'
}


class BacktestSectorAnalyzer:
    """
    Analiza correlación entre trades y sector/market context
    """
    
    def __init__(self, results_file):
        self.results_file = Path(results_file)
        self.df = None
        self.sector_etf_data = {}
        self.spy_data = None
        self.vix_data = None
        
    def load_results(self):
        """Carga resultados de backtest"""
        print(f"📂 Loading backtest results: {self.results_file}")
        
        self.df = pd.read_csv(self.results_file)
        
        # Convertir fechas
        self.df['entry_date'] = pd.to_datetime(self.df['entry_date'])
        self.df['exit_date'] = pd.to_datetime(self.df['exit_date'])
        
        print(f"✅ Loaded {len(self.df)} trades")
        print(f"   Date range: {self.df['entry_date'].min()} → {self.df['exit_date'].max()}")
        
        return self.df
    
    def enrich_with_sectors(self):
        """Agrega columna de sector a cada trade"""
        print("\n🏷️  Classifying trades by sector...")
        
        self.df['sector'] = self.df['symbol'].map(SECTOR_MAP)
        self.df['sector'] = self.df['sector'].fillna('Other')
        
        sector_counts = self.df['sector'].value_counts()
        print("\nTrades by Sector:")
        for sector, count in sector_counts.items():
            print(f"   {sector:<25} {count:>3} trades")
        
    def load_market_context(self):
        """Carga datos de mercado (SPY, VIX, Sector ETFs) para todo el periodo"""
        print("\n📊 Loading market context data...")
        
        start_date = self.df['entry_date'].min() - timedelta(days=30)
        end_date = self.df['exit_date'].max() + timedelta(days=5)
        
        # SPY
        print("   Loading SPY...")
        self.spy_data = yf.download('SPY', start=start_date, end=end_date, progress=False)
        if not self.spy_data.empty:
            self.spy_data['ema21'] = self.spy_data['Close'].ewm(span=21).mean()
            self.spy_data['ema50'] = self.spy_data['Close'].ewm(span=50).mean()
        
        # VIX
        print("   Loading VIX...")
        self.vix_data = yf.download('^VIX', start=start_date, end=end_date, progress=False)
        
        # Sector ETFs
        print("   Loading Sector ETFs...")
        for sector, etf in SECTOR_ETFS.items():
            try:
                data = yf.download(etf, start=start_date, end=end_date, progress=False)
                if not data.empty:
                    # Calculate daily returns
                    data['daily_return'] = data['Close'].pct_change() * 100
                    # Calculate momentum (20-day rate of change)
                    data['momentum_20d'] = ((data['Close'] / data['Close'].shift(20)) - 1) * 100
                    self.sector_etf_data[sector] = data
            except Exception as e:
                print(f"   ⚠️  Could not load {etf}: {e}")
        
        print(f"✅ Market context loaded for {len(self.sector_etf_data)} sectors")
    
    def calculate_market_health_at_entry(self):
        """
        Calcula market health score en el momento de cada entrada
        
        Score (0-7 points):
        - SPY > EMA21: +3
        - SPY > EMA50: +2
        - VIX < 20: +2
        - VIX trending down: +1
        """
        print("\n🏥 Calculating market health at entry...")
        
        health_scores = []
        
        for idx, trade in self.df.iterrows():
            entry_date = trade['entry_date']
            
            score = 0
            reasons = []
            
            # SPY trend
            if not self.spy_data.empty:
                try:
                    spy_entry = self.spy_data[self.spy_data.index <= entry_date].iloc[-1]
                    
                    if spy_entry['Close'] > spy_entry['ema21']:
                        score += 3
                        reasons.append('SPY>EMA21')
                    
                    if spy_entry['Close'] > spy_entry['ema50']:
                        score += 2
                        reasons.append('SPY>EMA50')
                        
                except:
                    pass
            
            # VIX
            if not self.vix_data.empty:
                try:
                    vix_slice = self.vix_data[self.vix_data.index <= entry_date]
                    if len(vix_slice) >= 5:
                        vix_current = vix_slice['Close'].iloc[-1]
                        vix_avg_5d = vix_slice['Close'].tail(5).mean()
                        
                        if vix_current < 20:
                            score += 2
                            reasons.append('VIX<20')
                        
                        if vix_current < vix_avg_5d:
                            score += 1
                            reasons.append('VIX↓')
                except:
                    pass
            
            # Classify
            if score >= 6:
                health_status = 'GREEN'
            elif score >= 4:
                health_status = 'YELLOW'
            else:
                health_status = 'RED'
            
            health_scores.append({
                'score': score,
                'status': health_status,
                'reasons': ', '.join(reasons)
            })
        
        # Add to dataframe
        self.df['market_health_score'] = [h['score'] for h in health_scores]
        self.df['market_health_status'] = [h['status'] for h in health_scores]
        self.df['market_health_reasons'] = [h['reasons'] for h in health_scores]
        
        print(f"✅ Market health calculated")
        print(f"   GREEN: {len(self.df[self.df['market_health_status']=='GREEN'])} trades")
        print(f"   YELLOW: {len(self.df[self.df['market_health_status']=='YELLOW'])} trades")
        print(f"   RED: {len(self.df[self.df['market_health_status']=='RED'])} trades")
    
    def calculate_sector_momentum_at_entry(self):
        """Calcula el momentum del sector en el momento de entrada"""
        print("\n🚀 Calculating sector momentum at entry...")
        
        sector_momentum = []
        sector_ranking = []
        
        for idx, trade in self.df.iterrows():
            sector = trade['sector']
            entry_date = trade['entry_date']
            
            momentum = np.nan
            ranking = None
            
            if sector in self.sector_etf_data:
                try:
                    etf_data = self.sector_etf_data[sector]
                    etf_entry = etf_data[etf_data.index <= entry_date]
                    
                    if len(etf_entry) >= 20:
                        momentum = etf_entry['momentum_20d'].iloc[-1]
                        
                        # Calculate ranking vs other sectors
                        all_momentums = {}
                        for s, data in self.sector_etf_data.items():
                            s_entry = data[data.index <= entry_date]
                            if len(s_entry) >= 20:
                                all_momentums[s] = s_entry['momentum_20d'].iloc[-1]
                        
                        if all_momentums:
                            sorted_sectors = sorted(all_momentums.items(), 
                                                  key=lambda x: x[1], 
                                                  reverse=True)
                            
                            for rank, (s, m) in enumerate(sorted_sectors, 1):
                                if s == sector:
                                    ranking = rank
                                    break
                except:
                    pass
            
            sector_momentum.append(momentum)
            sector_ranking.append(ranking)
        
        self.df['sector_momentum_20d'] = sector_momentum
        self.df['sector_ranking'] = sector_ranking
        
        print(f"✅ Sector momentum calculated")
    
    def analyze_correlations(self):
        """Analiza correlaciones entre factores y performance"""
        print("\n" + "="*80)
        print("📈 CORRELATION ANALYSIS")
        print("="*80)
        
        # 1. Performance by Sector
        print("\n1️⃣  PERFORMANCE BY SECTOR")
        print("-"*80)
        
        sector_stats = self.df.groupby('sector').agg({
            'returns_pct': ['count', 'mean', 'median', 'std'],
            'is_profitable': 'mean'
        }).round(2)
        
        sector_stats.columns = ['Trades', 'Avg_Return%', 'Median_Return%', 'Std%', 'Win_Rate']
        sector_stats = sector_stats.sort_values('Avg_Return%', ascending=False)
        
        print(sector_stats)
        
        # 2. Performance by Market Health
        print("\n2️⃣  PERFORMANCE BY MARKET HEALTH")
        print("-"*80)
        
        health_stats = self.df.groupby('market_health_status').agg({
            'returns_pct': ['count', 'mean', 'median'],
            'is_profitable': 'mean'
        }).round(2)
        
        health_stats.columns = ['Trades', 'Avg_Return%', 'Median_Return%', 'Win_Rate']
        health_stats = health_stats.reindex(['GREEN', 'YELLOW', 'RED'])
        
        print(health_stats)
        
        # 3. Performance by Sector Momentum
        print("\n3️⃣  PERFORMANCE BY SECTOR MOMENTUM")
        print("-"*80)
        
        # Classify by momentum
        self.df['sector_momentum_class'] = pd.cut(
            self.df['sector_momentum_20d'],
            bins=[-np.inf, 0, 5, 10, np.inf],
            labels=['Negative', 'Weak (0-5%)', 'Moderate (5-10%)', 'Strong (>10%)']
        )
        
        momentum_stats = self.df.groupby('sector_momentum_class', observed=True).agg({
            'returns_pct': ['count', 'mean', 'median'],
            'is_profitable': 'mean'
        }).round(2)
        
        momentum_stats.columns = ['Trades', 'Avg_Return%', 'Median_Return%', 'Win_Rate']
        
        print(momentum_stats)
        
        # 4. Best Combinations
        print("\n4️⃣  BEST COMBINATIONS (Sector + Market Health)")
        print("-"*80)
        
        combo_stats = self.df.groupby(['sector', 'market_health_status']).agg({
            'returns_pct': ['count', 'mean'],
            'is_profitable': 'mean'
        }).round(2)
        
        combo_stats.columns = ['Trades', 'Avg_Return%', 'Win_Rate']
        combo_stats = combo_stats[combo_stats['Trades'] >= 3]  # At least 3 trades
        combo_stats = combo_stats.sort_values('Avg_Return%', ascending=False).head(10)
        
        print(combo_stats)
        
        print("\n" + "="*80)
    
    def generate_insights(self):
        """Genera insights para evitar overfitting"""
        print("\n" + "="*80)
        print("💡 INSIGHTS & OVERFITTING CHECK")
        print("="*80)
        
        insights = []
        
        # 1. Sector Concentration
        sector_pnl = self.df.groupby('sector')['returns_pct'].sum()
        total_pnl = sector_pnl.sum()
        
        if total_pnl > 0:
            top_sector = sector_pnl.idxmax()
            top_sector_contribution = (sector_pnl.max() / total_pnl) * 100
            
            if top_sector_contribution > 50:
                insights.append(f"⚠️  OVERFITTING RISK: {top_sector_contribution:.1f}% of PnL from {top_sector}")
                insights.append(f"   → Your system may be overfit to {top_sector} characteristics")
            else:
                insights.append(f"✅ Good diversification: Top sector ({top_sector}) = {top_sector_contribution:.1f}% of PnL")
        
        # 2. Market Health Dependency
        green_trades = self.df[self.df['market_health_status'] == 'GREEN']
        red_trades = self.df[self.df['market_health_status'] == 'RED']
        
        if len(green_trades) > 0 and len(red_trades) > 0:
            green_wr = green_trades['is_profitable'].mean()
            red_wr = red_trades['is_profitable'].mean()
            
            if green_wr > red_wr + 0.3:  # 30% difference
                insights.append(f"⚠️  MARKET DEPENDENCY: Win rate drops {(green_wr-red_wr)*100:.0f}% in RED markets")
                insights.append(f"   → System performs best in bull markets only")
            else:
                insights.append(f"✅ Market resilience: Similar performance across market conditions")
        
        # 3. Sector Momentum Dependency
        strong_momentum = self.df[self.df['sector_ranking'] <= 3]  # Top 3 sectors
        weak_momentum = self.df[self.df['sector_ranking'] > 7]    # Bottom sectors
        
        if len(strong_momentum) > 0 and len(weak_momentum) > 0:
            strong_return = strong_momentum['returns_pct'].mean()
            weak_return = weak_momentum['returns_pct'].mean()
            
            if strong_return > weak_return + 5:  # 5% difference
                insights.append(f"⚠️  MOMENTUM DEPENDENCY: {strong_return - weak_return:.1f}% better return in leading sectors")
                insights.append(f"   → Consider adding sector strength filter")
            else:
                insights.append(f"✅ Sector agnostic: Works across sector momentum levels")
        
        # Print insights
        for insight in insights:
            print(insight)
        
        print("="*80 + "\n")
        
        return insights
    
    def save_enriched_results(self, output_file=None):
        """Guarda resultados enriquecidos con sector y market context"""
        if output_file is None:
            output_file = self.results_file.stem + '_enriched.csv'
        
        output_path = Path(output_file)
        self.df.to_csv(output_path, index=False)
        
        print(f"💾 Enriched results saved to: {output_path}")
    
    def plot_sector_performance(self, output_file='sector_performance.png'):
        """Genera gráfico de performance por sector"""
        plt.figure(figsize=(12, 6))
        
        sector_returns = self.df.groupby('sector')['returns_pct'].mean().sort_values()
        
        colors = ['red' if x < 0 else 'green' for x in sector_returns.values]
        sector_returns.plot(kind='barh', color=colors)
        
        plt.xlabel('Average Return (%)')
        plt.ylabel('Sector')
        plt.title('Average Trade Performance by Sector')
        plt.axvline(0, color='black', linestyle='--', linewidth=0.5)
        plt.grid(axis='x', alpha=0.3)
        plt.tight_layout()
        
        plt.savefig(output_file, dpi=150)
        print(f"📊 Chart saved: {output_file}")
        plt.close()


def main():
    parser = argparse.ArgumentParser(description='Analyze backtest results by sector & market health')
    parser.add_argument('--results', type=str, required=True, help='Backtest results CSV file')
    parser.add_argument('--year', type=int, help='Filter by specific year')
    parser.add_argument('--full-report', action='store_true', help='Generate full report with charts')
    parser.add_argument('--output', type=str, help='Output file for enriched results')
    
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("🔬 BACKTEST SECTOR & MARKET HEALTH ANALYZER")
    print("="*80 + "\n")
    
    analyzer = BacktestSectorAnalyzer(args.results)
    
    # Load & enrich
    analyzer.load_results()
    
    # Filter by year if specified
    if args.year:
        analyzer.df = analyzer.df[analyzer.df['entry_date'].dt.year == args.year]
        print(f"\n📅 Filtered to year {args.year}: {len(analyzer.df)} trades")
    
    analyzer.enrich_with_sectors()
    analyzer.load_market_context()
    analyzer.calculate_market_health_at_entry()
    analyzer.calculate_sector_momentum_at_entry()
    
    # Analyze
    analyzer.analyze_correlations()
    analyzer.generate_insights()
    
    # Save enriched results
    analyzer.save_enriched_results(args.output)
    
    # Generate charts if requested
    if args.full_report:
        analyzer.plot_sector_performance()
    
    print("\n✅ Analysis complete!\n")


if __name__ == "__main__":
    main()
