# scripts/precheck_doctrine_v2.ps1
# Precheck obrigatorio Doctrine V2.1:
# 1) py_compile em govy/api e govy/doctrine
# 2) smoke import test (inclui run_microbatch_report)
# Falha imediatamente se houver erro.

$ErrorActionPreference = "Stop"

Write-Host "=== GOVY PRECHECK | Doctrine V2.1 ===" -ForegroundColor Cyan

# 1) py_compile
Write-Host "`n[1/2] py_compile em govy/api/*.py e govy/doctrine/*.py" -ForegroundColor Yellow

python -c "
import glob, py_compile, sys
files = glob.glob('govy/api/*.py') + glob.glob('govy/doctrine/*.py')
print(f'Arquivos encontrados: {len(files)}')
errs = 0
for f in files:
    try:
        py_compile.compile(f, doraise=True)
    except Exception as e:
        errs += 1
        print(f'[ERRO] {f}: {e}')
if errs:
    raise SystemExit(f'py_compile falhou em {errs} arquivo(s).')
print('py_compile OK')
"

# 2) smoke import test
Write-Host "`n[2/2] Smoke import test (pipeline/semantic/run_batch/run_microbatch_report)" -ForegroundColor Yellow
python -c "
import govy.doctrine.pipeline
import govy.doctrine.semantic
import govy.doctrine.run_batch
import govy.doctrine.run_microbatch_report
print('imports OK')
"

Write-Host "`nPRECHECK OK. Pode abrir PR / seguir para deploy." -ForegroundColor Green
