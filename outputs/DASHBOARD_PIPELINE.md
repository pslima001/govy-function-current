# Dashboard Pipeline — Jurisprudencia GOVY

> Atualizado: 2026-02-24 | 15 tribunais | ~150K PDFs em `juris-raw`

| Tribunal | Scraper (juris-raw) | Parser (kb-raw) | Operacional | Proximo passo | Pendencia |
|----------|:---:|:---:|:---:|---|---|
| TCE-SP | 🟢 44.741 | 🟢 44.464 | 🔴 | Agente Diario | 274 image-only skips (terminal) |
| TCU | 🟢 32.921 | 🟢 32.405 | 🔴 | Agente Diario | 14 no_pdf, 1 failed (terminal) |
| TCE-ES | 🟢 6.206 | 🟢 7.861 | 🔴 | Agente Diario | 1 terminal_skip; 3 no_pdf (terminal) |
| TCE-MG | 🟢 5.668 | 🟢 5.668 | 🔴 | Agente Diario | Poison limpa |
| TCM-SP | 🟢 2.343 | 🟢 2.296 | 🔴 | Agente Diario | 47 terminal_skip (non_decision_attachment) |
| TCE-SC | 🟢 574 | 🟢 576 | 🔴 | Agente Diario | — |
| TCE-PR | 🟢 20.176 | 🟡 | 🔴 | Fechar parsing + auditoria + REPORT_FINAL | Parsing iniciado, nao fechado; 27 no_pdf |
| TCE-PE | 🟡 13.091 | 🔴 | 🔴 | Subsegmentar 6 combos truncados + re-scrape | **6 combos truncados (~1.946 itens) — precisa subsegmentacao**; 392 upstream_missing_pdf (terminal) |
| TCE-BA | 🟢 11.341 | 🔴 | 🔴 | Estrategia propria + parse full | 5.278 no_pdf (docs internos) — risco cobertura |
| TCE-PA | 🟢 9.144 | 🔴 | 🔴 | Validar qualidade PDFs + parse full | HTML scraping — risco qualidade variavel; 2 failed, 2 no_url |
| TCE-RS | 🟢 5.471 | 🔴 | 🔴 | Parse full + auditoria 30 | API REST, clean |
| TCE-CE | 🟢 3.136 | 🔴 | 🔴 | Parse full + auditoria 30 | 1 failed (HTTP 500); API REST |
| TCE-AM | 🟢 33.941 | 🟢 33.900 | 🔴 | Agente Diario | 41 terminal_skip (non_decision_attachment); 99.88% coverage |
| TCE-PB | 🟢 1.760 | 🔴 | 🔴 | Parse full + auditoria 30 | API REST, 0 failed |
| TCE-RJ | 🟢 406 | 🔴 | 🔴 | Parse full + auditoria 30 | Menor volume; API REST |

---

### Legenda

| Icone | Significado |
|:---:|---|
| 🟢 | Completo — inventario validado, sem gaps estruturais |
| 🟡 | Parcial — iniciado mas com gaps (combos truncados, auditoria pendente, report nao gerado) |
| 🔴 | Nao iniciado / pendente |

### Prioridade parser pendente

**Ordem aprovada**: RJ → PB → AM → CE → PE* → RS → PR → PA → BA

| Fase | Tribunal | Vol. | Justificativa |
|------|----------|-----:|---|
| 🟢 Fase 1 — Rapido | TCE-RJ | 406 | Menor volume, fecha em <1h |
| | TCE-PB | 1.760 | API REST, PDFs estruturados |
| | TCE-AM | 2.087 | API REST, parsing direto |
| 🟡 Fase 2 — Medio | TCE-CE | 3.136 | Diario com estrutura regular |
| | TCE-PE* | 13.091 | REST API — *so apos resolver 6 combos truncados do scraper* |
| | TCE-RS | 5.471 | API REST, volume medio-alto |
| 🟠 Fase 3 — Aberto | TCE-PR | 20.176 | Parsing iniciado — fechar antes que vire divida |
| 🔴 Fase 4 — Risco | TCE-PA | 9.144 | HTML scraping — validar qualidade antes |
| | TCE-BA | 11.341 | 5.278 no_pdf — precisa estrategia propria |

*TCE-PE: parser so deve iniciar apos scraper subir de 🟡 para 🟢 (subsegmentacao dos 6 combos).*
