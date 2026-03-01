"""
Batch processor for OBRA_001 - LOTE 2 (20 capitulos Lei 14.133/2021, arts 20-39)
Mapeamento granular: cada artigo tem tema_principal e etapa_processo proprios.

Uso:
  python scripts/doctrine_batch_obra_001_lote2.py --step validate   # 2 primeiros
  python scripts/doctrine_batch_obra_001_lote2.py --step batch      # todos 20
  python scripts/doctrine_batch_obra_001_lote2.py --step status     # checar processed
"""
import os, sys, json, argparse, time

# ---------------------------------------------------------------------------
# MANIFEST LOTE 2: blob_name -> metadata
# Arts 20-32: etapa EDITAL (fase preparatoria / modalidades de licitacao)
# Arts 33-39: etapa JULGAMENTO (criterios de julgamento)
# ---------------------------------------------------------------------------
MANIFEST = [
    {
        "blob_name": "raw/OBRA_001/art_20_itens_de_consumo.docx",
        "etapa_processo": "edital",
        "tema_principal": "ITENS_DE_CONSUMO",
        "capitulo": "Art. 20 - Itens de Consumo",
    },
    {
        "blob_name": "raw/OBRA_001/art_21_audiencia_publica.docx",
        "etapa_processo": "edital",
        "tema_principal": "AUDIENCIA_PUBLICA",
        "capitulo": "Art. 21 - Audiencia Publica",
    },
    {
        "blob_name": "raw/OBRA_001/art_22_alocacao_de_riscos.docx",
        "etapa_processo": "edital",
        "tema_principal": "ALOCACAO_DE_RISCOS",
        "capitulo": "Art. 22 - Alocacao de Riscos",
    },
    {
        "blob_name": "raw/OBRA_001/art_23_levantamento_do_valor_estimado.docx",
        "etapa_processo": "edital",
        "tema_principal": "LEVANTAMENTO_DO_VALOR_ESTIMADO",
        "capitulo": "Art. 23 - Levantamento do Valor Estimado",
    },
    {
        "blob_name": "raw/OBRA_001/art_24_orcamento_sigiloso.docx",
        "etapa_processo": "edital",
        "tema_principal": "ORCAMENTO_SIGILOSO",
        "capitulo": "Art. 24 - Orcamento Sigiloso",
    },
    {
        "blob_name": "raw/OBRA_001/art_25_requisitos_do_edital.docx",
        "etapa_processo": "edital",
        "tema_principal": "REQUISITOS_DO_EDITAL",
        "capitulo": "Art. 25 - Requisitos do Edital",
    },
    {
        "blob_name": "raw/OBRA_001/art_26_margens_de_preferencia.docx",
        "etapa_processo": "edital",
        "tema_principal": "MARGENS_DE_PREFERENCIA",
        "capitulo": "Art. 26 - Margens de Preferencia",
    },
    {
        "blob_name": "raw/OBRA_001/art_27_divulgacao_empresas_beneficiadas.docx",
        "etapa_processo": "edital",
        "tema_principal": "DIVULGACAO_EMPRESAS_BENEFICIADAS",
        "capitulo": "Art. 27 - Divulgacao de Empresas Beneficiadas",
    },
    {
        "blob_name": "raw/OBRA_001/art_28_modalidades.docx",
        "etapa_processo": "edital",
        "tema_principal": "MODALIDADES",
        "capitulo": "Art. 28 - Modalidades de Licitacao",
    },
    {
        "blob_name": "raw/OBRA_001/art_29_concorrencia_e_pregao.docx",
        "etapa_processo": "edital",
        "tema_principal": "CONCORRENCIA_E_PREGAO",
        "capitulo": "Art. 29 - Concorrencia e Pregao",
    },
    {
        "blob_name": "raw/OBRA_001/art_30_concurso.docx",
        "etapa_processo": "edital",
        "tema_principal": "CONCURSO",
        "capitulo": "Art. 30 - Concurso",
    },
    {
        "blob_name": "raw/OBRA_001/art_31_leilao.docx",
        "etapa_processo": "edital",
        "tema_principal": "LEILAO",
        "capitulo": "Art. 31 - Leilao",
    },
    {
        "blob_name": "raw/OBRA_001/art_32_dialogo_competitivo.docx",
        "etapa_processo": "edital",
        "tema_principal": "DIALOGO_COMPETITIVO",
        "capitulo": "Art. 32 - Dialogo Competitivo",
    },
    {
        "blob_name": "raw/OBRA_001/art_33_criterios_de_julgamento.docx",
        "etapa_processo": "julgamento",
        "tema_principal": "CRITERIOS_DE_JULGAMENTO",
        "capitulo": "Art. 33 - Criterios de Julgamento",
    },
    {
        "blob_name": "raw/OBRA_001/art_34_julgamento_menor_preco_ou_menor_desconto.docx",
        "etapa_processo": "julgamento",
        "tema_principal": "JULGAMENTO_MENOR_PRECO_OU_MENOR_DESCONTO",
        "capitulo": "Art. 34 - Julgamento por Menor Preco ou Menor Desconto",
    },
    {
        "blob_name": "raw/OBRA_001/art_35_julgamento_por_melhor_tecnica_ou_conteudo_artistico.docx",
        "etapa_processo": "julgamento",
        "tema_principal": "JULGAMENTO_POR_MELHOR_TECNICA_OU_CONTEUDO_ARTISTICO",
        "capitulo": "Art. 35 - Julgamento por Melhor Tecnica ou Conteudo Artistico",
    },
    {
        "blob_name": "raw/OBRA_001/art_36_julgamento_por_tecnica_e_preco.docx",
        "etapa_processo": "julgamento",
        "tema_principal": "JULGAMENTO_POR_TECNICA_E_PRECO",
        "capitulo": "Art. 36 - Julgamento por Tecnica e Preco",
    },
    {
        "blob_name": "raw/OBRA_001/art_37_julgamento_por_melhor_tecnica_ou_tecnica_e_preco.docx",
        "etapa_processo": "julgamento",
        "tema_principal": "JULGAMENTO_POR_MELHOR_TECNICA_OU_TECNICA_E_PRECO",
        "capitulo": "Art. 37 - Julgamento por Melhor Tecnica ou Tecnica e Preco",
    },
    {
        "blob_name": "raw/OBRA_001/art_38_execucao_do_profissional_na_melhor_tecnica.docx",
        "etapa_processo": "julgamento",
        "tema_principal": "EXECUCAO_DO_PROFISSIONAL_NA_MELHOR_TECNICA",
        "capitulo": "Art. 38 - Execucao do Profissional na Melhor Tecnica",
    },
    {
        "blob_name": "raw/OBRA_001/art_39_maior_retorno_economico.docx",
        "etapa_processo": "julgamento",
        "tema_principal": "MAIOR_RETORNO_ECONOMICO",
        "capitulo": "Art. 39 - Maior Retorno Economico",
    },
]

