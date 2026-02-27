"""
LOTE 5 - Batch processor para OBRA_001 (arts 100-139, 40 capitulos Lei 14.133/2021).
Uso:
  python scripts\doctrine_batch_obra_001_lote5.py --step validate
  python scripts\doctrine_batch_obra_001_lote5.py --step batch
  python scripts\doctrine_batch_obra_001_lote5.py --step status
"""
import os, sys, json, argparse, time

MANIFEST = [
    {"blob_name": "raw/art_100_restituicao_garantia.docx", "etapa_processo": "contratacao", "tema_principal": "RESTITUICAO_GARANTIA"},
    {"blob_name": "raw/art_101_bens_da_administracao_particular_depositario.docx", "etapa_processo": "contratacao", "tema_principal": "BENS_ADMINISTRACAO_DEPOSITARIO"},
    {"blob_name": "raw/art_102_assuncao_seguradora.docx", "etapa_processo": "contratacao", "tema_principal": "ASSUNCAO_SEGURADORA"},
    {"blob_name": "raw/art_103_alocacao_de_riscos.docx", "etapa_processo": "contratacao", "tema_principal": "ALOCACAO_DE_RISCOS_CONTRATO"},
    {"blob_name": "raw/art_104_prerrogativas_administracao.docx", "etapa_processo": "contratacao", "tema_principal": "PRERROGATIVAS_ADMINISTRACAO"},
    {"blob_name": "raw/art_105_duracao_contratos.docx", "etapa_processo": "contratacao", "tema_principal": "DURACAO_CONTRATOS"},
    {"blob_name": "raw/art_106_prazos_de_contratos_de_servicos_e_fornecimentos_continuos.docx", "etapa_processo": "contratacao", "tema_principal": "PRAZOS_SERVICOS_FORNECIMENTOS_CONTINUOS"},
    {"blob_name": "raw/art_107_prorrogacao_contratos_servicos_e_fornecimentos_continuos.docx", "etapa_processo": "contratacao", "tema_principal": "PRORROGACAO_SERVICOS_FORNECIMENTOS_CONTINUOS"},
    {"blob_name": "raw/art_108_contratos_de_10_anos.docx", "etapa_processo": "contratacao", "tema_principal": "CONTRATOS_DEZ_ANOS"},
    {"blob_name": "raw/art_109_contratos_indeterminados_administracao_usuaria_de_servico_publico_em_monopolio.docx", "etapa_processo": "contratacao", "tema_principal": "CONTRATOS_INDETERMINADOS_MONOPOLIO"},
    {"blob_name": "raw/art_110_contrato_de_receita_e_eficiencia.docx", "etapa_processo": "contratacao", "tema_principal": "CONTRATO_RECEITA_EFICIENCIA"},
    {"blob_name": "raw/art_111_prorrogacao_contrato_por_escopo.docx", "etapa_processo": "contratacao", "tema_principal": "PRORROGACAO_CONTRATO_ESCOPO"},
    {"blob_name": "raw/art_112_prazos_leis_especiais.docx", "etapa_processo": "contratacao", "tema_principal": "PRAZOS_LEIS_ESPECIAIS"},
    {"blob_name": "raw/art_113_prazos_servicos_associados.docx", "etapa_processo": "contratacao", "tema_principal": "PRAZOS_SERVICOS_ASSOCIADOS"},
    {"blob_name": "raw/art_114_prazos_contratos_servicos_estruturantes_de_ti.docx", "etapa_processo": "contratacao", "tema_principal": "PRAZOS_SERVICOS_ESTRUTURANTES_TI"},
    {"blob_name": "raw/art_115_execucao_do_contrato.docx", "etapa_processo": "contratacao", "tema_principal": "EXECUCAO_CONTRATO"},
    {"blob_name": "raw/art_116_reserva_de_cargos_durante_o_contrato.docx", "etapa_processo": "contratacao", "tema_principal": "RESERVA_CARGOS_CONTRATO"},
    {"blob_name": "raw/art_117_fiscalizacao_contrato.docx", "etapa_processo": "contratacao", "tema_principal": "FISCALIZACAO_CONTRATO"},
    {"blob_name": "raw/art_118_preposto_contratado.docx", "etapa_processo": "contratacao", "tema_principal": "PREPOSTO_CONTRATADO"},
    {"blob_name": "raw/art_119_correcao_contrato.docx", "etapa_processo": "contratacao", "tema_principal": "CORRECAO_CONTRATO"},
    {"blob_name": "raw/art_120_responsabilidade_danos.docx", "etapa_processo": "contratacao", "tema_principal": "RESPONSABILIDADE_DANOS"},
    {"blob_name": "raw/art_121_responsbilidade_subsidiaria_encargos.docx", "etapa_processo": "contratacao", "tema_principal": "RESPONSABILIDADE_SUBSIDIARIA_ENCARGOS"},
    {"blob_name": "raw/art_122_subcontratacao.docx", "etapa_processo": "contratacao", "tema_principal": "SUBCONTRATACAO"},
    {"blob_name": "raw/art_123_solicitacoes_do_contratado.docx", "etapa_processo": "contratacao", "tema_principal": "SOLICITACOES_CONTRATADO"},
    {"blob_name": "raw/art_124_alteracao_dos_contratos.docx", "etapa_processo": "contratacao", "tema_principal": "ALTERACAO_CONTRATOS"},
    {"blob_name": "raw/art_125_acrescimos_e_supressoes.docx", "etapa_processo": "contratacao", "tema_principal": "ACRESCIMOS_SUPRESSOES"},
    {"blob_name": "raw/art_126_limites_alteracoes.docx", "etapa_processo": "contratacao", "tema_principal": "LIMITES_ALTERACOES"},
    {"blob_name": "raw/art_127_aditamentos_precos_unitarios.docx", "etapa_processo": "contratacao", "tema_principal": "ADITAMENTOS_PRECOS_UNITARIOS"},
    {"blob_name": "raw/art_128_obras_e_servicos_engenharia_manutencao_diferenca_percentual_contrato_e_referencia.docx", "etapa_processo": "contratacao", "tema_principal": "DIFERENCA_PERCENTUAL_CONTRATO_REFERENCIA"},
    {"blob_name": "raw/art_129_supressao_e_indenizacao_custos_aquisicao_e_outros_danos.docx", "etapa_processo": "contratacao", "tema_principal": "SUPRESSAO_INDENIZACAO_CUSTOS"},
    {"blob_name": "raw/art_130_alteracao_e_equilibrio_economico_financeiro.docx", "etapa_processo": "contratacao", "tema_principal": "EQUILIBRIO_ECONOMICO_FINANCEIRO"},
    {"blob_name": "raw/art_131_reequilibrio_prazo_decadencial_e_reconhecimento_pos_extincao.docx", "etapa_processo": "contratacao", "tema_principal": "REEQUILIBRIO_PRAZO_DECADENCIAL"},
    {"blob_name": "raw/art_132_obrigatoriedade_aditivo.docx", "etapa_processo": "contratacao", "tema_principal": "OBRIGATORIEDADE_ADITIVO"},
    {"blob_name": "raw/art_133_contratacao_integrada_ou_semi_integrada.docx", "etapa_processo": "contratacao", "tema_principal": "CONTRATACAO_INTEGRADA_SEMI_INTEGRADA"},
    {"blob_name": "raw/art_134_revisao_precos_por_alteracao_tributaria.docx", "etapa_processo": "contratacao", "tema_principal": "REVISAO_PRECOS_ALTERACAO_TRIBUTARIA"},
    {"blob_name": "raw/art_135_repactuacao_contratos_servicos_continuos_com_mao_de_obra.docx", "etapa_processo": "contratacao", "tema_principal": "REPACTUACAO_SERVICOS_MAO_DE_OBRA"},
    {"blob_name": "raw/art_136_apostilamento_hipoteses.docx", "etapa_processo": "contratacao", "tema_principal": "APOSTILAMENTO_HIPOTESES"},
    {"blob_name": "raw/art_137_extincao_do_contrato_hipoteses.docx", "etapa_processo": "contratacao", "tema_principal": "EXTINCAO_CONTRATO_HIPOTESES"},
    {"blob_name": "raw/art_138_extincao_do_contrato_modalidades.docx", "etapa_processo": "contratacao", "tema_principal": "EXTINCAO_CONTRATO_MODALIDADES"},
    {"blob_name": "raw/art_139_extincao_por_ato_unilateral_consequencias.docx", "etapa_processo": "contratacao", "tema_principal": "EXTINCAO_ATO_UNILATERAL_CONSEQUENCIAS"},
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
    parser = argparse.ArgumentParser(description="Batch OBRA_001 Lote 5 (arts 100-139)")
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
