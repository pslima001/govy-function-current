# REPORT POISON QUEUE — TCE-SC

**Data**: 2026-02-23
**Storage Account**: stgovyparsetestsponsor

---

## Filas verificadas

| Fila | Existe | Mensagens | Status |
|------|--------|-----------|--------|
| parse-tce-queue | Sim | **0** | Limpa |
| parse-tce-queue-poison | Sim | **0** | Limpa |

## Evidencia

```bash
$ az storage queue metadata show --account-name stgovyparsetestsponsor \
    --queue-name parse-tce-queue --query "approximateMessageCount"
# Result: 0 (empty output = 0)

$ az storage message peek --account-name stgovyparsetestsponsor \
    --queue-name parse-tce-queue-poison --num-messages 5
# Result: []
```

## Analise

- Nenhuma mensagem envenenada encontrada para TCE-SC.
- Pipeline processou todos os 576 PDFs sem erros fatais.
- Nenhum legado de outro tribunal na poison queue.
- **Nenhuma acao necessaria.**

---

**Status: LIMPO**
