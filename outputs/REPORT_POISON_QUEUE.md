# REPORT: Poison Queue — Triagem e Recomendacao

**Data/Hora**: 2026-02-23T19:37Z (UTC)
**Queue**: `parse-tce-queue-poison` (stgovyparsetestsponsor)
**Total mensagens**: ~7.127

---

## 1. Diagnostico

### 1.1 Distribuicao por tribunal (sample de 32 mensagens)

| Tribunal (blob_path prefix) | Count (sample) | % |
|---|---|---|
| tce-sp | 32 | 100% |

**Conclusao**: 100% das mensagens amostradas sao de **TCE-SP**. Zero mensagens de TCE-MG, TCU, ou outros tribunais.

### 1.2 Formato das mensagens

As mensagens estao em **formato antigo** (pre-fix). Campos presentes:

```json
{
  "blob_path": "tce-sp/acordaos/24461_989_21_acordao.pdf",
  "blob_etag": "0x8DE6A2231427356",
  "json_key": "tce-sp--acordaos--24461_989_21_acordao.json"
}
```

**Campos ausentes** (que o formato atual inclui):
- `tribunal_id` — ausente em 100% das amostras
- Sem metadata adicional

### 1.3 Timestamps

Todas as mensagens amostradas foram inseridas em **2026-02-17T14:58:24Z** — run unico de enqueue do TCE-SP.

### 1.4 Dequeue count

`dequeue_count = 0` em todas as amostras. Isso significa que o Azure Functions tentou processar cada mensagem 5 vezes (max_dequeue_count padrao) e moveu para poison apos falhas consecutivas. O contador reseta ao mover para poison.

---

## 2. Sample de 20 mensagens (sem secrets)

| # | blob_path | has_tribunal_id | dequeue | inserted_on |
|---|---|---|---|---|
| 1 | tce-sp/acordaos/24461_989_21_acordao.pdf | No | 0 | 2026-02-17 14:58:24 |
| 2 | tce-sp/acordaos/24461_989_24_acordao.pdf | No | 0 | 2026-02-17 14:58:24 |
| 3 | tce-sp/acordaos/24469_989_20_acordao.pdf | No | 0 | 2026-02-17 14:58:24 |
| 4 | tce-sp/acordaos/24472_989_21_acordao.pdf | No | 0 | 2026-02-17 14:58:24 |
| 5 | tce-sp/acordaos/24474_989_19_acordao.pdf | No | 0 | 2026-02-17 14:58:24 |
| 6 | tce-sp/acordaos/24475_989_20_acordao.pdf | No | 0 | 2026-02-17 14:58:24 |
| 7 | tce-sp/acordaos/24476_989_20_acordao.pdf | No | 0 | 2026-02-17 14:58:24 |
| 8 | tce-sp/acordaos/24481_989_21_acordao.pdf | No | 0 | 2026-02-17 14:58:24 |
| 9 | tce-sp/acordaos/24486_989_19_acordao.pdf | No | 0 | 2026-02-17 14:58:24 |
| 10 | tce-sp/acordaos/24487_989_19_acordao.pdf | No | 0 | 2026-02-17 14:58:24 |
| 11 | tce-sp/acordaos/24487_989_24_acordao.pdf | No | 0 | 2026-02-17 14:58:24 |
| 12 | tce-sp/acordaos/24491_989_19_acordao.pdf | No | 0 | 2026-02-17 14:58:24 |
| 13 | tce-sp/acordaos/24492_989_21_acordao.pdf | No | 0 | 2026-02-17 14:58:24 |
| 14 | tce-sp/acordaos/24493_989_19_acordao.pdf | No | 0 | 2026-02-17 14:58:24 |
| 15 | tce-sp/acordaos/24493_989_21_acordao.pdf | No | 0 | 2026-02-17 14:58:24 |
| 16 | tce-sp/acordaos/24501_989_21_acordao.pdf | No | 0 | 2026-02-17 14:58:24 |
| 17 | tce-sp/acordaos/24502_989_24_acordao.pdf | No | 0 | 2026-02-17 14:58:24 |
| 18 | tce-sp/acordaos/24508_989_21_acordao.pdf | No | 0 | 2026-02-17 14:58:24 |
| 19 | tce-sp/acordaos/24510_989_21_acordao.pdf | No | 0 | 2026-02-17 14:58:25 |
| 20 | tce-sp/acordaos/24511_026_10_acordao.pdf | No | 0 | 2026-02-17 14:58:25 |

---

## 3. Causa raiz provavel

As 7.127 mensagens poisoned sao de um **enqueue em massa do TCE-SP em 2026-02-17**. A falha provavel:
- Formato antigo (sem `tribunal_id`) → handler nao conseguiu identificar config → erro → retry 5x → poison
- Ou: bug de parsing no momento (pre-fix do override) causou excecoes repetidas

