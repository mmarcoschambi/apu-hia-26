import subprocess
r = subprocess.run(['gentle-ai', 'sdd-verify-validate', '--input', r'openspec\changes\sdd-architecture-closure\verify-report-candidate.md', '--requirements', '4', '--scenarios', '4'], capture_output=True, text=True)
print("OUT:", r.stdout)
print("ERR:", r.stderr)
print("CODE:", r.returncode)
