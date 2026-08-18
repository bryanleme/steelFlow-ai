# SteelFlow AI

> Protótipo educacional offline, construído exclusivamente com dados sintéticos. Os limites são internos e simulados; o sistema não é validado pela API 5CT, não controla máquinas e não fornece instruções para operação industrial real.

SteelFlow AI é um *decision-support digital twin* simplificado para uma fábrica fictícia de tubos OCTG de aço sem costura. O produto demonstra como separar efeito de mix, estimar produtividade, qualidade, energia e risco com incerteza e comparar alternativas condicionais sob restrições — sempre com aprovação humana.

**English summary:** SteelFlow AI is an offline, reproducible portfolio prototype built entirely from synthetic data. It combines temporal machine learning, calibrated uncertainty, explainability and constrained Pareto scenarios. It is not a validated physical digital twin and never controls production equipment.

## Estado atual

As Fases 0–8 entregam a fundação, o gerador auditável, a camada analítica, o
contrato point-in-time, a modelagem temporal, a otimização segura, o produto e o pacote
final de portfólio:

- configuração YAML tipada e estrita para os perfis `test`, `dev` e `mvp`;
- CLI instalável com diagnóstico, validação e hash estável das configurações;
- logging estruturado;
- estrutura modular para geração, validação, curadoria, features, modelos e otimização;
- testes unitários e de integração da fundação;
- plano rastreável, decisões e riscos documentados.
- geração incremental de dimensões, ordens, tarugos, tubos, etapas, parâmetros, sensores resumidos, qualidade, energia, paradas e manutenção;
- IDs, seeds, manifests e hashes lógicos/físicos determinísticos;
- verdade causal por tubo armazenada fora da camada `raw` e proibida para features/modelos;
- contratos automáticos de PK/FK, temporalidade, domínios, ranges, completude e linhagem.
- DuckDB recriável com schemas `raw`, `curated`, `analytics`, `features`, `model_outputs` e `metadata`;
- fatos, dimensões e marts reconciliados nos grãos por ordem e data × linha × turno;
- catálogo executável e documentação de 17 KPIs, incluindo indicadores ainda planejados;
- 13 tabelas estrela exportadas em CSV e Parquet para Power BI, com hashes e DAX.
- diagnóstico reproduzível de tendências, mix, Pareto, controle estatístico e interações;
- três snapshots congelados com `X`, índice e targets fisicamente separados;
- verificações automáticas de timestamps, IDs, targets, proxies e isolamento causal.
- quatro janelas cronológicas com embargo de rótulos, baselines e dez tarefas CatBoost;
- calibração sigmoid exclusiva, P10/P50/P90, TreeSHAP global/segmentado/local e model cards;
- avaliação final idempotente, métricas segmentadas e auditoria causal posterior 6/6.
- envelopes históricos condicionais, barreira OOD e limites de mudança para 11 controles elegíveis;
- NSGA-II com seis objetivos, nove restrições duras e quatro cenários comparáveis por contexto;
- recusa explícita fora da distribuição, incerteza P10/P50/P90 e aprovação humana obrigatória.
- aplicativo Streamlit responsivo com cinco páginas, consultas DuckDB agregadas e cache;
- laboratório de cenários com controles contratados, confirmação humana e exportação JSON/CSV;
- pacote Power BI com 13 tabelas, 26 arquivos verificados, tema, wireframe e checklist.
- case study, post, carrossel e roteiro de demonstração com linguagem responsável;
- auditoria executável que rastreia números publicados até artefatos JSON versionados;
- data card, model card, auditoria causal, riscos e aceitação final consolidados.

O perfil `mvp` foi gerado, validado, curado, modelado, otimizado e integrado ao
produto em três contextos demonstrativos. A meta de reduzir em 5% o MAE de TBH não
foi atingida: a melhora final foi 0,98%. Os cenários são estimativas em backtest
sintético, não contrafactuais causais nem instruções de operação. Não há controle de máquina.

## Instalação

