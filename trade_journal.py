#!/usr/bin/env python3
"""
TRADE JOURNAL - Logging and Performance Analytics
Sistema de journaling automático integrado con tu trading

Usage:
    python trade_journal.py add "Setup AAPL Blue Sky, waited for confirmation"
    python trade_journal.py stats                    # Ver estadísticas
    python trade_journal.py report --days 7          # Reporte semanal
    python trade_journal.py export                   # Exportar a CSV
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
from typing import List, Dict

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))


class TradeJournal:
    """Journal para documentar proceso de trading y mejorar con el tiempo"""
    
    def __init__(self):
        self.journal_file = project_root / "trade_journal.json"
        self.entries = []
        self._load_journal()
        
    def _load_journal(self):
        """Cargar journal del archivo"""
        if self.journal_file.exists():
            with open(self.journal_file, 'r') as f:
                self.entries = json.load(f)
    
    def _save_journal(self):
        """Guardar journal al archivo"""
        with open(self.journal_file, 'w') as f:
            json.dump(self.entries, f, indent=2)
    
    def add_entry(self, note: str, tags: List[str] = None, 
                  symbols: List[str] = None, trade_outcome: str = None):
        """Añadir entrada al journal"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'note': note,
            'tags': tags or [],
            'symbols': [s.upper() for s in symbols] if symbols else [],
            'trade_outcome': trade_outcome  # 'win', 'loss', 'scratch', None
        }
        
        self.entries.append(entry)
        self._save_journal()
        
        print(f"✅ Journal entry added")
        print(f"   {note[:60]}...")
        
    def show_recent(self, days: int = 7):
        """Mostrar entradas recientes"""
        cutoff = datetime.now() - timedelta(days=days)
        
        recent = [
            e for e in self.entries
            if datetime.fromisoformat(e['timestamp']) >= cutoff
        ]
        
        if not recent:
            print(f"\n📭 No journal entries in the last {days} days\n")
            return
        
        print(f"\n{'='*80}")
        print(f"📖 JOURNAL ENTRIES (Last {days} days)")
        print(f"{'='*80}\n")
        
        for entry in reversed(recent):  # Most recent first
            dt = datetime.fromisoformat(entry['timestamp'])
            print(f"📅 {dt.strftime('%Y-%m-%d %H:%M')}")
            
            if entry.get('symbols'):
                print(f"   Symbols: {', '.join(entry['symbols'])}")
            
            if entry.get('tags'):
                print(f"   Tags: {', '.join(entry['tags'])}")
            
            if entry.get('trade_outcome'):
                outcome_emoji = {'win': '🟢', 'loss': '🔴', 'scratch': '⚪'}.get(entry['trade_outcome'], '⚫')
                print(f"   Outcome: {outcome_emoji} {entry['trade_outcome'].upper()}")
            
            print(f"   {entry['note']}")
            print()
    
    def show_stats(self):
        """Mostrar estadísticas del journal"""
        if not self.entries:
            print("\n📭 No journal entries yet\n")
            return
        
        print(f"\n{'='*80}")
        print("📊 JOURNAL STATISTICS")
        print(f"{'='*80}\n")
        
        # Basic stats
        total_entries = len(self.entries)
        days_active = (datetime.now() - datetime.fromisoformat(self.entries[0]['timestamp'])).days
        
        print(f"Total Entries: {total_entries}")
        print(f"Days Active: {days_active}")
        print(f"Avg Entries/Day: {total_entries/max(days_active, 1):.1f}")
        
        # Tag frequency
        all_tags = []
        for e in self.entries:
            all_tags.extend(e.get('tags', []))
        
        if all_tags:
            tag_counts = pd.Series(all_tags).value_counts()
            print(f"\n📌 Most Common Tags:")
            for tag, count in tag_counts.head(5).items():
                print(f"   {tag}: {count}")
        
        # Symbol frequency
        all_symbols = []
        for e in self.entries:
            all_symbols.extend(e.get('symbols', []))
        
        if all_symbols:
            symbol_counts = pd.Series(all_symbols).value_counts()
            print(f"\n📈 Most Traded Symbols:")
            for symbol, count in symbol_counts.head(5).items():
                print(f"   {symbol}: {count}")
        
        # Trade outcomes
        outcomes = [e.get('trade_outcome') for e in self.entries if e.get('trade_outcome')]
        if outcomes:
            outcome_counts = pd.Series(outcomes).value_counts()
            print(f"\n🎯 Trade Outcomes:")
            for outcome, count in outcome_counts.items():
                emoji = {'win': '🟢', 'loss': '🔴', 'scratch': '⚪'}.get(outcome, '⚫')
                print(f"   {emoji} {outcome.upper()}: {count}")
        
        print(f"\n{'='*80}\n")
    
    def generate_weekly_report(self):
        """Generar reporte semanal de reflexión"""
        week_ago = datetime.now() - timedelta(days=7)
        
        week_entries = [
            e for e in self.entries
            if datetime.fromisoformat(e['timestamp']) >= week_ago
        ]
        
        if not week_entries:
            print("\n📭 No entries this week\n")
            return
        
        print(f"\n{'='*80}")
        print(f"📊 WEEKLY TRADING REPORT")
        print(f"Week of {week_ago.strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')}")
        print(f"{'='*80}\n")
        
        # Activity
        print(f"📝 Journal Activity: {len(week_entries)} entries")
        
        # Symbols traded
        symbols = []
        for e in week_entries:
            symbols.extend(e.get('symbols', []))
        
        if symbols:
            unique_symbols = set(symbols)
            print(f"📈 Symbols Traded: {len(unique_symbols)} ({', '.join(sorted(unique_symbols))})")
        
        # Outcomes
        outcomes = [e.get('trade_outcome') for e in week_entries if e.get('trade_outcome')]
        if outcomes:
            wins = outcomes.count('win')
            losses = outcomes.count('loss')
            scratches = outcomes.count('scratch')
            win_rate = (wins / len(outcomes) * 100) if outcomes else 0
            
            print(f"\n🎯 Trade Performance:")
            print(f"   🟢 Wins: {wins}")
            print(f"   🔴 Losses: {losses}")
            print(f"   ⚪ Scratches: {scratches}")
            print(f"   Win Rate: {win_rate:.1f}%")
        
        # Key learnings
        print(f"\n💡 Key Themes This Week:")
        tags = []
        for e in week_entries:
            tags.extend(e.get('tags', []))
        
        if tags:
            tag_counts = pd.Series(tags).value_counts()
            for tag, count in tag_counts.head(3).items():
                print(f"   • {tag} ({count} mentions)")
        
        # Recent notes
        print(f"\n📖 Recent Reflections:")
        for entry in reversed(week_entries[-3:]):  # Last 3
            dt = datetime.fromisoformat(entry['timestamp'])
            print(f"   • [{dt.strftime('%m/%d')}] {entry['note'][:60]}...")
        
        print(f"\n{'='*80}\n")
    
    def export_to_csv(self):
        """Exportar journal a CSV para análisis externo"""
        if not self.entries:
            print("📭 No entries to export")
            return
        
        df = pd.DataFrame(self.entries)
        output_file = project_root / "trade_journal_export.csv"
        df.to_csv(output_file, index=False)
        
        print(f"✅ Journal exported to: {output_file}")
        print(f"   {len(df)} entries exported")


