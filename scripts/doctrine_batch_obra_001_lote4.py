"""
LOTE 4 - Batch processor para OBRA_001 (arts 59-99, 40 capitulos Lei 14.133/2021).
MANIFEST granular por artigo.

Uso:
  python scripts\doctrine_batch_obra_001_lote4.py --step validate   # 2 primeiros
  python scripts\doctrine_batch_obra_001_lote4.py --step batch      # todos 40
  python scripts\doctrine_batch_obra_001_lote4.py --step status     # listar processed
  python scripts\doctrine_batch_obra_001_lote4.py --step batch --force  # reprocessar
"""
import os, sys, json, argparse, time

MANIFEST = [
    {"blob_name": "raw/art_59_julgamento.docx", "etapa_processo": "julgamento", "tema_principal": "PROCEDIMENTO_DE_JULGAMENTO"},
    {"blob_name": "raw/art_60_criterios_de_desempate.docx", "etapa_processo": "julgamento", "tema_principal": "CRITERIOS_DE_DESEMPATE"},
    {"blob_name": "raw/art_61_negociacao_com_melhor_colocado.docx", "etapa_processo": "julgamento", "tema_principal": "NEGOCIACAO_MELHOR_COLOCADO"},
    {"blob_name": "raw/art_62_habilitacao_introducao.docx", "etapa_processo": "habilitacao", "tema_principal": "HABILITACAO_INTRODUCAO"},
    {"blob_name": "raw/art_63_habilitacao_declaracao_e_procedimentos.docx", "etapa_processo": "habilitacao", "tema_principal": "HABILITACAO_DECLARACAO_PROCEDIMENTOS"},
    {"blob_name": "raw/art_64_diligencias.docx", "etapa_processo": "habilitacao", "tema_principal": "DILIGENCIAS"},
    {"blob_name": "raw/art_65_habilitacao_definicoes.docx", "etapa_processo": "habilitacao", "tema_principal": "HABILITACAO_DEFINICOES"},
    {"blob_name": "raw/art_66_habilitacao_juridica.docx", "etapa_processo": "habilitacao", "tema_principal": "HABILITACAO_JURIDICA"},
    {"blob_name": "raw/art_67_habilitacao_tecnica.docx", "etapa_processo": "habilitacao", "tema_principal": "HABILITACAO_TECNICA"},
    {"blob_name": "raw/art_68_habilitacoes_fiscal_social_e_trabalhista.docx", "etapa_processo": "habilitacao", "tema_principal": "HABILITACAO_FISCAL_SOCIAL_TRABALHISTA"},
    {"blob_name": "raw/art_69_habilitacao_economico_financeira.docx", "etapa_processo": "habilitacao", "tema_principal": "HABILITACAO_ECONOMICO_FINANCEIRA"},
    {"blob_name": "raw/art_71_encerramento_licitacao.docx", "etapa_processo": "julgamento", "tema_principal": "ENCERRAMENTO_LICITACAO"},
    {"blob_name": "raw/art_72_contratacao_direta.docx", "etapa_processo": "contratacao", "tema_principal": "CONTRATACAO_DIRETA"},
    {"blob_name": "raw/art_73_contratacao_direta_indevida.docx", "etapa_processo": "contratacao", "tema_principal": "CONTRATACAO_DIRETA_INDEVIDA"},
    {"blob_name": "raw/art_74_inexibilidade_de_licitacao.docx", "etapa_processo": "contratacao", "tema_principal": "INEXIGIBILIDADE_LICITACAO"},
    {"blob_name": "raw/art_75_dispensa_licitacao.docx", "etapa_processo": "contratacao", "tema_principal": "DISPENSA_LICITACAO"},
    {"blob_name": "raw/art_76_alienacao_de_bens.docx", "etapa_processo": "contratacao", "tema_principal": "ALIENACAO_DE_BENS"},
    {"blob_name": "raw/art_77_direito_preferencia_ocupante_imovel.docx", "etapa_processo": "contratacao", "tema_principal": "DIREITO_PREFERENCIA_OCUPANTE_IMOVEL"},
    {"blob_name": "raw/art_78_procedimentos_auxiliares.docx", "etapa_processo": "edital", "tema_principal": "PROCEDIMENTOS_AUXILIARES"},
    {"blob_name": "raw/art_79_credenciamento.docx", "etapa_processo": "edital", "tema_principal": "CREDENCIAMENTO"},
    {"blob_name": "raw/art_80_pre_qualificacao.docx", "etapa_processo": "edital", "tema_principal": "PRE_QUALIFICACAO"},
    {"blob_name": "raw/art_81_manifestacao_de_interesse.docx", "etapa_processo": "edital", "tema_principal": "MANIFESTACAO_DE_INTERESSE"},
    {"blob_name": "raw/art_82_registro_de_precos.docx", "etapa_processo": "edital", "tema_principal": "REGISTRO_DE_PRECOS"},
    {"blob_name": "raw/art_83_registro_de_precos_e_licitacao_concomitante.docx", "etapa_processo": "edital", "tema_principal": "REGISTRO_PRECOS_LICITACAO_CONCOMITANTE"},
    {"blob_name": "raw/art_84_registro_de_precos_vigencia.docx", "etapa_processo": "edital", "tema_principal": "REGISTRO_PRECOS_VIGENCIA"},
    {"blob_name": "raw/art_85_registro_de_precos_para_obras_e_servicos_de_engenharia.docx", "etapa_processo": "edital", "tema_principal": "REGISTRO_PRECOS_OBRAS_ENGENHARIA"},
    {"blob_name": "raw/art_86_srp_manifestacao_de_interesse_outros_orgaos.docx", "etapa_processo": "edital", "tema_principal": "SRP_MANIFESTACAO_INTERESSE_OUTRSS_ORGAOS"},
    {"blob_name": "raw/art_87_registro_cadastral.docx", "etapa_processo": "habilitacao", "tema_principal": "REGISTRO_CADASTRAL"},
    {"blob_name": "raw/art_88_registro_cadastral_procedimentos.docx", "etapa_processo": "habilitacao", "tema_principal": "REGISTRO_CADASTRAL_PROCEDIMENTOS"},
    {"blob_name": "raw/art_89_formalizacao_de_contratos.docx", "etapa_processo": "contratacao", "tema_principal": "FORMALIZACAO_CONTRATOS"},
    {"blob_name": "raw/art_90_convocacao_assinatura_contrato.docx", "etapa_processo": "contratacao", "tema_principal": "CONVOCACAO_ASSINATURA_CONTRATO"},
    {"blob_name": "raw/art_91_arquivamento_contrato.docx", "etapa_processo": "contratacao", "tema_principal": "ARQUIVAMENTO_CONTRATO"},
    {"blob_name": "raw/art_92_contratos_clausulas_obrigatorias.docx", "etapa_processo": "contratacao", "tema_principal": "CLAUSULAS_OBRIGATORIAS_CONTRATO"},
    {"blob_name": "raw/art_93_cessao_direitos_patrimoniais.docx", "etapa_processo": "contratacao", "tema_principal": "CESSAO_DIREITOS_PATRIMONIAIS"},
    {"blob_name": "raw/art_94_divulgacao_do_contrato_no_pnpc.docx", "etapa_processo": "contratacao", "tema_principal": "DIVULGACAO_CONTRATO_PNPC"},
    {"blob_name": "raw/art_95_instrumento_de_contrato_obrigatoriedade_e_dispensa.docx", "etapa_processo": "contratacao", "tema_principal": "INSTRUMENTO_CONTRATO_OBRIGATORIEDADE"},
    {"blob_name": "raw/art_96_garantias.docx", "etapa_processo": "contratacao", "tema_principal": "GARANTIAS_CONTRATUAIS"},
    {"blob_name": "raw/art_97_seguro_garantia.docx", "etapa_processo": "contratacao", "tema_principal": "SEGURO_GARANTIA"},
    {"blob_name": "raw/art_98_percentual_garantia.docx", "etapa_processo": "contratacao", "tema_principal": "PERCENTUAL_GARANTIA"},
    {"blob_name": "raw/art_99_garantia_obras_grande_vulto.docx", "etapa_processo": "contratacao", "tema_principal": "GARANTIA_OBRAS_GRANDE_VULTO"},
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
    parser = argparse.ArgumentParser(description="Batch OBRA_001 Lote 4 (arts 59-99)")
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
