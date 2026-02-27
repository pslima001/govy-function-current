"""
LOTE 6 (FINAL) - Batch processor OBRA_001 (arts 140-171, 32 capitulos Lei 14.133/2021).
Uso:
  python scripts\doctrine_batch_obra_001_lote6.py --step validate
  python scripts\doctrine_batch_obra_001_lote6.py --step batch
  python scripts\doctrine_batch_obra_001_lote6.py --step status
"""
import os, sys, json, argparse, time

MANIFEST = [
    {"blob_name": "raw/art_140_termo_de_recebimento.docx", "etapa_processo": "contratacao", "tema_principal": "TERMO_DE_RECEBIMENTO"},
    {"blob_name": "raw/art_141_pagamentos_ordem_cronologica.docx", "etapa_processo": "contratacao", "tema_principal": "PAGAMENTOS_ORDEM_CRONOLOGICA"},
    {"blob_name": "raw/art_142_pagamentos_conta_vinculada.docx", "etapa_processo": "contratacao", "tema_principal": "PAGAMENTOS_CONTA_VINCULADA"},
    {"blob_name": "raw/art_143_pagamento_parcela_incontroversa.docx", "etapa_processo": "contratacao", "tema_principal": "PAGAMENTO_PARCELA_INCONTROVERSA"},
    {"blob_name": "raw/art_144_remuneracao_variavel_por_desempenho.docx", "etapa_processo": "contratacao", "tema_principal": "REMUNERACAO_VARIAVEL_DESEMPENHO"},
    {"blob_name": "raw/art_145_pagamento_antecipado.docx", "etapa_processo": "contratacao", "tema_principal": "PAGAMENTO_ANTECIPADO"},
    {"blob_name": "raw/art_146_liquidacao_de_despesas.docx", "etapa_processo": "contratacao", "tema_principal": "LIQUIDACAO_DESPESAS"},
    {"blob_name": "raw/art_147_contratos_nulidades.docx", "etapa_processo": "contratacao", "tema_principal": "CONTRATOS_NULIDADES"},
    {"blob_name": "raw/art_148_contratos_efeitos_da_nulidade.docx", "etapa_processo": "contratacao", "tema_principal": "EFEITOS_NULIDADE"},
    {"blob_name": "raw/art_149_nulidade_e_indenizacao.docx", "etapa_processo": "contratacao", "tema_principal": "NULIDADE_INDENIZACAO"},
    {"blob_name": "raw/art_150_recursos_orcamentarios.docx", "etapa_processo": "contratacao", "tema_principal": "RECURSOS_ORCAMENTARIOS"},
    {"blob_name": "raw/art_151_meios_alternativos_de_resolucao_de_controversias.docx", "etapa_processo": "contratacao", "tema_principal": "MEIOS_ALTERNATIVOS_RESOLUCAO_CONTROVERSIAS"},
    {"blob_name": "raw/art_152_arbitragem_e_publicidade.docx", "etapa_processo": "contratacao", "tema_principal": "ARBITRAGEM_PUBLICIDADE"},
    {"blob_name": "raw/art_153_aditamento_para_prever_meios_alternativos_de_resolucao_de_controversias.docx", "etapa_processo": "contratacao", "tema_principal": "ADITAMENTO_MEIOS_ALTERNATIVOS"},
    {"blob_name": "raw/art_154_arbitragem_isonomia.docx", "etapa_processo": "contratacao", "tema_principal": "ARBITRAGEM_ISONOMIA"},
    {"blob_name": "raw/art_155_infracoes.docx", "etapa_processo": "sancao", "tema_principal": "INFRACOES"},
    {"blob_name": "raw/art_156_penalidades.docx", "etapa_processo": "sancao", "tema_principal": "PENALIDADES"},
    {"blob_name": "raw/art_157_multa_defesa_previa.docx", "etapa_processo": "sancao", "tema_principal": "MULTA_DEFESA_PREVIA"},
    {"blob_name": "raw/art_158_instauracao_processo_responsabilizacao.docx", "etapa_processo": "sancao", "tema_principal": "PROCESSO_RESPONSABILIZACAO"},
    {"blob_name": "raw/art_159_lei_12846.docx", "etapa_processo": "sancao", "tema_principal": "LEI_ANTICORRUPCAO_12846"},
    {"blob_name": "raw/art_160_desconsideracao_da_personalidade_juridica.docx", "etapa_processo": "sancao", "tema_principal": "DESCONSIDERACAO_PERSONALIDADE_JURIDICA"},
    {"blob_name": "raw/art_161_cadastro_de_sancoes.docx", "etapa_processo": "sancao", "tema_principal": "CADASTRO_SANCOES"},
    {"blob_name": "raw/art_162_multa_de_mora.docx", "etapa_processo": "sancao", "tema_principal": "MULTA_DE_MORA"},
    {"blob_name": "raw/art_163_reabilitacao_condicoes.docx", "etapa_processo": "sancao", "tema_principal": "REABILITACAO_CONDICOES"},
    {"blob_name": "raw/art_164_impugnacoes.docx", "etapa_processo": "recurso", "tema_principal": "IMPUGNACOES"},
    {"blob_name": "raw/art_165_recursos.docx", "etapa_processo": "recurso", "tema_principal": "RECURSOS"},
    {"blob_name": "raw/art_166_recurso_contra_sancoes.docx", "etapa_processo": "recurso", "tema_principal": "RECURSO_CONTRA_SANCOES"},
    {"blob_name": "raw/art_167_inidoneidade_pedido_de_reconsideracao.docx", "etapa_processo": "recurso", "tema_principal": "INIDONEIDADE_PEDIDO_RECONSIDERACAO"},
    {"blob_name": "raw/art_168_efeito_suspensivo_recurso_e_pedido_de_reconsideracao.docx", "etapa_processo": "recurso", "tema_principal": "EFEITO_SUSPENSIVO_RECURSO"},
    {"blob_name": "raw/art_169_controle_das_contratacoes.docx", "etapa_processo": "contratacao", "tema_principal": "CONTROLE_CONTRATACOES"},
    {"blob_name": "raw/art_170_controle_das_contratacoes_criterios_de_avaliacao.docx", "etapa_processo": "contratacao", "tema_principal": "CONTROLE_CONTRATACOES_CRITERIOS_AVALIACAO"},
    {"blob_name": "raw/art_171_fiscalizacao_de_controle_procedimentos.docx", "etapa_processo": "contratacao", "tema_principal": "FISCALIZACAO_CONTROLE_PROCEDIMENTOS"},
]

