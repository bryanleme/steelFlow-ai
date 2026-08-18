# Plano de implementação rastreável

## Objetivo e regra de execução

Construir o SteelFlow AI como protótipo offline e reproduzível de apoio à decisão para uma fábrica fictícia de tubos OCTG sem costura. Todo dado será sintético; todos os limites, internos e simulados. O trabalho avança por checkpoints aprovados, sem iniciar a fase seguinte silenciosamente.

**Status:** Fases 0–4 implementadas e validadas localmente em 2026-08-18; Fase 5 aguarda aprovação do Checkpoint 4.

## Estado inicial auditado em 2026-08-18

- O diretório de trabalho estava vazio: não havia `README.md`, charter, SIPOC, dicionário de dados ou código a preservar.
- O diretório não foi reconhecido como repositório Git; portanto, não foi possível obter branch ou alterações pendentes.
- Ambiente encontrado: Windows 11, Python 3.14.6 e `pip` 26.1.2.
- `uv`, `make`, Pydantic, PyYAML, pytest e Ruff não estavam inicialmente disponíveis.
- Não há evidência, nesta fase, de Power BI Desktop nem das dependências binárias de dados/ML.

## Estratégia de entrega

| Bloco | Entregáveis principais | Verificação de saída |
|---|---|---|
| Fases 0–1 — fundação | auditoria, plano, decisões, riscos, `pyproject.toml`, CLI, logging, configuração tipada, três perfis, testes e bootstrap | instalação editável; `doctor`; validação dos três perfis; pytest; Ruff; comandos futuros falham de forma explícita |
| Fase 2 — geração | dimensões, ordens, tubos, etapas, sensores resumidos, qualidade, energia, paradas, manutenção, causalidade isolada, manifests e IDs determinísticos | `test` e `dev` gerados; contratos; integridade; reprodutibilidade lógica e hashes; ausência de importação da verdade causal pelo pipeline analítico |
| Fase 3 — curadoria | Parquet curated, DuckDB, marts SQL, KPIs, esquema estrela e exports Power BI | reconciliação de grãos e fórmulas; chaves; divisões por zero; consultas e exports testados |
| Fase 4 — diagnóstico/features | análises reproduzíveis, ajuste de mix, Pareto, snapshots por instante de decisão e contrato de disponibilidade | testes temporais e contra vazamento; contrato de features congelado |
| Fase 5 — modelos | baselines, CatBoost, calibração exclusiva, MultiQuantile, SHAP, avaliação temporal e model card | comparação no teste final intocado; métricas globais/segmentadas; calibração e cobertura; auditoria de quatro mecanismos |
| Fase 6 — otimização | envelopes condicionais, OOD, NSGA-II, restrições duras e alternativas Pareto | 100% dos cenários publicados dentro das restrições; recusa de OOD; artefato reproduzível |
| Fase 7 — produto | cinco páginas Streamlit, DuckDB sob demanda, fluxo de cenário, confirmação humana, pacote Power BI e screenshots reais | smoke test ponta a ponta; app inicia sem artefatos; exportação JSON/CSV; pacote Power BI verificável |
| Fase 8 — portfólio | cards, case, LinkedIn, carrossel, demo, auditoria de números e aceite final | instalação limpa/equivalente; rastreabilidade de cada número; relatório final com pendências reais |

## Critérios verificáveis por fase

### Fases 0–1

1. Três perfis carregam por modelos estritos e rejeitam chaves desconhecidas.
2. `test` cobre 2 dias, `dev` 30 dias e `mvp` 24 meses inclusivos.
3. Cada configuração e o bundle completo possuem SHA-256 lógico estável.
4. A configuração veta caminhos absolutos ou com travessia para outputs.
5. A CLI instalada expõe ajuda, validação, hash e diagnóstico.
6. Comandos de fases futuras falham com código 2 e mensagem clara.
7. Testes unitários e de integração e lint passam.
8. README documenta bootstrap em PowerShell e Linux/macOS sem pressupor `make`.

### Fase 2

1. Perfil `test` gera todas as tabelas previstas e um manifest completo.
2. Duas execuções isoladas, com mesma versão/configuração/semente, produzem IDs, contagens e hashes lógicos idênticos.
3. Perfil `dev` é gerado por partições sem carregar o conjunto inteiro em memória.
4. Contratos validam PK/FK, domínio, unidades, ranges, tempo e completude esperada.
5. MCAR, MAR e falhas em bloco são mensuráveis e documentadas.
6. A verdade causal fica em limite de pacote/armazenamento isolado e recebe teste arquitetural.

### Fase 3

1. DuckDB recriável contém `raw`, `curated`, `analytics`, `features` e `model_outputs`.
2. TBH/GTPH reconcilia massa aprovada na primeira passagem e horas produtivas nos grãos linha × turno e ordem.
3. Todos os KPIs documentam fórmula, grão, unidade, filtros, origem e divisão por zero.
4. Marts e exports preservam relacionamentos do esquema estrela.

