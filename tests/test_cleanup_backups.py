import os
from pathlib import Path
import tempfile
import pytest
from scripts.cleanup_backups import run_cleanup

def test_cleanup_backups(monkeypatch):
    """
    Verifica que run_cleanup encuentre y elimine archivos de backup en el directorio objetivo.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        src_mock = tmp_path / "src"
        src_mock.mkdir()
        
        # Crear archivos de prueba
        good_file = src_mock / "daily_engine.py"
        good_file.write_text("print('hello')")
        
        backup_file1 = src_mock / "daily_engine.py.backup"
        backup_file1.write_text("print('backup')")
        
        backup_file2 = src_mock / "market_regime.py.bak"
        backup_file2.write_text("print('bak')")
        
        # Mockear la constante SRC_DIR para que apunte a nuestro directorio temporal
        monkeypatch.setattr("scripts.cleanup_backups.SRC_DIR", src_mock)
        
        # Ejecutar la limpieza
        run_cleanup()
        
        # Verificar resultados
        assert good_file.exists(), "El archivo valido no deberia ser eliminado"
        assert not backup_file1.exists(), "El archivo .backup deberia ser eliminado"
        assert not backup_file2.exists(), "El archivo .bak deberia ser eliminado"
