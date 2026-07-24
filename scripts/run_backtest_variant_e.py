
import sys
import subprocess
import json
import os
from pathlib import Path

def run_variant_e_experiment():
    config_path = Path("config/production_config.json")
    
    # 1. Leer config original
    with open(config_path, "r") as f:
        original_config = json.load(f)
    
    # 2. Crear config temporal para Variante E (Divergencia)
    # IMPORTANTE: Desactivamos sector_etf_filter para permitir la divergencia
    test_config = original_config.copy()
    test_config["tier2_filters"]["use_sector_etf_filter"] = False
    test_config["tier2_filters"]["use_theme_group_filter"] = True
    test_config["tier2_filters"]["theme_filter_mode"] = "divergence"
    
    temp_config_path = Path("config/temp_variant_e_config.json")
    with open(temp_config_path, "w") as f:
        json.dump(test_config, f, indent=2)
    
    print("🚀 Iniciando Backtest Pesado: Variante E (Divergencia Temática)")
    print("Config: Sector ETF OFF | Theme Divergence ON")
    
    try:
        # 3. Ejecutar Backtest
        # Nota: He modificado el comando para usar el config temporal si fuera necesario, 
        # pero como el script lee de production_config, vamos a hacer el swap rápido.
        os.rename(config_path, "config/production_config.json.bak")
        os.rename(temp_config_path, config_path)
        
        cmd = [
            sys.executable, "scripts/backtest_via_signal_engine.py",
            "--start", "2023-01-01",
            "--end", "2024-12-31",
            "--capital", "100000",
            "--universe-size", "200",
            "--tag", "variant_e_full"
        ]
        subprocess.run(cmd, check=True)
        
        # 4. Ejecutar Análisis
        print("\n📊 Generando atribución de sectores y meses...")
        subprocess.run([sys.executable, "scripts/analyze_backtest_output.py"], check=True)
        
    finally:
        # 5. Restaurar config original
        if os.path.exists("config/production_config.json.bak"):
            if os.path.exists(config_path): os.remove(config_path)
            os.rename("config/production_config.json.bak", config_path)
        if os.path.exists(temp_config_path): os.remove(temp_config_path)

if __name__ == "__main__":
    run_variant_e_experiment()
