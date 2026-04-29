#!/usr/bin/env python3
"""
Analiza duplicación y divergencias entre motores THOR y Advanced
"""
import ast
import re
from pathlib import Path
from collections import defaultdict

def extract_functions(filepath):
    """Extrae funciones de un archivo Python"""
    with open(filepath) as f:
        try:
            tree = ast.parse(f.read())
            functions = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions[node.name] = {
                        'lineno': node.lineno,
                        'args': [arg.arg for arg in node.args.args],
                        'body_lines': node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 0
                    }
            return functions
        except:
            return {}

def find_calculation_patterns(filepath, pattern_name):
    """Busca patrones de cálculo específicos"""
    with open(filepath) as f:
        content = f.read()
        
    patterns = {
        'rvol': r'(rvol|relative_volume|vol.*?/.*?avg.*?vol)',
        'adr': r'(adr|average.*?daily.*?range)',
        'trades_count': r'(len\(trades\)|\.shape\[0\]|n_trades|num_trades)',
        'win_rate': r'(win_rate|wins.*?/.*?total|pct_win)',
        'partial_exits': r'(tp1|tp2|runner|partial.*?exit)',
    }
    
    if pattern_name in patterns:
        matches = re.finditer(patterns[pattern_name], content, re.IGNORECASE)
        return [(m.group(), m.start()) for m in matches]
    return []

def analyze_files():
    """Analiza archivos principales"""
    files = {
        'thor': 'src/backtest/optimization_engine_thor.py',
        'advanced': 'src/backtest/vectorbt_engine_advanced.py',
        'daily': 'src/backtest/daily_engine.py'
    }
    
    results = {}
    
    print("=" * 80)
    print("🔍 ANÁLISIS DE DUPLICACIÓN Y DIVERGENCIAS")
    print("=" * 80)
    
    for name, filepath in files.items():
        if Path(filepath).exists():
            print(f"\n📁 {name.upper()}: {filepath}")
            funcs = extract_functions(filepath)
            results[name] = {
                'functions': funcs,
                'total_functions': len(funcs)
            }
            
            # Buscar cálculos clave
            for calc in ['rvol', 'adr', 'trades_count', 'win_rate', 'partial_exits']:
                matches = find_calculation_patterns(filepath, calc)
                if matches:
                    print(f"   🔹 {calc}: {len(matches)} referencias")
                    for match, _ in matches[:3]:  # Mostrar primeras 3
                        print(f"      → {match[:50]}")
    
    # Comparar funciones comunes
    print("\n" + "=" * 80)
    print("🔄 FUNCIONES COMUNES ENTRE MOTORES")
    print("=" * 80)
    
    if 'thor' in results and 'advanced' in results:
        thor_funcs = set(results['thor']['functions'].keys())
        adv_funcs = set(results['advanced']['functions'].keys())
        
        common = thor_funcs & adv_funcs
        thor_only = thor_funcs - adv_funcs
        adv_only = adv_funcs - thor_funcs
        
        print(f"\n✅ Comunes ({len(common)}): {', '.join(sorted(common)[:10])}")
        print(f"🔵 Solo THOR ({len(thor_only)}): {', '.join(sorted(thor_only)[:10])}")
        print(f"🟢 Solo Advanced ({len(adv_only)}): {', '.join(sorted(adv_only)[:10])}")
    
    return results

def find_metric_calculations():
    """Encuentra cómo cada motor calcula métricas clave"""
    print("\n" + "=" * 80)
    print("📊 CÁLCULO DE MÉTRICAS CLAVE")
    print("=" * 80)
    
    files = [
        'src/backtest/optimization_engine_thor.py',
        'src/backtest/vectorbt_engine_advanced.py'
    ]
    
    metrics = {
        'win_rate': [r'win.*?rate', r'wins.*?/.*?total', r'pct.*?win'],
        'trade_count': [r'len\(.*?trades', r'n_trades', r'num.*?trades', r'\.shape\[0\]'],
        'sharpe': [r'sharpe.*?ratio', r'returns.*?/.*?std'],
    }
    
    for filepath in files:
        if Path(filepath).exists():
            print(f"\n📄 {Path(filepath).name}")
            with open(filepath) as f:
                lines = f.readlines()
                
            for metric_name, patterns in metrics.items():
                print(f"   🎯 {metric_name}:")
                found = False
                for i, line in enumerate(lines, 1):
                    for pattern in patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            print(f"      L{i}: {line.strip()[:70]}")
                            found = True
                            break
                    if found and i > len(lines) - 100:  # Solo las últimas apariciones
                        break

if __name__ == "__main__":
    analyze_files()
    find_metric_calculations()
    
    print("\n" + "=" * 80)
    print("💡 RECOMENDACIONES")
    print("=" * 80)
    print("""
1. CREAR MÓDULO COMPARTIDO (src/utils/metrics.py):
   - calculate_rvol(volume, avg_volume)
   - calculate_adr(high, low, close)
   - calculate_win_rate(trades_df)
   - calculate_sharpe(returns)
   
2. CREAR MÓDULO DE CONTEO (src/utils/trade_counter.py):
   - count_complete_positions(entries) → cuenta 1 por entrada
   - count_partial_exits(entries) → cuenta TP1, TP2, Runner
   - normalize_metrics(trades, method='complete'|'partial')
   
3. REFACTORIZAR MOTORES:
   - THOR: usar count_complete_positions()
   - Advanced: especificar qué método usa en logs
   - Ambos: importar de módulos compartidos
   
4. TESTS DE CONVERGENCIA:
   - Validar que ambos usen mismo método de conteo
   - Comparar métricas con normalización
   
5. UI STREAMLIT:
   - Usar mismas funciones de cálculo
   - Mostrar aclaración de método de conteo
""")
