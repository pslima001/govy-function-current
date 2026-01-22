from govy.extractors.o001_objeto import _is_texto_generico_objeto, _extrair_objeto_folha_dados

# Texto de exemplo do edital
texto_generico = 'O objeto da presente dispensa visa contratacao conforme descricao especificadas no ANEXO IV - FOLHA DE DADOS (CGDL 1.1)'

print('=== Teste 1: Detectar texto generico ===')
resultado = _is_texto_generico_objeto(texto_generico)
print(f'Texto generico detectado: {resultado}')

# Simular texto com CGDL 1.1 real
texto_com_cgdl = '''blablabla
CGDL 1.1
Contratacao de empresa especializada para a prestacao de servicos continuos de limpeza.
CGDL 2.1
Site: www.compras.rs.gov.br
'''

print('\n=== Teste 2: Extrair da FOLHA DE DADOS ===')
objeto = _extrair_objeto_folha_dados(texto_com_cgdl)
print(f'Objeto extraido: {objeto}')