Python compatível: `>=3.11,<3.15`. As Fases 5–7 foram verificadas no Python 3.14.6
com CatBoost 1.2.10, scikit-learn 1.9.0, SHAP 0.52.0, pymoo 0.6.2 e Streamlit 1.61.1.

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e ".[all]"
.venv\Scripts\python -m steelflow doctor
.venv\Scripts\python -m pytest
```

### Linux e macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[all]"
.venv/bin/python -m steelflow doctor
.venv/bin/python -m pytest
```

Se `uv` estiver disponível, o bootstrap equivalente é:

```bash
uv venv
uv pip install -e ".[all]"
uv run steelflow doctor
uv run pytest
```

## Comandos disponíveis

```bash
python -m steelflow --help
python -m steelflow validate-config --all
python -m steelflow config-hash --profile dev
python -m steelflow doctor --json
python -m steelflow generate --profile test
python -m steelflow validate-data --profile test
python -m steelflow build-db --profile test
python -m steelflow generate --profile dev
python -m steelflow validate-data --profile dev
python -m steelflow build-db --profile dev
python -m steelflow diagnose --profile dev
python -m steelflow build-features --profile dev
python -m steelflow train --profile mvp
python -m steelflow evaluate --profile mvp
python -m steelflow optimize-demo --profile mvp
python -m steelflow app --profile mvp --check
python -m steelflow app --profile mvp
python -m steelflow audit-portfolio
powershell -ExecutionPolicy Bypass -File scripts/security_audit.ps1 -History
python -m pytest
python -m ruff check .
```

Quando `make` estiver instalado, `make setup`, `make validate-config`, `make doctor` e `make test` são atalhos. No Windows sem `make`, use os comandos Python acima.

## Comandos de produto e disponibilidade

| Atalho | Comando Python equivalente | Fase de implementação |
|---|---|---:|
| `make generate-dev` | `python -m steelflow generate --profile dev` | Implementado |
| `make validate-data` | `python -m steelflow validate-data --profile dev` | Implementado |
| `make build-db` | `python -m steelflow build-db --profile dev` | Implementado |
| `make diagnose` | `python -m steelflow diagnose --profile dev` | Implementado |
| `make build-features` | `python -m steelflow build-features --profile dev` | Implementado |
| `make train` | `python -m steelflow train --profile dev` | Implementado |
| `make evaluate` | `python -m steelflow evaluate --profile dev` | Implementado |
| `make optimize-demo` | `python -m steelflow optimize-demo --profile mvp` | Implementado |
| `make app` | `python -m steelflow app --profile mvp` | Implementado |
| `make audit-portfolio` | `python -m steelflow audit-portfolio` | Implementado |

`app --check` valida os artefatos sem abrir servidor. `app` inicia as cinco páginas em
`http://127.0.0.1:8501`; se algum artefato estiver ausente, a tela apresenta os comandos
de recuperação em vez de um traceback.

## Perfis

| Perfil | Período inclusivo | Finalidade | Volume de referência |
|---|---:|---|---:|
| `test` | 2 dias | CI e testes rápidos | 24 ordens / 480 tubos |
| `dev` | 30 dias | desenvolvimento e validação local | 500 ordens / 10.500 tubos |
| `mvp` | 24 meses | demonstração em escala de portfólio | 12.000 ordens / 250.000 tubos |

Os três perfis foram materializados. O `mvp` produziu 12.594.517 registros públicos <!-- [claim:MVP_PUBLIC_ROWS] --> em 410,29 s e 0,672 GiB de Parquet raw no ambiente local.

## Evidência da Fase 2

| Perfil | Linhas públicas | Tempo de geração | Disco raw | Validação | Hash lógico |
|---|---:|---:|---:|---:|---|
| `test` | 24.263 | 2,55 s | 1,56 MB | 83/83 | `1a3cfadac7af…` |
| `dev` | 529.014 | 19,05 s | 30,35 MB | 83/83 | `ee400a163caf…` |

