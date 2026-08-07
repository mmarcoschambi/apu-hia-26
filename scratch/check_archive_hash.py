#!/usr/bin/env python3
"""check_archive_hash.py — Hash SHA-256 recursivo y determinístico de una carpeta de archive.

Uso: python scratch/check_archive_hash.py [ruta_carpeta]
Por defecto hashea openspec/changes/archive/2026-07-20-refactor-ticker-cache/.

El hash es estable entre ejecuciones: los archivos se procesan en orden
lexicográfico de ruta relativa y se combina ruta + contenido en un único digest.
Si la carpeta no existe, el script falla con exit code != 0.
"""
import hashlib
import sys
from pathlib import Path

# Salvaguarda para prevenir UnicodeEncodeError en terminales de Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, IOError):
        pass

DEFAULT_ARCHIVE = "openspec/changes/archive/2026-07-20-refactor-ticker-cache"


def hash_file(path: Path) -> bytes:
    """SHA-256 del contenido binario de un archivo."""
    sha = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            sha.update(chunk)
    return sha.digest()


def recursive_hash(root: Path) -> str:
    """SHA-256 recursivo determinístico de la carpeta `root`.

    Ordena los archivos por ruta relativa (posix) y encadena
    ruta + contenido en un único digest raíz.
    """
    if not root.is_dir():
        raise FileNotFoundError(f"Carpeta inexistente: {root}")

    files = sorted(
        (p for p in root.rglob("*") if p.is_file()),
        key=lambda p: p.relative_to(root).as_posix(),
    )
    digest = hashlib.sha256()
    for path in files:
        rel = path.relative_to(root).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(hash_file(path))
        digest.update(b"\x00")
    return digest.hexdigest()


def main() -> int:
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
    else:
        target = Path(__file__).resolve().parent.parent / DEFAULT_ARCHIVE
    try:
        result = recursive_hash(target)
    except FileNotFoundError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    print(f"SHA-256 ({target}) = {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
