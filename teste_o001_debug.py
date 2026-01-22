from govy.extractors.o001_objeto import _extract_candidates, _is_texto_generico_objeto

# Simular o texto do edital com a estrutura real
texto = '''
1. DO OBJETO
1.1. O objeto da presente dispensa de licitacao visa a contratacao de prestacao de servicos continuos com dedicacao exclusiva de mao de obra, conforme descricao e condicoes especificadas no ANEXO IV - FOLHA DE DADOS (CGDL 1.1) e de acordo com as condicoes contidas no Termo de Referencia.
2. DA DISPONIBILIZACAO

da contratacao.7.5. No momento do envio da proposta, o participante devera prestar, por meio do sistema.

CGDL 1.1
Contratacao de empresa especializada para a prestacao de servicos continuos de limpeza e higienizacao nas Escolas Estaduais do Estado do Rio Grande do Sul.
CGDL 2.1
Site: www.compras.rs.gov.br
'''

print('=== Candidatos extraidos ===')
candidatos = _extract_candidates(texto)
print(f'Total: {len(candidatos)}')
for i, (obj, ev, score) in enumerate(candidatos):
    print(f'\n--- Candidato {i+1} (score={score}) ---')
    print(f'Objeto: {obj[:100]}...')
    print(f'Generico? {_is_texto_generico_objeto(obj)}')
