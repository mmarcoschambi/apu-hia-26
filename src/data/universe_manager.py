"""
UNIVERSE MANAGER - Sistema de gestión de universo dinámico con cache
=====================================================================
Descarga y mantiene actualizado el universo de acciones
"""

import pandas as pd
import yfinance as yf
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

class UniverseManager:
    """Gestiona el universo de acciones con cache persistente"""
    
    def __init__(self, cache_dir="data/universe"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.universe_file = self.cache_dir / "universe.json"
        self.custom_file = self.cache_dir / "custom_tickers.json"
        self.metadata_file = self.cache_dir / "metadata.json"
    
    def get_sp500(self):
        """Descarga S&P 500 desde Wikipedia"""
        try:
            url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
            tables = pd.read_html(url)
            df = tables[0]
            tickers = df['Symbol'].tolist()
            tickers = [t.replace('.', '-') for t in tickers]
            return tickers
        except Exception as e:
            print(f"[WARN]  Error descargando S&P 500: {e}")
            return []
    
    def get_nasdaq100(self):
        """Descarga NASDAQ 100 desde Wikipedia"""
        try:
            url = 'https://en.wikipedia.org/wiki/Nasdaq-100'
            tables = pd.read_html(url)
            df = tables[4]
            tickers = df['Ticker'].tolist()
            return tickers
        except Exception as e:
            print(f"[WARN]  Error descargando NASDAQ 100: {e}")
            return []
    
    def add_custom_tickers(self, tickers):
        """
        Agrega tickers personalizados al universo
        
        Args:
            tickers: Lista de tickers o string separado por comas
        """
        if isinstance(tickers, str):
            tickers = [t.strip().upper() for t in tickers.split(',')]
        else:
            tickers = [t.upper() for t in tickers]
        
        # Cargar existentes
        custom = self.load_custom_tickers()
        
        # Agregar nuevos
        custom.extend(tickers)
        custom = list(set(custom))  # Eliminar duplicados
        
        # Guardar
        with open(self.custom_file, 'w') as f:
            json.dump({
                'tickers': sorted(custom),
                'updated': datetime.now().isoformat()
            }, f, indent=2)
        
        print(f"[OK] Agregados {len(tickers)} tickers. Total custom: {len(custom)}")
        
        return custom
    
    def load_custom_tickers(self):
        """Carga tickers personalizados"""
        if self.custom_file.exists():
            with open(self.custom_file, 'r') as f:
                data = json.load(f)
                return data.get('tickers', [])
        return []
    
    def build_universe(self, force_refresh=False):
        """
        Construye el universo completo
        
        Args:
            force_refresh: Forzar descarga aunque exista cache
        
        Returns:
            Lista de tickers únicos
        """
        # Verificar cache
        if not force_refresh and self.universe_file.exists():
            metadata = self.load_metadata()
            cache_date = datetime.fromisoformat(metadata.get('updated', '2000-01-01'))
            
            # Cache válido por 7 días
            if datetime.now() - cache_date < timedelta(days=7):
                print(f"[OK] Usando cache del {cache_date.strftime('%Y-%m-%d')}")
                return self.load_universe()
        
        print("[U+1F4E5] Descargando universo completo...")
        
        # Descargar índices
        sp500 = self.get_sp500()
        nasdaq = self.get_nasdaq100()
        custom = self.load_custom_tickers()
        
        # Combinar y eliminar duplicados
        universe = list(set(sp500 + nasdaq + custom))
        universe = sorted(universe)
        
        # Guardar
        data = {
            'tickers': universe,
            'sources': {
                'sp500': len(sp500),
                'nasdaq100': len(nasdaq),
                'custom': len(custom)
            },
            'total': len(universe),
            'updated': datetime.now().isoformat()
        }
        
        with open(self.universe_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Actualizar metadata
        self.save_metadata({
            'updated': datetime.now().isoformat(),
            'total_tickers': len(universe)
        })
        
        print(f"[OK] Universo construido: {len(universe)} tickers")
        print(f"   S&P 500: {len(sp500)}")
        print(f"   NASDAQ 100: {len(nasdaq)}")
        print(f"   Custom: {len(custom)}")
        
        return universe
    
    def load_universe(self):
        """Carga el universo desde cache"""
        if self.universe_file.exists():
            with open(self.universe_file, 'r') as f:
                data = json.load(f)
                return data['tickers']
        return []
    
    def load_metadata(self):
        """Carga metadata del universo"""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_metadata(self, metadata):
        """Guarda metadata"""
        with open(self.metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def get_info(self):
        """Retorna información del universo actual"""
        metadata = self.load_metadata()
        universe = self.load_universe()
        custom = self.load_custom_tickers()
        
        return {
            'total_tickers': len(universe),
            'custom_tickers': len(custom),
            'last_updated': metadata.get('updated', 'Never'),
            'cache_exists': self.universe_file.exists()
        }
    
    def filter_by_liquidity(self, universe, min_price=10, max_price=500, 
                           min_volume=500000, progress_callback=None):
        """
        Filtra universo por liquidez
        
        Args:
            universe: Lista de tickers
            min_price: Precio mínimo
            max_price: Precio máximo
            min_volume: Volumen promedio mínimo
            progress_callback: Función para reportar progreso (opcional)
        
        Returns:
            Lista filtrada
        """
        filtered = []
        total = len(universe)
        
        for i, ticker in enumerate(universe):
            if progress_callback:
                progress_callback(i + 1, total, ticker)
            
            try:
                data = yf.download(ticker, period='5d', progress=False, show_errors=False)
                
                if len(data) < 3:
                    continue
                
                precio = data['Close'].iloc[-1]
                volumen = data['Volume'].tail(3).mean()
                
                if min_price <= precio <= max_price and volumen >= min_volume:
                    filtered.append(ticker)
            
            except:
                continue
        
        return filtered


if __name__ == "__main__":
    # Test
    manager = UniverseManager()
    
    print("\n" + "="*80)
    print("UNIVERSE MANAGER - TEST")
    print("="*80)
    
    # Construir universo
    universe = manager.build_universe()
    
    # Info
    info = manager.get_info()
    print(f"\nTotal tickers: {info['total_tickers']}")
    print(f"Custom tickers: {info['custom_tickers']}")
    print(f"Última actualización: {info['last_updated']}")
