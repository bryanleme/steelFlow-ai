# Data Card — SteelFlow AI

## Aviso essencial

Este conjunto é 100% sintético e foi criado para um protótipo educacional offline. Não descreve nenhuma fábrica, lote, produto, operador, fornecedor ou desempenho real. J55, N80, L80 e P110 são somente códigos de contexto industrial. Limites dimensionais, mecânicos e operacionais são internos e simulados; não representam API 5CT, certificação nem instrução operacional.

## Finalidade

Representar uma fábrica fictícia de tubos OCTG sem costura com rastreabilidade suficiente para estudar:

- produtividade e efeito de mix;
- qualidade dimensional, mecânica e NDT simulada;
- energia por tonelada boa;
- desgaste, manutenção e paradas não planejadas;
- relações não lineares e interações de processo;
- previsão temporal, incerteza, OOD e cenários restritos em fases posteriores.

O conjunto não deve ser usado para controle de equipamento, especificação de processo real, certificação, avaliação de pessoas ou inferência causal industrial.

## Perfis

| Perfil | Período inclusivo | Ordens | Tubos | Etapas | Sensores resumidos | Qualidade | Paradas |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | 2025-01-01 a 2025-01-02 | 24 | 480 | 3.456 | 15.360 | 2.880 | 40 |
| `dev` | 2025-01-01 a 2025-01-30 | 500 | 10.500 | 75.600 | 336.000 | 63.000 | 820 |
| `mvp` | 2024-01-01 a 2025-12-31 | 12.000 | 250.000 | 1.800.000 | 8.000.000 | 1.500.000 | 20.000 |

`test` e `dev` foram materializados e validados em 2026-08-18. `mvp` continua configurado, mas não foi executado.

## Conteúdo

O run público possui cinco tabelas de referência e dez tabelas factuais:

- dimensões: produtos, linhas, turnos, ativos e disponibilidade de features;
- fatos: ordens, lotes de tarugo, tubos, parâmetros, etapas, janelas de sensores, qualidade, energia, paradas e manutenção.

Cada tubo possui:

- sete etapas base e uma oitava etapa quando há tratamento térmico;
- 32 janelas de sensores, combinando oito tipos de sensor e quatro janelas;
- seis resultados de inspeção;
- três eventos de energia;
- parâmetros controláveis, mediadores observáveis e resultados separados por disponibilidade temporal.

Não há sinal bruto de alta frequência.

## Geração e reprodutibilidade

O `simulation_run_id` deriva deterministicamente de perfil, versão do gerador, seed principal e SHA-256 do bundle de configuração. Seeds de componentes usam namespaces independentes derivados por SHA-256.

O manifest registra:

- versão e perfil;
- seed principal e seeds derivadas;
- hash da configuração;
- período e volumes solicitados;
- contagem, arquivos e hashes por tabela;
- dependências e runtime;
- início, fim, duração, status e erros.

Testes geraram duas cópias isoladas do perfil `test` e confirmaram os mesmos IDs, contagens, hashes lógicos e hashes físicos de Parquet.

## Particionamento e armazenamento

- `test` e `dev`: partições diárias;
- `mvp`: partições mensais;
- formato: Parquet comprimido com Zstandard;
- escrita: buffers limitados por perfil;
- substituição: proibida por padrão; `--force` afeta apenas o run determinístico selecionado.

Dados gerados são recriáveis e ficam fora do Git.

## Ausência de sensores

| Mecanismo | Implementação sintética | Observabilidade |
|---|---|---|
| MCAR | seleção determinística rara independente do estado | `missingness_type = MCAR` |
| MAR | turno noturno combinado com degradação observável | `missingness_type = MAR` |
| Falha em bloco | duas janelas contíguas em combinações linha/dia/sensor | `missingness_type = BLOCK` |
| Não aplicável | sensor de têmpera quando o tubo não passa por tratamento térmico | `missingness_type = NOT_APPLICABLE` |

No perfil `dev`, as contagens observadas foram: 1.421 MCAR, 613 MAR, 2.486 em bloco, 33.600 não aplicáveis e 297.880 válidas.

## Verdade causal isolada

Parâmetros latentes por tubo são gravados em `data/ground_truth`, fora de `data/raw`. O manifest público registra apenas hash/contagem e a política de acesso. `features`, `models` e `optimization` não podem importar o módulo privado nem ler essa área. A auditoria pós-modelagem será executada separadamente na Fase 5.

## Qualidade e validação

`validate-data` executa 83 verificações, incluindo:

- tabela e contagem esperada;
- PK não nula e única;
- FK para ordens, tubos, lotes, linhas, turnos e ativos;
- `simulation_run_id` uniforme;
- ordem e disponibilidade temporal;
- domínios e ranges internos simulados;
- completude coerente das estatísticas de sensores;
- presença de MCAR, MAR e falhas em bloco;
- checksum de cada Parquet e do manifest;
- isolamento da verdade causal;
- cobertura dos quatro graus e doze produtos.

Resultados reais da Fase 2: `test` 83/83 e `dev` 83/83.

## Estatísticas descritivas da execução `dev`

- FPY sintético: 86,0762%;
- retrabalho: 13,1048%;
- refugo: 0,8190%;
- duração média de parada: 23,3184 minutos;
- 529.014 linhas públicas;
- 30,35 MB de Parquet raw;
- 0,94 MB de verdade causal isolada;
- 19,05 segundos para geração e 1,61 segundo para validação no ambiente local.

Esses valores são propriedades desta simulação e não constituem benchmark ou ganho industrial.

## Limitações conhecidas

- O gerador é um modelo substituto educacional, não uma física completa do processo.
- Correlações foram projetadas e não demonstram causalidade industrial.
- Calendário, receitas, química e limites foram simplificados.
- O perfil `dev` não mede estabilidade de longo prazo; drift completo exige `mvp`.
- O suporte para eventos raros será reavaliado por janela temporal e segmento antes da modelagem.
- Não há dados pessoais nem ranking de operadores.
