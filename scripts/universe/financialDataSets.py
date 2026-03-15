import requests
import json  # Importamos la librería para manejar JSON

headers = {"X-API-KEY": "8d4fb7e5-2316-4840-bdc4-82d2b6924dc9"} # Recuerda dejar tus comillas aquí
url_tickers = 'https://api.financialdatasets.ai/company/facts/tickers/'


response = requests.get(url_tickers, headers=headers)

if response.status_code == 200:
    universo_tickers = response.json().get('tickers', [])
    print(f"¡Éxito! Obtuviste un universo de {len(universo_tickers)} tickers.")
    
    # --- LA PARTE NUEVA: GUARDAR EN EL DISCO ---
    # Abrimos (o creamos) un archivo en modo escritura ('w')
    with open('tickers_universo.json', 'w') as archivo:
        # Volcamos la lista de Python al archivo físico
        json.dump(universo_tickers, archivo)
        
    print("La lista se ha guardado correctamente en 'tickers_universo.json'")
else:
    print("Error al obtener los tickers:", response.status_code)
