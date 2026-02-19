## Summary
<!-- Descreva o que mudou e por quê -->

## Checklist (obrigatório)
- [ ] Rodei `scripts/verify_repo_integrity.ps1` sem falhas
- [ ] CI verde (`lint-and-test` pass)
- [ ] Atualizei `docs/MANIFEST_DOCTRINE.md` (linhas + sha256)
- [ ] Atualizei `docs/DOCTRINE_CONTRACTS.md` (contratos)
- [ ] Nenhum arquivo fora dos paths permitidos (`govy/`, `tests/`, `docs/`, `scripts/`, `.github/`)
- [ ] Commits pequenos e focados com mensagem clara

## Test plan
- [ ] `pytest tests/test_juris_*.py -q` pass
- [ ] `pytest tests/test_doctrine_*.py -q` pass
- [ ] `ruff check` + `ruff format --check` pass
