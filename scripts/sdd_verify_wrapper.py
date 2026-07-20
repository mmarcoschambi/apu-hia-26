#!/usr/bin/env python3
import sys
import subprocess
import hashlib

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/sdd_verify_wrapper.py <command...>", file=sys.stderr)
        sys.exit(1)
        
    cmd = sys.argv[1:]
    
    # Usar Popen para streaming en tiempo real sin bloquear el buffer del SO
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    hasher = hashlib.sha256()
    
    # Lectura por chunks en tiempo real: muestra logs inmediatamente y acumula el hash
    while True:
        chunk = proc.stdout.read(1024)
        if not chunk and proc.poll() is not None:
            break
        if chunk:
            sys.stderr.buffer.write(chunk)
            sys.stderr.buffer.flush()
            hasher.update(chunk)
            
    proc.wait()
    output_hash = hasher.hexdigest()
    
    print(f"\nCOMMAND: {' '.join(cmd)}")
    print(f"EXIT_CODE: {proc.returncode}")
    print(f"OUTPUT_HASH: sha256:{output_hash}")
    
    sys.exit(proc.returncode)

if __name__ == "__main__":
    main()
