import fitz  # PyMuPDF
import os

def extraer_texto_pdf(ruta_pdf):

    texto_completo = ""
    try:
        doc = fitz.open(ruta_pdf)
        for pagina in doc:

            texto_completo += pagina.get_text() + "\n"
        doc.close()
        return texto_completo
    except Exception as e:
        print(f"  ⚠️ Error al procesar {os.path.basename(ruta_pdf)}: {e}")
        return None

def main():
    # 1. Detectar carpeta de entrada
    carpeta_entrada = "bocks" if os.path.isdir("bocks") else "books"
    carpeta_salida = "extracted_texts"
    
    if not os.path.isdir(carpeta_entrada):
        print(f"❌ Error: No se encontró la carpeta '{carpeta_entrada}' ni 'books'.")
        return

    os.makedirs(carpeta_salida, exist_ok=True)

    # 2. VALIDADOR: Obtener lista de libros YA procesados (archivos .txt existentes)
    libros_ya_procesados = set()
    if os.path.isdir(carpeta_salida):
        for archivo in os.listdir(carpeta_salida):
            if archivo.lower().endswith('.txt'):
                # Guardamos solo el nombre sin la extensión para comparar fácilmente
                nombre_base = os.path.splitext(archivo)[0]
                libros_ya_procesados.add(nombre_base)

    # 3. Obtener todos los PDFs de la carpeta de entrada
    archivos_pdf = [f for f in os.listdir(carpeta_entrada) if f.lower().endswith('.pdf')]

    if not archivos_pdf:
        print(f"⚠️ No se encontraron archivos PDF en la carpeta '{carpeta_entrada}'.")
        return

    # 4. Filtrar: Separar libros nuevos de los ya procesados
    libros_nuevos = []
    libros_omitidos = []

    for pdf in archivos_pdf:
        nombre_base = os.path.splitext(pdf)[0]
        if nombre_base in libros_ya_procesados:
            libros_omitidos.append(pdf)
        else:
            libros_nuevos.append(pdf)


    # 5. Informar estado inicial
    print(f"📚 Escaneo completado:")
    print(f"   - Total PDFs encontrados: {len(archivos_pdf)}")
    print(f"   - Ya procesados (se omitirán): {len(libros_omitidos)}")
    print(f"   - Nuevos para procesar: {len(libros_nuevos)}\n")

    if not libros_nuevos:
        print("✅ ¡Todo está al día! No hay libros nuevos para extraer.")
        return

    print("🚀 Iniciando extracción de libros nuevos...\n")

    exitosos = 0
    fallidos = 0

    # 6. Procesar SOLO los libros nuevos
    for archivo in libros_nuevos:
        ruta_pdf = os.path.join(carpeta_entrada, archivo)
        nombre_sin_ext = os.path.splitext(archivo)[0]
        ruta_txt = os.path.join(carpeta_salida, f"{nombre_sin_ext}.txt")

        print(f"📖 Procesando (NUEVO): {archivo}")
        
        texto = extraer_texto_pdf(ruta_pdf)
        
        if texto:
            with open(ruta_txt, 'w', encoding='utf-8') as f:
                f.write(texto)
            print(f"  ✅ Guardado en: {ruta_txt}")
            exitosos += 1
        else:
            fallidos += 1

    # 7. Resumen final
    print("\n" + "="*60)
    print("🎉 ¡Proceso de desensamblaje finalizado!")
    print(f"📊 Resumen de esta ejecución:")
    print(f"   - Libros omitidos (ya existentes): {len(libros_omitidos)}")
    print(f"   - Libros extraídos exitosamente:   {exitosos}")
    print(f"   - Libros con errores:              {fallidos}")
    print(f"   - Carpeta de salida:               ./{carpeta_salida}/")
    print("="*60)

if __name__ == "__main__":
    main()
