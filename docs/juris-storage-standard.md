# Juris Storage Standard

Padrão de armazenamento para jurisprudência multi-tribunal na plataforma GOVY.

## Storage Accounts

| Account | Finalidade |
|---------|------------|
| `sttcejurisprudencia` | RAW: PDFs originais, votos, metadata |
| `stgovyparsetestsponsor` | PARSED: JSONs processados pelo pipeline |

## Containers

| Container | Account | Descrição |
|-----------|---------|-----------|
| `juris-raw` | sttcejurisprudencia | Documentos brutos (PDFs, votos) |
| `juris-parsed` | stgovyparsetestsponsor | Outputs processados (JSONs) |
| `tce-jurisprudencia` | sttcejurisprudencia | **Legado** - manter read-only |
| `kb-raw` | stgovyparsetestsponsor | **Legado** - paste/imports antigos |
| `kb-processed` | stgovyparsetestsponsor | **Legado** - parsed antigos |

## Path Patterns

### juris-raw (fonte da verdade)

```
juris-raw/
  {tribunal}/
    acordaos/{doc_id}_acordao.pdf
    relatorios_voto/{doc_id}_voto.pdf
    metadata/{doc_id}.json
```

Exemplos:
```
juris-raw/tce-sp/acordaos/10000_989_17_acordao.pdf
juris-raw/tcu/acordaos/2666_2025_acordao.pdf
juris-raw/tcu/metadata/2666_2025.json
juris-raw/tce-mg/acordaos/12345_acordao.pdf
```

### juris-parsed (outputs processados)

```
juris-parsed/
  {tribunal}/
    {ano}/
      {doc_id}.json
```

Exemplos:
```
juris-parsed/tce-sp/2023/10000_989.json
juris-parsed/tcu/2025/2666_2025.json
```

## Metadata JSON (por documento)

Cada doc em `juris-raw/{tribunal}/metadata/{doc_id}.json`:

```json
{
  "tribunal_id": "tce-sp",
  "doc_type": "acordao",
  "doc_id": "10000_989_17",
  "source": "batch_from_raw_pdfs",
  "ingested_at": "2026-02-18T17:00:00Z",
  "sha256": "abc123...",
  "original_blob_path": "tce-sp/acordaos/10000_989_17_acordao.pdf",
  "detail_link": null,
  "ano": 2017
}
```

## Tribunais Suportados

| tribunal_id | source_mode | Status |
|-------------|-------------|--------|
| `tce-sp` | `batch_from_raw_pdfs` | ~44.741 PDFs migrados |
| `tcu` | `scrape_pdf` (futuro) | Inventario em andamento |
| `tce-mg` | `import_json` | 1 doc importado |

## Regras

1. **Um container por camada** (raw, parsed), prefixos por tribunal
2. **Nunca apagar legado** sem validação completa
3. **Dedup** por `doc_id` + `sha256` antes de ingest
4. **Idempotência**: scripts devem poder rodar N vezes sem efeito colateral
5. **Audit trail**: todo ingest gera metadata JSON com timestamp e hash