ANO_DEFAULT = 2021
AUTOR_DEFAULT = "INTERNO"
OBRA_DEFAULT = "OBRA_001"


def get_blob_service():
    from azure.storage.blob import BlobServiceClient
    conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING") or os.getenv("AzureWebJobsStorage")
    if not conn:
        print("ERRO: AZURE_STORAGE_CONNECTION_STRING nao configurada")
        sys.exit(1)
    return BlobServiceClient.from_connection_string(conn)


def process_items(items, force=False):
    """Processa lista de items do MANIFEST."""
    from govy.doctrine.pipeline import DoctrineIngestRequest, ingest_doctrine_process_once

    bs = get_blob_service()
    container_source = os.getenv("DOCTRINE_CONTAINER_NAME", "kb-doutrina-raw")
    container_processed = os.getenv("DOCTRINE_PROCESSED_CONTAINER_NAME", "kb-doutrina-processed")

    results = {"processed": 0, "already_processed": 0, "failed": 0, "errors": []}

    for i, item in enumerate(items, 1):
        blob = item["blob_name"]
        print(f"\n[{i}/{len(items)}] Processando: {blob}")
        print(f"  etapa={item['etapa_processo']} tema={item['tema_principal']}")

        try:
            req = DoctrineIngestRequest(
                blob_name=blob,
                etapa_processo=item["etapa_processo"],
                tema_principal=item["tema_principal"],
                ano=ANO_DEFAULT,
                autor=AUTOR_DEFAULT,
                obra=OBRA_DEFAULT,
                capitulo=item["capitulo"],
                force_reprocess=force,
            )
            t0 = time.time()
            res = ingest_doctrine_process_once(
                blob_service=bs,
                container_source=container_source,
                container_processed=container_processed,
                req=req,
            )
            dt = time.time() - t0

            status = res.get("status", "unknown")
            if status == "processed":
                results["processed"] += 1
                stats = res.get("stats", {})
                print(f"  OK ({dt:.1f}s) - semantic={stats.get('semantic_chunks', '?')}, "
                      f"verbatim={stats.get('verbatim_legal_chunks', '?')}, "
                      f"incertos={stats.get('incertos', '?')}")
                src = res.get("source", {})
                sha = src.get("source_sha", "?")
                print(f"  SHA: {sha}")
            elif status == "already_processed":
                results["already_processed"] += 1
                print(f"  SKIP (already_processed, {dt:.1f}s)")
            else:
                results["failed"] += 1
                results["errors"].append({"blob": blob, "status": status, "detail": str(res)[:200]})
                print(f"  WARN: status={status}")

        except Exception as e:
            results["failed"] += 1
            results["errors"].append({"blob": blob, "error": str(e)[:300]})
            print(f"  ERRO: {e}")

    return results


def check_status():
    """Lista blobs processados em doutrina-processed."""
    bs = get_blob_service()
    container = os.getenv("DOCTRINE_PROCESSED_CONTAINER_NAME", "kb-doutrina-processed")
    client = bs.get_container_client(container)

    blobs = []
    for b in client.list_blobs():
        if b.name.endswith(".json"):
            blobs.append(b.name)

    print(f"\nBlobs processados em {container}: {len(blobs)}")
    for b in sorted(blobs):
        print(f"  {b}")
    return blobs


def main():
    parser = argparse.ArgumentParser(description="Batch OBRA_001 - Lote 2 (arts 20-39)")
    parser.add_argument("--step", choices=["validate", "batch", "status"], required=True)
    parser.add_argument("--force", action="store_true", help="Force reprocess")
    args = parser.parse_args()

    if args.step == "status":
        check_status()
        return

    if args.step == "validate":
        items = MANIFEST[:2]
        print(f"=== VALIDATE LOTE 2: Processando {len(items)} primeiros ===")
    else:
        items = MANIFEST
        print(f"=== BATCH LOTE 2: Processando todos {len(items)} ===")

    results = process_items(items, force=args.force)

    print("\n" + "=" * 50)
    print(f"RESULTADO FINAL LOTE 2:")
    print(f"  processed:         {results['processed']}")
    print(f"  already_processed: {results['already_processed']}")
    print(f"  failed:            {results['failed']}")
    if results["errors"]:
        print(f"\n  ERROS:")
        for e in results["errors"]:
            print(f"    {json.dumps(e, ensure_ascii=False)}")
    print("=" * 50)


if __name__ == "__main__":
    main()
