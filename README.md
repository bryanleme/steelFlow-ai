# SteelFlow AI

> Protótipo educacional offline, construído exclusivamente com dados sintéticos. Os limites são internos e simulados; o sistema não é validado pela API 5CT, não controla máquinas e não fornece instruções para operação industrial real.

SteelFlow AI é um *decision-support digital twin* simplificado para uma fábrica fictícia de tubos OCTG de aço sem costura. O produto demonstrará como separar efeito de mix, estimar produtividade, qualidade, energia e risco com incerteza e comparar alternativas condicionais sob restrições — sempre com aprovação humana.

**English summary:** SteelFlow AI is an offline, reproducible portfolio prototype built entirely from synthetic data. It will combine temporal machine learning, calibrated uncertainty, explainability and constrained Pareto scenarios. It is not a validated physical digital twin and never controls production equipment.

## Estado atual

As Fases 0 e 1 estabelecem a fundação executável:

- configuração YAML tipada e estrita para os perfis `test`, `dev` e `mvp`;
- CLI instalável com diagnóstico, validação e hash estável das configurações;
- logging estruturado;
- estrutura modular para geração, validação, curadoria, features, modelos e otimização;
- testes unitários e de integração da fundação;
- plano rastreável, decisões e riscos documentados.

O gerador completo começa apenas na Fase 2. Os comandos futuros já são reservados na CLI, mas falham explicitamente até sua fase de implementação.

## Instalação

Python compatível: `>=3.11,<3.15`. A fundação foi verificada no ambiente local indicado no checkpoint. Para as fases de machine learning, a compatibilidade das rodas binárias será reavaliada antes da instalação do extra `all`.

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m steelflow doctor
.venv\Scripts\python -m pytest
```

### Linux e macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m steelflow doctor
.venv/bin/python -m pytest
```

Se `uv` estiver disponível, o bootstrap equivalente é:

```bash
uv venv
uv pip install -e ".[dev]"
uv run steelflow doctor
uv run pytest
```

## Comandos da fundação

```bash
python -m steelflow --help
python -m steelflow validate-config --all
python -m steelflow config-hash --profile dev
python -m steelflow doctor --json
python -m pytest
python -m ruff check .
```

Quando `make` estiver instalado, `make setup`, `make validate-config`, `make doctor` e `make test` são atalhos. No Windows sem `make`, use os comandos Python acima.

## Comandos de produto e disponibilidade

| Atalho | Comando Python equivalente | Fase de implementação |
|---|---|---:|
| `make generate-dev` | `python -m steelflow generate --profile dev` | 2 |
| `make validate-data` | `python -m steelflow validate-data --profile dev` | 2 |
| `make build-db` | `python -m steelflow build-db --profile dev` | 3 |
| `make train` | `python -m steelflow train --profile dev` | 5 |
| `make evaluate` | `python -m steelflow evaluate --profile dev` | 5 |
| `make optimize-demo` | `python -m steelflow optimize-demo --profile dev` | 6 |
| `make app` | `python -m steelflow app --profile dev` | 7 |

Antes da fase correspondente, cada comando retorna código diferente de zero e informa claramente que ainda não foi implementado.

## Perfis

| Perfil | Período inclusivo | Finalidade | Volume de referência |
|---|---:|---|---:|
| `test` | 2 dias | CI e testes rápidos | 24 ordens / 480 tubos |
| `dev` | 30 dias | desenvolvimento e validação local | 500 ordens / 10.500 tubos |
| `mvp` | 24 meses | demonstração em escala de portfólio | 12.000 ordens / 250.000 tubos |

Os números acima são volumes solicitados em configuração, não resultados já gerados. Nenhuma base sintética foi produzida na Fase 1.

## Arquitetura planejada

```text
Versioned YAML
      |
      v
Synthetic generator --> raw Parquet --> curated DuckDB --> analytics / features
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
