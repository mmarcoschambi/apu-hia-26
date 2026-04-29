import pandas as pd
import sys
import argparse
from pathlib import Path
import requests

def get_from_8marketcap(limit=1000, min_price=5.0):
    """Descarga top tickers de 8marketcap.com con paginación y filtro de precio"""
    print(f"   📥 Descargando Top Market Cap desde 8marketcap.com (Price > ${min_price})...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    all_tickers = []
    max_pages = 8  # Scrape up to page 8 to ensure we get enough tickers
    
    try:
        for page in range(1, max_pages + 1):
            url = f'https://8marketcap.com/companies/?page={page}'
            print(f"      📄 Scanning page {page}/{max_pages}...")
            
            try:
                response = requests.get(url, headers=headers, timeout=30)
                tables = pd.read_html(response.text)
                
                found_on_page = False
                for table in tables:
                    if 'Symbol' in table.columns and 'Price' in table.columns:
                        # Clean and convert Price column
                        # Remove '$', ',', and convert to float. Handle errors with coerce.
                        table['Price_Clean'] = table['Price'].astype(str).str.replace('$', '', regex=False).str.replace(',', '', regex=False)
                        table['Price_Clean'] = pd.to_numeric(table['Price_Clean'], errors='coerce')
                        
                        # Filter by min_price
                        filtered_table = table[table['Price_Clean'] > min_price].copy()
                        
                        tickers = filtered_table['Symbol'].tolist()
                        clean_tickers = [str(t).replace('.', '-') for t in tickers if str(t) != 'nan']
                        
                        all_tickers.extend(clean_tickers)
                        found_on_page = True
                        print(f"         ✅ Found {len(clean_tickers)} valid tickers (> ${min_price})")
                        break
                
                if not found_on_page:
                    print(f"         ⚠️ No valid table found on page {page}")
            
            except Exception as e:
                print(f"         ⚠️ Error on page {page}: {e}")
                continue

        # Remove duplicates while preserving order
        seen = set()
        unique_tickers = [x for x in all_tickers if not (x in seen or seen.add(x))]
        
        print(f"   ✅ Total found from 8marketcap: {len(unique_tickers)} tickers")
        return unique_tickers[:limit]
        
    except Exception as e:
        print(f"   ⚠️ Error 8marketcap.com: {e}")
        return []

def get_from_wikipedia(limit=1000):
    """Descarga tickers de Wikipedia (S&P 500 + Nasdaq 100)"""
    print("   📥 Descargando componentes S&P 500 + Nasdaq 100 desde Wikipedia...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    tickers = []
    
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        response = requests.get(url, headers=headers, timeout=30)
        sp500 = pd.read_html(response.text)[0]
        tickers.extend(sp500['Symbol'].tolist())
        print(f"   ✅ S&P 500: {len(sp500)} tickers")
    except Exception as e:
        print(f"   ⚠️ Error S&P 500: {e}")

    try:
        url = 'https://en.wikipedia.org/wiki/NASDAQ-100'
        response = requests.get(url, headers=headers, timeout=30)
        tables = pd.read_html(response.text)
        for t in tables:
            if 'Ticker' in t.columns:
                tickers.extend(t['Ticker'].tolist())
                break
            elif 'Symbol' in t.columns:
                tickers.extend(t['Symbol'].tolist())
                break
        print(f"   ✅ Nasdaq 100 agregado")
    except Exception as e:
        print(f"   ⚠️ Error Nasdaq 100: {e}")
    
    clean_tickers = [str(t).replace('.', '-') for t in tickers]
    
    seen = set()
    final_list = [x for x in clean_tickers if not (x in seen or seen.add(x))]
    
    print(f"   ✅ Total Wikipedia: {len(final_list)} tickers únicos")
    return final_list[:limit]

def get_top_companies(source='wikipedia', limit=1000):
    print(f"🌍 Obteniendo lista de empresas Top (fuente: {source})...")
    
    if source == '8marketcap':
        tickers = get_from_8marketcap(limit)
    elif source == 'wikipedia':
        tickers = get_from_wikipedia(limit)
    elif source == 'both':
        tickers_wiki = get_from_wikipedia(limit)
        tickers_8mc = get_from_8marketcap(limit)
        
        combined = tickers_wiki + tickers_8mc
        seen = set()
        tickers = [x for x in combined if not (x in seen or seen.add(x))]
        print(f"   ✅ Combinado: {len(tickers)} tickers únicos")
    else:
        print(f"❌ Fuente no válida: {source}")
        return []
    
    return tickers

def save_and_prompt(tickers):
    filename = "top_global_tickers.txt"
    with open(filename, 'w') as f:
        for t in tickers:
            f.write(f"{t}\n")
            
    print(f"\n💾 Lista guardada en: {filename}")
    
    print(f"\n📊 Resumen: {len(tickers)} tickers")

def main():
    parser = argparse.ArgumentParser(description='Obtener lista de tickers de alta calidad')
    parser.add_argument('--source', choices=['wikipedia', '8marketcap', 'both'], 
                       default='wikipedia', help='Fuente de datos (default: wikipedia)')
    parser.add_argument('--limit', type=int, default=1000, help='Límite de tickers')
    
    args = parser.parse_args()
    
    top_tickers = get_top_companies(source=args.source, limit=args.limit)
    if top_tickers:
        save_and_prompt(top_tickers)

if __name__ == "__main__":
    main()
