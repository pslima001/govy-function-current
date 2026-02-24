# REPORT: Poison Queue Audit — TCE-SP

**Data**: 2026-02-23
**Queue**: `parse-tce-queue-poison` (stgovyparsetestsponsor)

## Sumario

| Metrica                              | Valor |
|--------------------------------------|-------|
| Total mensagens na poison queue      | 32    |
| Formato legado (sem `tribunal_id`)   | 32    |
| Formato atual (com `tribunal_id`)    | 0     |
| Oriundas da run TCE-SP 2026-02-23   | **0** |

## Analise

Todas as 32 mensagens poison sao do formato antigo do pipeline, contendo apenas o campo `blob_path` sem o campo `tribunal_id` que o pipeline v2 injeta. Isso confirma que todas sao de runs anteriores a implementacao do campo `tribunal_id`.

- **Range de IDs**: processo 24461 a 24522
- **Prefixo**: 100% `tce-sp/acordaos/`
- **dequeue_count**: 0 em todas (nunca reprocessadas)

## Lista Completa (32 mensagens)

| # | blob_path | has_tribunal_id | dequeue_count |
|---|-----------|-----------------|---------------|
| 1 | `tce-sp/acordaos/24461_989_21_acordao.pdf` | N | 0 |
| 2 | `tce-sp/acordaos/24461_989_24_acordao.pdf` | N | 0 |
| 3 | `tce-sp/acordaos/24469_989_20_acordao.pdf` | N | 0 |
| 4 | `tce-sp/acordaos/24472_989_21_acordao.pdf` | N | 0 |
| 5 | `tce-sp/acordaos/24474_989_19_acordao.pdf` | N | 0 |
| 6 | `tce-sp/acordaos/24475_989_20_acordao.pdf` | N | 0 |
| 7 | `tce-sp/acordaos/24476_989_20_acordao.pdf` | N | 0 |
| 8 | `tce-sp/acordaos/24481_989_21_acordao.pdf` | N | 0 |
| 9 | `tce-sp/acordaos/24486_989_19_acordao.pdf` | N | 0 |
|10 | `tce-sp/acordaos/24487_989_19_acordao.pdf` | N | 0 |
|11 | `tce-sp/acordaos/24487_989_24_acordao.pdf` | N | 0 |
|12 | `tce-sp/acordaos/24491_989_19_acordao.pdf` | N | 0 |
|13 | `tce-sp/acordaos/24492_989_21_acordao.pdf` | N | 0 |
|14 | `tce-sp/acordaos/24493_989_19_acordao.pdf` | N | 0 |
|15 | `tce-sp/acordaos/24493_989_21_acordao.pdf` | N | 0 |
|16 | `tce-sp/acordaos/24501_989_21_acordao.pdf` | N | 0 |
|17 | `tce-sp/acordaos/24502_989_24_acordao.pdf` | N | 0 |
|18 | `tce-sp/acordaos/24508_989_21_acordao.pdf` | N | 0 |
|19 | `tce-sp/acordaos/24510_989_21_acordao.pdf` | N | 0 |
|20 | `tce-sp/acordaos/24511_026_10_acordao.pdf` | N | 0 |
|21 | `tce-sp/acordaos/24511_989_19_acordao.pdf` | N | 0 |
|22 | `tce-sp/acordaos/24511_989_24_acordao.pdf` | N | 0 |
|23 | `tce-sp/acordaos/24512_989_21_acordao.pdf` | N | 0 |
|24 | `tce-sp/acordaos/24513_989_24_acordao.pdf` | N | 0 |
|25 | `tce-sp/acordaos/24514_989_19_acordao.pdf` | N | 0 |
|26 | `tce-sp/acordaos/24514_989_21_acordao.pdf` | N | 0 |
|27 | `tce-sp/acordaos/24515_989_19_acordao.pdf` | N | 0 |
|28 | `tce-sp/acordaos/24516_989_24_acordao.pdf` | N | 0 |
|29 | `tce-sp/acordaos/24518_989_24_acordao.pdf` | N | 0 |
|30 | `tce-sp/acordaos/24520_989_24_acordao.pdf` | N | 0 |
|31 | `tce-sp/acordaos/24521_989_24_acordao.pdf` | N | 0 |
|32 | `tce-sp/acordaos/24522_989_20_acordao.pdf` | N | 0 |

## Recomendacao

Estas 32 mensagens podem ser **purgadas com seguranca**. Sao do formato antigo (pre-pipeline v2), nunca foram reprocessadas (dequeue=0), e nao correspondem a nenhum item da run atual.

Para purgar: `az storage message clear --queue-name parse-tce-queue-poison --account-name stgovyparsetestsponsor`

---

*Relatório gerado automaticamente por Claude Code em 2026-02-23*