ANO_DEFAULT = 2021
AUTOR_DEFAULT = ""
OBRA_DEFAULT = ""

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
    container_source = os.getenv("DOCTRINE_CONTAINER_SOURCE", "kb-doutrina-raw")
    container_processed = os.getenv("DOCTRINE_CONTAINER_PROCESSED", "kb-doutrina-processed")
    results = {"processed": 0, "already_processed": 0, "failed": 0, "errors": []}
    for i, item in enumerate(items, 1):
        blob = item["blob_name"]
        print(f"\n[{i}/{len(items)}] {blob}")
        req = DoctrineIngestRequest(
            blob_name=blob, etapa_processo=item["etapa_processo"],
            tema_principal=item["tema_principal"], autor=AUTOR_DEFAULT,
            obra=OBRA_DEFAULT, edicao="", ano=ANO_DEFAULT, capitulo="", secao="",
            force_reprocess=force,
        )
        try:
            t0 = time.time()
            res = ingest_doctrine_process_once(
                blob_service=bs, container_source=container_source,
                container_processed=container_processed, req=req,
            )
            dt = time.time() - t0
            status = res.get("status", "unknown")
            if status == "processed":
                results["processed"] += 1
                stats = res.get("stats", {})
                print(f"  OK ({dt:.0f}s): semantic={stats.get('semantic_chunks', '?')}, "
                      f"verbatim={stats.get('verbatim_legal_chunks', '?')}, "
                      f"incertos={stats.get('incertos', '?')}")
                print(f"  SHA: {res.get('source', {}).get('source_sha', '?')}")
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
    bs = get_blob_service()
    container = os.getenv("DOCTRINE_PROCESSED_CONTAINER_NAME", "kb-doutrina-processed")
    client = bs.get_container_client(container)
    blobs = [b.name for b in client.list_blobs() if b.name.endswith(".json")]
    print(f"\nBlobs processados em {container}: {len(blobs)}")
    for b in sorted(blobs):
        print(f"  {b}")
    return blobs

def main():
    parser = argparse.ArgumentParser(description="Batch OBRA_001 Lote 6 FINAL (arts 140-171)")
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