Medições locais em Python 3.14.6, não benchmarks universais. Os dados são inteiramente sintéticos e os resultados não representam desempenho de uma fábrica real.

Os arquivos são gravados em `data/raw/<profile>/<simulation_run_id>/`; a verdade causal fica separada em `data/ground_truth/`. Ambos são recriáveis e ignorados pelo Git. `--force` substitui somente o diretório determinístico da configuração selecionada.

## Evidência da Fase 3

| Perfil | Banco DuckDB | Tempo de build | Validação analítica | Marts executivos / ordens | Exports Power BI |
|---|---:|---:|---:|---:|---:|
| `test` | 20,20 MB | 1,81 s | 43/43 | 6 / 24 | 13 |
| `dev` | 92,55 MB | 18,58 s | 43/43 | 90 / 500 | 13 |

O `dev` reconciliou 1.733,672 t boas e 90,419 h produtivas, produzindo TBH sintético global de 19,174 t/h. Esses números são evidências técnicas da simulação, não ganhos reais nem benchmarks universais.

O banco fica em `data/analytics/<profile>/<simulation_run_id>/`; os arquivos para Power BI, em `powerbi/exports/<profile>/<simulation_run_id>/`. Ambos são recriáveis e ignorados pelo Git. Consulte [o modelo analítico](docs/ANALYTICAL_MODEL.md), [o catálogo de KPIs](docs/KPI_CATALOG.md) e [as instruções do Power BI](powerbi/README.md).

## Evidência da Fase 4

| Perfil | Validação DuckDB | Diagnóstico | Snapshots (`pre_order` / rolling / ativo) | Validação de features |
|---|---:|---:|---:|---:|
| `test` | 46/46 | 8/8; 375 linhas | 24 / 480 / 360 | 27/27 |
| `dev` | 46/46 | 8/8; 4.549 linhas | 500 / 10.500 / 5.400 | 27/27 |

No `dev`, o diagnóstico encontrou uma diferença média descritiva de -0,290 t/h após ajuste pelo mix de produto/grau/linha, 3 sinais de controle de TBH e 24 de qualidade. São associações em simulação, não efeitos causais. O target de parada em ativo × janela de duas horas manteve taxa de 13,648%, sem balanceamento artificial.

Consulte [o relatório diagnóstico](docs/DIAGNOSTIC_REPORT.md) e [o contrato congelado de features](docs/FEATURE_CONTRACT.md).

## Evidência da Fase 5

O `mvp` treinou dez tarefas em 211,09 s com baselines, CatBoost, calibração e seis modelos MultiQuantile. A avaliação cronológica final foi executada uma vez e passou 50/50 verificações. A cobertura P10–P90 ficou entre 77,39% e 82,13%; o ECE dos quatro classificadores calibrados ficou entre 0,00053 e 0,01572. A auditoria posterior recuperou 6/6 mecanismos sintéticos.

O resultado de TBH deve ser lido sem seleção favorável: a melhor baseline obteve MAE 2,158 t/h e o CatBoost, 2,137 t/h, melhora relativa de 0,98% <!-- [claim:TBH_RELATIVE_IMPROVEMENT] -->. Portanto, o critério de 5% <!-- [claim:TBH_ENGINEERING_TARGET] --> **não foi atingido**. Consulte [o relatório de modelagem](docs/MODELING_REPORT.md), o [model card do sistema](docs/MODEL_CARD.md) e os [cards consolidados](docs/MODEL_CARDS.md).

## Evidência da Fase 6

O `mvp` executou 20.160 avaliações NSGA-II em três contextos condicionados por produto, grau, linha e faixa de desgaste. Foram publicados 12 cenários (`current`, `conservative`, `balanced` e `productivity`), todos dentro do envelope e das nove restrições duras. As três sondas OOD foram recusadas sem emitir recomendação. A validação passou 14/14 checks e duas reconstruções completas produziram o mesmo hash lógico.

