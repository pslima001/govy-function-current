"""
LOTE 3 - Batch processor para OBRA_001 (arts 40-58, 20 capitulos Lei 14.133/2021).
MANIFEST granular por artigo.

Uso:
  python scripts\doctrine_batch_obra_001_lote3.py --step validate   # 2 primeiros
  python scripts\doctrine_batch_obra_001_lote3.py --step batch      # todos 20
  python scripts\doctrine_batch_obra_001_lote3.py --step status     # listar processed
  python scripts\doctrine_batch_obra_001_lote3.py --step batch --force  # reprocessar
"""
import os, sys, json, argparse, time

# ============================================================
# MANIFEST GRANULAR - CADA ARTIGO COM TEMA PROPRIO
# ============================================================
MANIFEST = [
    {
        "blob_name": "raw/art_40_e_41_compras_e_marcas.docx",
        "etapa_processo": "edital",
        "tema_principal": "COMPRAS_E_INDICACAO_DE_MARCAS",
    },
    {
        "blob_name": "raw/art_40_marcas_amostras_e_carta_de_solidariedade.docx",
        "etapa_processo": "edital",
        "tema_principal": "MARCAS_AMOSTRAS_E_CARTA_DE_SOLIDARIEDADE",
    },
    {
        "blob_name": "raw/art_40_planejamento_compras.docx",
        "etapa_processo": "edital",
        "tema_principal": "PLANEJAMENTO_DE_COMPRAS",
    },
    {
        "blob_name": "raw/art_42_comprovacao_qualidade_produto.docx",
        "etapa_processo": "edital",
        "tema_principal": "COMPROVACAO_QUALIDADE_PRODUTO",
    },
    {
        "blob_name": "raw/art_43_processo_de_padronizacao.docx",
        "etapa_processo": "edital",
        "tema_principal": "PROCESSO_DE_PADRONIZACAO",
    },
    {
        "blob_name": "raw/art_44_compra_ou_locacao_estudo_da_maior_vantagem.docx",
        "etapa_processo": "edital",
        "tema_principal": "COMPRA_OU_LOCACAO_ESTUDO_VANTAGEM",
    },
    {
        "blob_name": "raw/art_45_licitacoes_de_obras_e_servicos_de_engenharia.docx",
        "etapa_processo": "edital",
        "tema_principal": "LICITACOES_OBRAS_SERVICOS_ENGENHARIA",
    },
    {
        "blob_name": "raw/art_46_regimes_de_obras_e_servicos_de_engenharia.docx",
        "etapa_processo": "contratacao",
        "tema_principal": "REGIMES_OBRAS_SERVICOS_ENGENHARIA",
    },
    {
        "blob_name": "raw/art_47_licitacoes_de_servicos.docx",
        "etapa_processo": "contratacao",
        "tema_principal": "LICITACOES_DE_SERVICOS",
    },
    {
        "blob_name": "raw/art_48_regras_de_terceirizacao.docx",
        "etapa_processo": "contratacao",
        "tema_principal": "REGRAS_DE_TERCEIRIZACAO",
    },
    {
        "blob_name": "raw/art_49_contratacao_concomitante_de_empresas.docx",
        "etapa_processo": "contratacao",
        "tema_principal": "CONTRATACAO_CONCOMITANTE_EMPRESAS",
    },
    {
        "blob_name": "raw/art_50_dedicacao_exclusiva_de_mao_de_obra.docx",
        "etapa_processo": "contratacao",
        "tema_principal": "DEDICACAO_EXCLUSIVA_MAO_DE_OBRA",
    },
    {
        "blob_name": "raw/art_51_locacao_de_imoveis.docx",
        "etapa_processo": "contratacao",
        "tema_principal": "LOCACAO_DE_IMOVEIS",
    },
    {
        "blob_name": "raw/art_52_licitacoes_internacionais.docx",
        "etapa_processo": "edital",
        "tema_principal": "LICITACOES_INTERNACIONAIS",
    },
    {
        "blob_name": "raw/art_53_analise_juridica_da_contratacao.docx",
        "etapa_processo": "edital",
        "tema_principal": "ANALISE_JURIDICA_DA_CONTRATACAO",
    },
    {
        "blob_name": "raw/art_54_publicidade_do_edital.docx",
        "etapa_processo": "edital",
        "tema_principal": "PUBLICIDADE_DO_EDITAL",
    },
    {
        "blob_name": "raw/art_55_prazos_para_realizacao_do_certame.docx",
        "etapa_processo": "edital",
        "tema_principal": "PRAZOS_REALIZACAO_CERTAME",
    },
    {
        "blob_name": "raw/art_56_modo_de_disputa_aberto_ou_fechado.docx",
        "etapa_processo": "julgamento",
        "tema_principal": "MODO_DISPUTA_ABERTO_FECHADO",
    },
    {
        "blob_name": "raw/art_57_intervalo_minio_de_valores_de_lances.docx",
        "etapa_processo": "julgamento",
        "tema_principal": "INTERVALO_MINIMO_LANCES",
    },
    {
        "blob_name": "raw/art_58_garantia_de_proposta.docx",
        "etapa_processo": "edital",
        "tema_principal": "GARANTIA_DE_PROPOSTA",
    },
]

# Defaults internos (sigilo doutrinario)
ANO_DEFAULT = 2021
AUTOR_DEFAULT = ""
OBRA_DEFAULT = ""

# ============================================================
# FUNCOES
# ============================================================

def get_blob_service():
    from azure.storage.blob import BlobServiceClient
    conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING") or os.getenv("AzureWebJobsStorage")
    if not conn:
        print("ERRO: AZURE_STORAGE_CONNECTION_STRING nao configurada")
        sys.exit(1)
    return BlobServiceClient.from_connection_string(conn)


def process_items(items, force=False):
    from govy.doctrine.pipeline import ingest_doctrine_process_once, DoctrineIngestRequest

    bs = get_blob_service()
    container_source = os.getenv("DOCTRINE_CONTAINER_SOURCE", "doutrina")
    container_processed = os.getenv("DOCTRINE_CONTAINER_PROCESSED", "doutrina-processed")

    results = {"processed": 0, "already_processed": 0, "failed": 0, "errors": []}

    for i, item in enumerate(items, 1):
        blob = item["blob_name"]
        print(f"\n[{i}/{len(items)}] {blob}")

        req = DoctrineIngestRequest(
            blob_name=blob,
            etapa_processo=item["etapa_processo"],
            tema_principal=item["tema_principal"],
            autor=AUTOR_DEFAULT,
            obra=OBRA_DEFAULT,
            edicao="",
            ano=ANO_DEFAULT,
            capitulo="",
            secao="",
            force_reprocess=force,
        )

        try:
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
                print(f"  OK ({dt:.0f}s): semantic={stats.get('semantic_chunks', '?')}, "
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
    container = os.getenv("DOCTRINE_PROCESSED_CONTAINER_NAME", "doutrina-processed")
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
    parser = argparse.ArgumentParser(description="Batch OBRA_001 Lote 3 (arts 40-58)")
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