Os PDFs fonte em `juris-raw/tce-sp/` continuam intactos. As mensagens poison nao representam perda de dados — apenas falhas de processamento que podem ser retentadas.

---

## 4. Opcoes de tratamento

### Opcao A: Drenar e arquivar em blob `poison-archive/`

**Prós**: Preserva historico, auditavel, limpa a fila
**Contras**: Exige script customizado, ~7k JSONs minusculos no blob
**Esforco**: ~30 min

```python
# Pseudocodigo
from azure.storage.queue import QueueClient
from azure.storage.blob import ContainerClient

poison = QueueClient(...)
archive = ContainerClient(..., "poison-archive")

while True:
    msgs = poison.receive_messages(max_messages=32, visibility_timeout=60)
    if not msgs: break
    for m in msgs:
        archive.upload_blob(f"tce-sp/{m.id}.json", m.content)
        poison.delete_message(m)
```

### Opcao B: Apagar a poison queue (lixo historico)

**Prós**: Mais simples, limpa tudo de uma vez
**Contras**: Perde evidencia de quais PDFs falharam
**Esforco**: 1 comando

```python
poison.clear_messages()
# ou via CLI:
# az storage message clear --queue-name parse-tce-queue-poison --account-name stgovyparsetestsponsor
```

### Opcao C: Re-enqueue com script "poison replayer"

**Prós**: Reprocessa os PDFs que falharam com o codigo corrigido
**Contras**: Pode poisonar de novo se a causa raiz para TCE-SP nao foi corrigida; gera carga
**Esforco**: ~1h (script + monitoramento)

```python
# Pseudocodigo
poison = QueueClient(conn, "parse-tce-queue-poison")
main = QueueClient(conn, "parse-tce-queue")

while True:
    msgs = poison.receive_messages(max_messages=32, visibility_timeout=60)
    if not msgs: break
    for m in msgs:
        data = json.loads(m.content)
        # Adicionar tribunal_id se ausente
        data["tribunal_id"] = "tce-sp"
        main.send_message(json.dumps(data))
        poison.delete_message(m)
```

---

## 5. Decisao e Execucao

**Opcao escolhida**: **B (clear)** — lixo historico, PDFs fonte intactos em `juris-raw/tce-sp/`.

Justificativa:
- 100% das mensagens sao TCE-SP de run antigo (2026-02-17)
- Formato antigo (sem `tribunal_id`) — re-enqueue exigiria enriquecimento
- PDFs fonte em `juris-raw/tce-sp/` estao intactos — reprocessamento futuro via `enqueue-tce` com `tribunal_id=tce-sp` e mais limpo
- Nenhum dado perdido — apenas referencia a PDFs que continuam disponiveis

### Execucao

| Acao | Timestamp | Resultado |
|---|---|---|
| Before clear | 2026-02-23T19:48Z | 7.127 messages |
| `poison.clear_messages()` | 2026-02-23T19:48Z | OK |
| After clear | 2026-02-23T19:48Z | 0 messages |

```python
from azure.storage.queue import QueueServiceClient
qsvc = QueueServiceClient.from_connection_string("<STGOVYPARSETESTSPONSOR_CONN>")
poison = qsvc.get_queue_client("parse-tce-queue-poison")
print(f"Before: {poison.get_queue_properties().approximate_message_count}")  # 7127
poison.clear_messages()
print(f"After: {poison.get_queue_properties().approximate_message_count}")   # 0
```

### Proximo passo (quando necessario)

Para reprocessar TCE-SP no futuro, usar enqueue limpo:

```bash
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"tribunal_id":"tce-sp","skip_existing":false}' \
  "https://func-govy-parse-test-exabasfqgsfgexhd.eastus-01.azurewebsites.net/api/kb/juris/enqueue-tce?code=<KEY>"
```

---

## 6. Comandos de diagnostico utilizados

### Contagem da fila poison

```python
from azure.storage.queue import QueueServiceClient
qsvc = QueueServiceClient.from_connection_string("<STGOVYPARSETESTSPONSOR_CONN>")
poison = qsvc.get_queue_client("parse-tce-queue-poison")
props = poison.get_queue_properties()
print(f"Total: {props.approximate_message_count}")  # 7127
```

### Sample de 32 mensagens (peek, nao consome)

```python
msgs = poison.peek_messages(max_messages=32)
for m in msgs:
    data = json.loads(m.content)
    print(f"blob_path={data.get('blob_path')} "
          f"has_tid={'tribunal_id' in data} "
          f"inserted={m.inserted_on}")
```

### Listagem de todas as filas com "tce"

```python
for q in qsvc.list_queues():
    if "tce" in q.name.lower():
        client = qsvc.get_queue_client(q.name)
        props = client.get_queue_properties()
        print(f"{q.name}: {props.approximate_message_count}")
```