O surrogate auxiliar de `actual_tph`, avaliado somente na janela de calibração, obteve MAE P50 de 0,619 t/h e cobertura P10–P90 de 80,33%. A proxy de TBH combina essa mediana com a probabilidade calibrada de falha de qualidade. Ela não substitui o modelo TBH da Fase 5 e não possui alegação de desempenho no teste final. Consulte o [relatório de otimização](docs/OPTIMIZATION_REPORT.md) e o [contrato de cenários](docs/SCENARIO_CONTRACT.md).

## Evidência da Fase 7

As cinco páginas Streamlit foram abertas por smoke test usando o `mvp`. O teste ponta a
ponta reconstruiu um cenário publicado com os modelos congelados, confirmou 100% das
restrições, aplicou OOD, exigiu aceite humano e leu os exports JSON/CSV. O pacote Power BI
validou 5 dimensões, 8 fatos e os SHA-256 dos 26 arquivos, totalizando 24.482.012 bytes.
Nenhum `.pbix` foi declarado. Consulte o [relatório do produto](docs/PRODUCT_REPORT.md) e
o [pacote Power BI](powerbi/README.md).

## Entrega de portfólio da Fase 8

O [estudo de caso](docs/CASE_STUDY.md), o [post](docs/LINKEDIN_POST.md), o
[carrossel editável](docs/LINKEDIN_CAROUSEL.md), a
[apresentação pronta](docs/SteelFlow_AI_LinkedIn_Carousel.pptx), o
[guia de publicação](docs/LINKEDIN_PUBLICATION_GUIDE.md) e o
[roteiro de demonstração](docs/DEMO_SCRIPT.md) usam somente números ligados a evidências
versionadas. `audit-portfolio` verifica os
ponteiros JSON, a representação publicada, os avisos obrigatórios e expressões proibidas.
A [auditoria causal](docs/CAUSAL_GROUND_TRUTH_AUDIT.md) documenta por que a recuperação
sintética posterior não equivale a causalidade industrial.
O [relatório final de aceite](docs/FINAL_ACCEPTANCE_REPORT.md) reúne a evidência dos 17
critérios e todas as limitações que permanecem abertas.
A [revisão de segurança](docs/SECURITY_REVIEW.md) registra a varredura do conteúdo e do
histórico, a remoção do e-mail pessoal dos commits e o comando preventivo para futuras
publicações.

## Arquitetura implementada até a Fase 8

```text
Versioned YAML
      |
      v
Synthetic generator --> raw Parquet --> curated DuckDB --> analytics / feature snapshots
                                                   |               |
                                                   v               v
                                             Power BI exports   temporal ML
                                                                    |
                                                                    v
                                         calibrated risk + quantiles + SHAP
                                                                    |
                                                                    v
                                         OOD guard + constrained NSGA-II
                                                                    |
                                                                    v
                                                      Streamlit decision support
```

A verdade causal sintética pertence exclusivamente à geração e à auditoria posterior. Os pacotes `features`, `models` e `optimization` não podem importá-la.

## Estrutura

```text
configs/                 configurações versionadas
src/steelflow/           pacote Python e fronteiras do pipeline
sql/                     consultas curated e marts (Fase 3)
app/                     produto Streamlit (Fase 7)
powerbi/                 exports, medidas e tema (Fases 3 e 7)
tests/                   testes unitários, integração e qualidade
docs/                    plano, decisões, riscos e documentação do produto
data/                    dados recriáveis não versionados
artifacts/               manifests e artefatos leves rastreáveis
```

Consulte [o plano de implementação](docs/IMPLEMENTATION_PLAN.md), [a rastreabilidade](docs/REQUIREMENTS_TRACEABILITY.md), [as decisões](docs/DECISION_LOG.md) e [os riscos](docs/RISK_REGISTER.md).

## Licença e aviso

O código é disponibilizado sob a licença MIT. Dados, métricas e cenários produzidos pelo projeto são sintéticos e não representam operação, ganho, ROI ou conformidade de uma fábrica real.