def main():
    parser = argparse.ArgumentParser(description='Trade Journal')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Add entry
    add_parser = subparsers.add_parser('add', help='Add journal entry')
    add_parser.add_argument('note', help='Journal note')
    add_parser.add_argument('--tags', nargs='+', help='Tags')
    add_parser.add_argument('--symbols', nargs='+', help='Symbols')
    add_parser.add_argument('--outcome', choices=['win', 'loss', 'scratch'], help='Trade outcome')
    
    # Show entries
    show_parser = subparsers.add_parser('show', help='Show recent entries')
    show_parser.add_argument('--days', type=int, default=7, help='Days to show')
    
    # Stats
    subparsers.add_parser('stats', help='Show statistics')
    
    # Weekly report
    subparsers.add_parser('report', help='Generate weekly report')
    
    # Export
    subparsers.add_parser('export', help='Export to CSV')
    
    args = parser.parse_args()
    
    journal = TradeJournal()
    
    if args.command == 'add':
        journal.add_entry(
            note=args.note,
            tags=args.tags,
            symbols=args.symbols,
            trade_outcome=args.outcome
        )
    elif args.command == 'show':
        journal.show_recent(days=args.days)
    elif args.command == 'stats':
        journal.show_stats()
    elif args.command == 'report':
        journal.generate_weekly_report()
    elif args.command == 'export':
        journal.export_to_csv()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
