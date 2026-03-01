"""
Batch processor for OBRA_001 (20 capitulos Lei 14.133/2021)
Mapeamento granular: cada artigo tem tema_principal e etapa_processo proprios.

Uso:
  python scripts/doctrine_batch_obra_001.py --step validate   # 2 primeiros
  python scripts/doctrine_batch_obra_001.py --step batch      # todos 20
  python scripts/doctrine_batch_obra_001.py --step status     # checar processed
"""
import os, sys, json, argparse, time

# ---------------------------------------------------------------------------
# MANIFEST: blob_name -> metadata
# Arts 1-13, 17-19: etapa EDITAL (disposicoes gerais / fase preparatoria)
# Arts 14-16: etapa HABILITACAO (quem pode participar)
# ---------------------------------------------------------------------------
MANIFEST = [
    {
        "blob_name": "raw/OBRA_001/art_01_ambito_de_aplicacao_da_lei.docx",
        "etapa_processo": "edital",
        "tema_principal": "AMBITO_DE_APLICACAO",
        "capitulo": "Art. 1 - Ambito de Aplicacao",
    },
    {
        "blob_name": "raw/OBRA_001/art_02_aplicacao_da_lei.docx",
        "etapa_processo": "edital",
        "tema_principal": "APLICACAO_DA_LEI",
        "capitulo": "Art. 2 - Aplicacao da Lei",
    },
    {
        "blob_name": "raw/OBRA_001/art_03_contratacoes_que_nao_se_aplicam.docx",
        "etapa_processo": "edital",
        "tema_principal": "CONTRATACOES_EXCLUIDAS",
        "capitulo": "Art. 3 - Contratacoes Excluidas",
    },
    {
        "blob_name": "raw/OBRA_001/art_04_aplicacao_da_lei_123_2006.docx",
        "etapa_processo": "edital",
        "tema_principal": "LEI_COMPLEMENTAR_123",
        "capitulo": "Art. 4 - LC 123/2006",
    },
    {
        "blob_name": "raw/OBRA_001/art_05_principios.docx",
        "etapa_processo": "edital",
        "tema_principal": "PRINCIPIOS",
        "capitulo": "Art. 5 - Principios",
    },
    {
        "blob_name": "raw/OBRA_001/art_05_1_vinculacao_ao_edital.docx",
        "etapa_processo": "edital",
        "tema_principal": "VINCULACAO_AO_EDITAL",
        "capitulo": "Art. 5.1 - Vinculacao ao Edital",
    },
    {
        "blob_name": "raw/OBRA_001/art_06_definicoes.docx",
        "etapa_processo": "edital",
        "tema_principal": "DEFINICOES",
        "capitulo": "Art. 6 - Definicoes",
    },
    {
        "blob_name": "raw/OBRA_001/art_07_designacao_agentes_publicos.docx",
        "etapa_processo": "edital",
        "tema_principal": "AGENTES_PUBLICOS",
        "capitulo": "Art. 7 - Designacao de Agentes Publicos",
    },
    {
        "blob_name": "raw/OBRA_001/art_08_conducao_do_certame.docx",
        "etapa_processo": "edital",
        "tema_principal": "CONDUCAO_CERTAME",
        "capitulo": "Art. 8 - Conducao do Certame",
    },
    {
        "blob_name": "raw/OBRA_001/art_09_situacoes_vedadas.docx",
        "etapa_processo": "edital",
        "tema_principal": "SITUACOES_VEDADAS",
        "capitulo": "Art. 9 - Situacoes Vedadas",
    },
    {
        "blob_name": "raw/OBRA_001/art_10_defesa_juridica_agentes.docx",
        "etapa_processo": "edital",
        "tema_principal": "DEFESA_JURIDICA",
        "capitulo": "Art. 10 - Defesa Juridica dos Agentes",
    },
    {
        "blob_name": "raw/OBRA_001/art_11_objetivos_da_licitacao.docx",
        "etapa_processo": "edital",
        "tema_principal": "OBJETIVOS_LICITACAO",
        "capitulo": "Art. 11 - Objetivos da Licitacao",
    },
    {
        "blob_name": "raw/OBRA_001/art_12_regras_de_procedimento.docx",
        "etapa_processo": "edital",
        "tema_principal": "REGRAS_PROCEDIMENTO",
        "capitulo": "Art. 12 - Regras de Procedimento",
    },
    {
        "blob_name": "raw/OBRA_001/art_13_publicidade.docx",
        "etapa_processo": "edital",
        "tema_principal": "PUBLICIDADE",
        "capitulo": "Art. 13 - Publicidade",
    },
    {
        "blob_name": "raw/OBRA_001/art_14_impedimentos.docx",
        "etapa_processo": "habilitacao",
        "tema_principal": "IMPEDIMENTOS",
        "capitulo": "Art. 14 - Impedimentos",
    },
    {
        "blob_name": "raw/OBRA_001/art_15_consorcios.docx",
        "etapa_processo": "habilitacao",
        "tema_principal": "CONSORCIOS",
        "capitulo": "Art. 15 - Consorcios",
    },
    {
        "blob_name": "raw/OBRA_001/art_16_cooperativas.docx",
        "etapa_processo": "habilitacao",
        "tema_principal": "COOPERATIVAS",
        "capitulo": "Art. 16 - Cooperativas",
    },
    {
        "blob_name": "raw/OBRA_001/art_17_fases.docx",
        "etapa_processo": "edital",
        "tema_principal": "FASES_LICITACAO",
        "capitulo": "Art. 17 - Fases da Licitacao",
    },
    {
        "blob_name": "raw/OBRA_001/art_18_fase_preparatoria.docx",
        "etapa_processo": "edital",
        "tema_principal": "FASE_PREPARATORIA",
        "capitulo": "Art. 18 - Fase Preparatoria",
    },
    {
        "blob_name": "raw/OBRA_001/art_19_regulamentacao_interna.docx",
        "etapa_processo": "edital",
        "tema_principal": "REGULAMENTACAO_INTERNA",
        "capitulo": "Art. 19 - Regulamentacao Interna",
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
                # Show processed blob name for reference
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
    parser = argparse.ArgumentParser(description="Batch OBRA_001")
    parser.add_argument("--step", choices=["validate", "batch", "status"], required=True)
    parser.add_argument("--force", action="store_true", help="Force reprocess")
    args = parser.parse_args()

    if args.step == "status":
        check_status()
        return

    if args.step == "validate":
        items = MANIFEST[:2]
        print(f"=== VALIDATE: Processando {len(items)} primeiros ===")
    else:
        items = MANIFEST
        print(f"=== BATCH: Processando todos {len(items)} ===")

    results = process_items(items, force=args.force)

    print("\n" + "=" * 50)
    print(f"RESULTADO FINAL:")
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