**Evidência executada:** os perfis `test` e `dev` produziram bancos DuckDB com 66 objetos e 13 exports estrela cada. A validação final executou 43 checks por perfil sem falhas, incluindo linhagem, contagens das 15 tabelas curated, grãos, fórmulas, reconciliações, chaves, snapshots point-in-time e checksums dos exports.

### Fase 4

1. Cada feature registra disponibilidade e timestamp máximo de origem.
2. Snapshots pré-ordem não contêm IDs, targets, proxies nem campos pós-processo.
3. Transformações temporais são ajustadas exclusivamente no fold de treino.
4. Diagnósticos mostram desempenho bruto e ajustado por mix sem linguagem causal indevida.

**Evidência executada:** o `dev` materializou 4.549 linhas em sete conjuntos diagnósticos e passou 8/8 checks. Os snapshots congelados contêm 500 ordens, 10.500 tubos e 5.400 janelas ativo × 2 h e passaram 27/27 checks de contrato, timestamps, separação `X`/índice/`y`, IDs, targets, proxies, hashes e isolamento causal. O DuckDB ampliado passou 46/46 checks nos dois perfis.

### Fase 5

1. Divisão cronológica separa treino, tuning, calibração e teste final.
2. Baselines obrigatórios e modelos principais usam o mesmo teste final.
3. Regressão reporta MAE, RMSE, R², pinball loss e cobertura P10–P90 por segmentos.
4. Classificação reporta PR-AUC, ROC-AUC, log loss, Brier, ECE, matriz de confusão e recall sob orçamento.
5. A meta de 5% em MAE de TBH é reportada honestamente, atingida ou não.
6. SHAP, estabilidade temporal, latência e limitações constam no model card.

### Fase 6

1. Somente variáveis controláveis elegíveis variam no otimizador.
2. Envelope histórico, taxa máxima de mudança, risco e incerteza são restrições verificadas.
3. Resultado contém atual, conservador, equilibrado e orientado a produtividade quando factíveis.
4. Cada alternativa registra OOD/distância, restrições ativas, incerteza e principais fatores.

### Fases 7–8

1. As cinco páginas funcionam com consultas agregadas e cache consciente.
2. O app exibe avisos sintéticos e exige aprovação humana explícita.
3. Ausência de artefatos produz orientação útil, não traceback.
4. Power BI recebe exports, relacionamentos, Power Query, tema, wireframe e DAX validados como texto/JSON.
5. `.pbix` só será declarado se realmente criado, aberto e validado.
6. Screenshots, case e publicações usam apenas resultados gerados rastreáveis.

## Estimativa preliminar do perfil `mvp`

Esta é uma estimativa de capacidade anterior à execução, não um benchmark. Para aproximadamente 11,8 milhões de linhas factuais configuradas, espera-se:

| Recurso | Faixa estimada | Hipótese principal |
|---|---:|---|
| Tempo de geração + validação inicial | 20–60 min | escrita Parquet em lotes de 100 mil, CPU local moderna |
| Pico de memória | 2–6 GB | partições mensais e tabelas colunares, sem sinais brutos |
| Parquet raw | 2–6 GB | compressão Zstandard/Snappy e cardinalidade moderada |
| DuckDB + curated + exports | 3–8 GB adicionais | materialização seletiva, sem duplicar sensores integralmente |

Antes de executar `mvp`, a Fase 2 medirá tempo, memória e tamanho do perfil `dev`, extrapolará por tabela e exigirá espaço livre compatível. Se a máquina não suportar a escala, o pipeline permanecerá escalável e a limitação será registrada sem inventar resultados.

### Refinamento após execução de `dev`

O perfil `dev` produziu 529.014 registros públicos em 19,05 segundos, 30,35 MB de Parquet raw e 0,94 MB de verdade causal isolada. A validação de 83 contratos levou 1,61 segundo. Esses números são medições locais, não garantias para outra máquina.

Uma extrapolação linear por linhas sugere aproximadamente 8–20 minutos e 0,7–1,5 GB de Parquet raw para `mvp`. O pico de memória ainda não foi medido por telemetria externa; pela escrita em lotes de até 100 mil registros, mantém-se uma reserva conservadora de 2–6 GB. O perfil `mvp` não será executado sem nova verificação de espaço e sem necessidade demonstrável.

## Dependências por camada

- Fundação: Pydantic e PyYAML; pytest/Ruff apenas em desenvolvimento.
- Dados: NumPy, pandas/Polars, PyArrow e DuckDB.
- ML: scikit-learn, CatBoost, SHAP, pymoo e joblib.
- Produto: Streamlit e Plotly.

As dependências pesadas ficam em extras para que a fundação seja validável sem antecipar incompatibilidades ou custo de instalação das fases futuras.

## Sequência imediata após aprovação

Fase 5: definir janelas cronológicas distintas de treino, tuning, calibração e teste final; implementar baselines e modelos principais; avaliar incerteza, calibração, segmentos, estabilidade e latência; produzir SHAP, model cards e auditoria separada dos mecanismos sintéticos. O teste final permanecerá intocado durante ajustes.
