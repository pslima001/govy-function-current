# Manifest — govy/doctrine/

> Golden Path: atualizar este arquivo a cada PR que altere govy/doctrine/.

| Path | Lines | SHA256 (prefix) | Last Commit |
|------|------:|-----------------|-------------|
| `govy/doctrine/__init__.py` | 0 | `e3b0c44298fc1c14...` | f91060a 2026-02-02 |
| `govy/doctrine/chunker.py` | 77 | `a6da7165b55ecc08...` | f91060a 2026-02-02 |
| `govy/doctrine/citation_extractor.py` | 63 | `93af23f46d3f775d...` | 832c563 2026-02-02 |
| `govy/doctrine/pipeline.py` | 191 | `672629e970ef607b...` | 272da5f 2026-02-03 |
| `govy/doctrine/reader_docx.py` | 38 | `9aa319eeec7f236c...` | f91060a 2026-02-02 |
| `govy/doctrine/run_batch.py` | 73 | `fc2b26ca9f6bf547...` | 832c563 2026-02-02 |
| `govy/doctrine/run_microbatch_report.py` | 94 | `68b9205c27daeaaa...` | a30d402 2026-02-03 |
| `govy/doctrine/semantic.py` | 250 | `01836ac43a0c833c...` | 832c563 2026-02-02 |
| `govy/doctrine/verbatim_classifier.py` | 22 | `106fe9227992bb4c...` | 832c563 2026-02-02 |

## Como regenerar

```powershell
python -c "
import hashlib, subprocess
files = [
    'govy/doctrine/__init__.py','govy/doctrine/chunker.py',
    'govy/doctrine/citation_extractor.py','govy/doctrine/pipeline.py',
    'govy/doctrine/reader_docx.py','govy/doctrine/run_batch.py',
    'govy/doctrine/run_microbatch_report.py','govy/doctrine/semantic.py',
    'govy/doctrine/verbatim_classifier.py',
]
for f in files:
    data = open(f,'rb').read()
    sha = hashlib.sha256(data).hexdigest()
    lines = data.count(b'\n')
    commit = subprocess.check_output(['git','log','-1','--format=%h %ai','--',f],text=True).strip()
    print(f'| \x60{f}\x60 | {lines} | \x60{sha[:16]}...\x60 | {commit} |')
"
```
