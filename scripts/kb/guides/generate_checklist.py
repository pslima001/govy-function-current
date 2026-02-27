"""
CLI — Gerar checklist de auditoria para um edital/TR
=====================================================
Usage:
    python scripts/kb/guides/generate_checklist.py <pdf_path> [--no-retriever] [--output <file.json>]

Exemplos:
    python scripts/kb/guides/generate_checklist.py edital.pdf
    python scripts/kb/guides/generate_checklist.py edital.pdf --no-retriever --output resultado.json

Env vars (quando usando retriever):
    AZURE_SEARCH_API_KEY, AZURE_SEARCH_ENDPOINT, OPENAI_API_KEY
"""
import argparse
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from govy.checklist.generator import generate_checklist_from_pdf


def main():
    parser = argparse.ArgumentParser(
        description="Gerar checklist de auditoria para edital/TR"
    )
    parser.add_argument("pdf_path", help="Caminho para o PDF do edital/TR")
    parser.add_argument(
        "--no-retriever",
        action="store_true",
        help="Desabilitar busca no guia_tcu (offline mode)",
    )
    parser.add_argument(
        "--output", "-o",
        help="Salvar JSON em arquivo (default: stdout)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Log detalhado",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if not os.path.isfile(args.pdf_path):
        print(f"ERRO: Arquivo nao encontrado: {args.pdf_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Analisando: {args.pdf_path}")
    print(f"Retriever: {'OFF' if args.no_retriever else 'ON'}")

    result = generate_checklist_from_pdf(
        args.pdf_path,
        use_retriever=not args.no_retriever,
    )

    output_json = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"\nResultado salvo em: {args.output}")
    else:
        print("\n" + output_json)

    # Summary
    print(f"\n--- RESUMO ---")
    print(f"Run ID: {result.run_id}")
    print(f"Arquivo: {result.arquivo_analisado}")
    print(f"Total checks: {result.total_checks}")
    print(f"Sinalizacao: {result.sinalizacao_distribution}")
    print(f"Stages: {result.stage_tag_distribution}")
    if result.ni_reason_distribution:
        print(f"NI reasons: {result.ni_reason_distribution}")


if __name__ == "__main__":
    main()
