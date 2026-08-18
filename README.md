# SteelFlow AI

> Protótipo educacional offline, construído exclusivamente com dados sintéticos. Os limites são internos e simulados; o sistema não é validado pela API 5CT, não controla máquinas e não fornece instruções para operação industrial real.

SteelFlow AI é um *decision-support digital twin* simplificado para uma fábrica fictícia de tubos OCTG de aço sem costura. O produto demonstrará como separar efeito de mix, estimar produtividade, qualidade, energia e risco com incerteza e comparar alternativas condicionais sob restrições — sempre com aprovação humana.

**English summary:** SteelFlow AI is an offline, reproducible portfolio prototype built entirely from synthetic data. It will combine temporal machine learning, calibrated uncertainty, explainability and constrained Pareto scenarios. It is not a validated physical digital twin and never controls production equipment.

## Estado atual

As Fases 0–3 estabelecem a fundação, o gerador auditável e a camada analítica:

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

Os perfis `test` e `dev` já foram gerados, curados e validados. A próxima fase aprovada deverá tratar diagnóstico, ajuste de mix e congelamento do contrato de features; ainda não há modelo preditivo ou recomendação.

## Instalação

Python compatível: `>=3.11,<3.15`. A fundação foi verificada no ambiente local indicado no checkpoint. Para as fases de machine learning, a compatibilidade das rodas binárias será reavaliada antes da instalação do extra `all`.

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e ".[data,dev]"
.venv\Scripts\python -m steelflow doctor
.venv\Scripts\python -m pytest
```

### Linux e macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[data,dev]"
.venv/bin/python -m steelflow doctor
.venv/bin/python -m pytest
```

Se `uv` estiver disponível, o bootstrap equivalente é:

```bash
uv venv
uv pip install -e ".[data,dev]"
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
| `make train` | `python -m steelflow train --profile dev` | 5 |
| `make evaluate` | `python -m steelflow evaluate --profile dev` | 5 |
| `make optimize-demo` | `python -m steelflow optimize-demo --profile dev` | 6 |
| `make app` | `python -m steelflow app --profile dev` | 7 |

Os comandos de modelagem, otimização e aplicativo retornam código diferente de zero e informam claramente a fase em que serão implementados.

## Perfis

| Perfil | Período inclusivo | Finalidade | Volume de referência |
|---|---:|---|---:|
| `test` | 2 dias | CI e testes rápidos | 24 ordens / 480 tubos |
| `dev` | 30 dias | desenvolvimento e validação local | 500 ordens / 10.500 tubos |
| `mvp` | 24 meses | demonstração em escala de portfólio | 12.000 ordens / 250.000 tubos |

Os volumes configurados de `test` e `dev` foram materializados. O perfil `mvp` continua sendo apenas uma configuração até a validação de capacidade e autorização específica de execução.

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

## Arquitetura planejada

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

O código é disponibilizado sob a licença MIT. Dados, métricas e cenários produzidos pelo projeto serão sintéticos e não representarão operação, ganho, ROI ou conformidade de uma fábrica real.
