# SteelFlow AI

> Laboratório offline de análise de cenários industriais, construído com dados 100% sintéticos. O sistema não controla máquinas, não foi validado para operação industrial real e não demonstra causalidade industrial.

SteelFlow AI é um projeto de engenharia de dados e machine learning para responder a uma pergunta prática:

**se diferentes parâmetros de processo forem combinados, quais resultados são mais prováveis — e quão incerta é essa estimativa?**

O projeto nasceu de um problema comum em ambientes industriais: existem dados, mas, quando um defeito aparece, o ajuste de processo muitas vezes volta para a tentativa e erro. O SteelFlow AI cria um ambiente reproduzível para comparar hipóteses de parâmetros antes de qualquer decisão humana.

## O que o projeto faz

Para um contexto operacional fixo — produto, grau, linha, turno e condição do ativo — o laboratório permite alterar 11 parâmetros controláveis e recalcular um cenário.

Cada hipótese retorna:

- probabilidade calibrada de falha de qualidade e FPY estimado;
- produtividade e energia com faixas P10, P50 e P90;
- resultados dimensionais estimados;
- probabilidade e duração esperada de parada para o contexto;
- distância em relação ao histórico e estado dentro/fora da distribuição;
- resultado das nove restrições obrigatórias;
- indicação de cenário elegível para revisão humana ou recusado.

O sistema também compara alternativas `current`, `conservative`, `balanced` e `productivity` selecionadas por otimização multiobjetivo NSGA-II.

### Isso equivale a testar hipóteses?

Sim, no sentido **preditivo**: o projeto executa análises *what-if* e estima o comportamento esperado dos modelos para diferentes combinações de parâmetros.

Não, no sentido **causal ou físico**: uma previsão do modelo não prova que a alteração causará o mesmo efeito em uma máquina real. Todo resultado continua sujeito à validação de engenharia e à aprovação humana.

## Evidências do MVP

- 12.594.517 registros públicos sintéticos <!-- [claim:MVP_PUBLIC_ROWS] -->;
- 20.160 avaliações do otimizador em três contextos;
- 12 cenários publicados, todos dentro do envelope histórico e das nove restrições;
- três sondas fora da distribuição recusadas sem recomendação;
- cobertura P10–P90 entre 77,39% e 82,13% nos seis alvos contínuos;
- cinco páginas Streamlit e 13 tabelas verificadas para Power BI.

Um resultado foi mantido de forma explícita: a meta de melhorar o MAE de TBH em 5% <!-- [claim:TBH_ENGINEERING_TARGET] --> não foi atingida. A melhora observada foi 0,98% <!-- [claim:TBH_RELATIVE_IMPROVEMENT] -->. O projeto trata transparência sobre limites como parte do resultado.

## Limites importantes

- Os dados e mecanismos são inteiramente sintéticos.
- As saídas são estimativas de modelos, não contrafactuais causais.
- P10/P50/P90 são quantis preditivos, não limites físicos de segurança.
- O risco de parada é uma estimativa do contexto e permanece invariável entre ajustes de laminação na versão atual.
- Nenhuma tela envia comando para equipamentos.
- O protótipo não valida conformidade API 5CT, ganho financeiro ou desempenho de uma fábrica real.

## Aplicação

A interface Streamlit organiza a análise em cinco páginas:

1. **Executive Overview** — KPIs, tendências e Pareto de perdas.
2. **Root Cause Explainability** — fatores associados às previsões e análises SHAP.
3. **Forecast Risk** — probabilidades, faixas P10/P50/P90 e riscos previstos.
4. **Scenario Lab** — comparação de parâmetros, cenários e restrições.
5. **Model Reliability** — métricas, calibração, cobertura e limitações dos modelos.

O **Scenario Lab** é a página principal para testar hipóteses e comparar alternativas.

## Arquitetura

```text
Configuração versionada
        |
        v
Gerador sintético -> Parquet -> DuckDB -> analytics / feature snapshots
                                         |                 |
                                         v                 v
                                  Power BI exports     ML temporal
                                                               |
                                                               v
                                      probabilidades + quantis + SHAP
                                                               |
                                                               v
                                      OOD + restrições + NSGA-II
                                                               |
                                                               v
                                             Streamlit para decisão humana
```

A verdade causal usada pelo gerador fica isolada dos pacotes de features, modelos e otimização.

## Como executar

Requisito: Python `>=3.11,<3.15`.

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e ".[all]"
.venv\Scripts\python -m steelflow doctor
.venv\Scripts\python -m steelflow app --profile mvp
```

### Linux e macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[all]"
.venv/bin/python -m steelflow doctor
.venv/bin/python -m steelflow app --profile mvp
```

A aplicação abre em `http://127.0.0.1:8501`. Se algum artefato estiver ausente, a própria tela mostra os comandos necessários para reconstruí-lo.

## Reproduzir o pipeline

```bash
python -m steelflow generate --profile mvp
python -m steelflow validate-data --profile mvp
python -m steelflow build-db --profile mvp
python -m steelflow diagnose --profile mvp
python -m steelflow build-features --profile mvp
python -m steelflow train --profile mvp
python -m steelflow evaluate --profile mvp
python -m steelflow optimize-demo --profile mvp
python -m steelflow audit-portfolio
python -m pytest
python -m ruff check .
```

## Estrutura do repositório

```text
configs/          configurações e contratos versionados
src/steelflow/    pipeline, modelos, otimização e produto
sql/              transformação analítica e marts
app/              aplicação Streamlit
powerbi/          modelo, medidas e instruções para Power BI
tests/            testes unitários, de integração e qualidade
docs/             relatórios, contratos, segurança e materiais de portfólio
data/             dados recriáveis e não versionados
artifacts/        manifests e evidências leves versionadas
```

Documentação principal:

- [Contrato de cenários](docs/SCENARIO_CONTRACT.md)
- [Relatório de otimização](docs/OPTIMIZATION_REPORT.md)
- [Model card](docs/MODEL_CARD.md)
- [Relatório do produto](docs/PRODUCT_REPORT.md)
- [Revisão de segurança](docs/SECURITY_REVIEW.md)

## Segurança e licença

Antes de publicar alterações, execute:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/security_audit.ps1 -History
```

O código é disponibilizado sob licença MIT. Dados, métricas e cenários deste repositório são sintéticos e não representam operação, ganho, ROI ou conformidade de uma fábrica real.
