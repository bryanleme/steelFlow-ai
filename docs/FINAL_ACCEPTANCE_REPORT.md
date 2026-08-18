# Relatório final de aceite — SteelFlow AI

## Parecer

**APROVADO — 17/17 critérios atendidos.** O MVP está concluído dentro do escopo de
protótipo educacional offline, feito com dados 100% sintéticos, sem validação API 5CT e
sem controle automático de máquina.

A instalação limpa foi executada em um novo ambiente virtual. O pacote e todas as
dependências `.[all]` foram instalados a partir do `pyproject.toml`; uma raiz de projeto
isolada, sem dados anteriores, regenerou o perfil `dev`, reproduziu o hash lógico de
referência e reconstruiu as camadas analítica, diagnóstica e de features.

## Matriz dos 17 critérios

| # | Critério | Estado | Evidência |
|---:|---|---|---|
| 1 | Instalação limpa reproduz `dev` | PASS | novo venv; wheel local + `.[all]`; 529.014 linhas em raiz isolada |
| 2 | Mesma semente recria dados lógicos e IDs | PASS | run `sim-dev-v0.1.0-36068c9e490c`; SHA-256 lógico `ee400a163caf…` igual à referência |
| 3 | Testes unitários, integração e qualidade | PASS | 69 testes; zero falhas; Ruff PASS |
| 4 | Integridade referencial e contrato | PASS | raw 83/83 e analytics 46/46; contratos em `DATA_CARD.md` e `ANALYTICAL_MODEL.md` |
| 5 | Snapshots sem vazamento | PASS | features 27/27; `X`, índice e `y` separados; `fold_train_only` |
| 6 | Baselines e modelos no mesmo teste | PASS | manifest final único, janelas cronológicas e relatório de modelagem |
| 7 | Calibração de probabilidades | PASS | Platt/sigmoid em janela exclusiva; Brier, ECE e curvas reportados |
| 8 | Cobertura P10/P50/P90 | PASS | seis regressões; cobertura final por tarefa e segmento |
| 9 | Métricas globais e segmentadas | PASS | 218 linhas de recortes segmentados e model cards individuais |
| 10 | 100% das restrições duras | PASS | 12/12 cenários publicados passaram nove restrições |
| 11 | OOD bloqueado | PASS | 3/3 sondas recusadas sem recomendação |
| 12 | Ao menos quatro mecanismos recuperados | PASS | auditoria posterior recuperou 6/6, sem verdade causal no treino |
| 13 | Streamlit e fluxo de cenário | PASS | cinco page smokes e fluxo com modelo congelado, OOD, aceite e exportação |
| 14 | Power BI verificável | PASS | 13 tabelas, 26 arquivos, hashes, DAX, Power Query, tema e wireframe |
| 15 | Números de case/LinkedIn rastreáveis | PASS | 12 claims, 86 checks documentais/numéricos, três fontes versionadas |
| 16 | Limites e ausência de automação explícitos | PASS | 48 checks de linguagem; avisos no app, README e quatro peças publicáveis |
| 17 | README executável sem conhecimento implícito | PASS | Windows, Linux/macOS, venv/pip/uv, CLI completa e recuperação de artefatos |

## Validação final

| Verificação | Resultado |
|---|---|
| Instalação `.[all]` em ambiente novo | PASS |
| `doctor --json` e três perfis de configuração | PASS |
| Geração e validação raw `dev` isoladas | 529.014 linhas; 83/83 |
| DuckDB `dev` isolado | 46/46 |
| Diagnóstico `dev` isolado | 8/8 |
| Features `dev` isoladas | 27/27 |
| Suíte completa no ambiente limpo | 69 passed |
| Ruff | PASS |
| Auditoria do portfólio | 12 claims; 86 checks de claim; 48 de linguagem; PASS |
| Checagem do app `mvp` | PASS |
| Checagem Power BI | 13 tabelas; 26 arquivos; 24.482.012 bytes; PASS |

O resumo legível por máquina está em
`artifacts/samples/phase_8_acceptance_summary.json`.

## Pendências e limitações reais

Não há pendência bloqueante dentro do MVP aprovado. Permanecem limitações explícitas:

- **sem validação industrial:** dados, limites, relações e métricas são sintéticos;
- **meta de TBH não atingida:** melhora de 0,98% contra meta de 5% no backtest;
- **sem `.pbix` validado:** Power BI Desktop não estava disponível; o pacote textual e
  os exports foram verificados, mas nenhum binário é declarado;
- **warnings externos:** quatro avisos de depreciação surgem na desserialização
  joblib/NumPy; não são falhas do projeto, mas devem ser reavaliados em upgrades;
- **sem comando de máquina:** cenários exigem revisão humana e exportam somente JSON/CSV;
- **sem inferência causal industrial:** SHAP, diagnóstico e otimização descrevem
  associações e estimativas condicionais na simulação.

## Próximos passos fora do escopo do MVP

Somente com nova autorização: revisão por engenharia de processo, dados industriais
governados, mapeamento normativo aplicável, validação externa prospectiva, modo sombra,
monitoramento contínuo, segurança, gestão de mudanças e aprovação formal. Nenhum desses
passos deve reutilizar automaticamente os limites sintéticos atuais.
