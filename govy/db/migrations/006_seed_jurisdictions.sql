-- 006_seed_jurisdictions.sql
-- Seed: BR federal + 27 UFs

INSERT INTO jurisdiction (jurisdiction_id, name, uf, level) VALUES
    ('federal_br', 'Federal - Brasil', NULL, 'federal'),
    ('ac', 'Acre', 'AC', 'estadual'),
    ('al', 'Alagoas', 'AL', 'estadual'),
    ('am', 'Amazonas', 'AM', 'estadual'),
    ('ap', 'Amapá', 'AP', 'estadual'),
    ('ba', 'Bahia', 'BA', 'estadual'),
    ('ce', 'Ceará', 'CE', 'estadual'),
    ('df', 'Distrito Federal', 'DF', 'estadual'),
    ('es', 'Espírito Santo', 'ES', 'estadual'),
    ('go', 'Goiás', 'GO', 'estadual'),
    ('ma', 'Maranhão', 'MA', 'estadual'),
    ('mg', 'Minas Gerais', 'MG', 'estadual'),
    ('ms', 'Mato Grosso do Sul', 'MS', 'estadual'),
    ('mt', 'Mato Grosso', 'MT', 'estadual'),
    ('pa', 'Pará', 'PA', 'estadual'),
    ('pb', 'Paraíba', 'PB', 'estadual'),
    ('pe', 'Pernambuco', 'PE', 'estadual'),
    ('pi', 'Piauí', 'PI', 'estadual'),
    ('pr', 'Paraná', 'PR', 'estadual'),
    ('rj', 'Rio de Janeiro', 'RJ', 'estadual'),
    ('rn', 'Rio Grande do Norte', 'RN', 'estadual'),
    ('ro', 'Rondônia', 'RO', 'estadual'),
    ('rr', 'Roraima', 'RR', 'estadual'),
    ('rs', 'Rio Grande do Sul', 'RS', 'estadual'),
    ('sc', 'Santa Catarina', 'SC', 'estadual'),
    ('se', 'Sergipe', 'SE', 'estadual'),
    ('sp', 'São Paulo', 'SP', 'estadual'),
    ('to', 'Tocantins', 'TO', 'estadual')
ON CONFLICT (jurisdiction_id) DO NOTHING;
