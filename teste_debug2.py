from govy.extractors.o001_objeto import _extract_candidates, _is_texto_generico_objeto, _extrair_objeto_folha_dados

texto = '''
1. DO OBJETO
1.1. O objeto da presente dispensa de licitacao visa a contratacao de prestacao de servicos continuos com dedicacao exclusiva de mao de obra, conforme descricao e condicoes especificadas no ANEXO IV - FOLHA DE DADOS (CGDL 1.1) e de acordo com as condicoes contidas no Termo de Referencia.
2. DA DISPONIBILIZACAO

CGDL 1.1
Contratacao de empresa especializada para a prestacao de servicos continuos de limpeza e higienizacao nas Escolas Estaduais do Estado do Rio Grande do Sul.
CGDL 2.1
Site: www.compras.rs.gov.br
'''

# Testar diretamente a extracao da FOLHA DE DADOS
print('=== Teste direto da FOLHA DE DADOS ===')
folha = _extrair_objeto_folha_dados(texto)
print(f'Resultado: {folha}')

# Ver o que o candidato detecta como generico
candidatos = _extract_candidates(texto)
if candidatos:
    obj, ev, score = candidatos[0]
    print(f'\n=== Candidato ===')
    print(f'Objeto: {obj[:80]}')
    print(f'Score: {score}')
    print(f'Generico: {_is_texto_generico_objeto(obj)}')
