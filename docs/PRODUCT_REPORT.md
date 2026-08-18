# Relatório do produto — Fase 7

## Resultado

O SteelFlow AI possui uma aplicação Streamlit offline de cinco páginas, conectada ao
DuckDB e aos artefatos congelados de modelagem, explicabilidade e otimização do perfil
`mvp`. Todo conteúdo é sintético e interno; o produto não valida API 5CT, não estima ganho
real e não envia comando para máquinas.

## Páginas

1. **Executive Overview:** TBH, FPY, OEE, energia, parada, toneladas boas, tendência,
   comparação entre linhas, ajuste de mix, Pareto e alertas estatísticos.
2. **Root Cause & Explainability:** TreeSHAP global, por segmento e local, interação de
   processo e associações estratificadas, sempre rotuladas como não causais.
3. **Forecast & Risk:** P10/P50/P90, riscos calibrados, distância histórica, restrições e
   comparação honesta com baselines no mesmo teste final.
4. **Scenario Lab:** contexto fixo, somente 11 controles elegíveis, recálculo pelos modelos
   congelados, OOD, nove restrições duras, aceite humano e exportação JSON/CSV.
5. **Model Reliability:** cobertura, calibração, métricas temporais/segmentadas, latência,
   OOD, meta TBH não atingida e model cards.

## Execução

```powershell
.venv\Scripts\python -m pip install -e ".[all]"
.venv\Scripts\python -m steelflow app --profile mvp --check
.venv\Scripts\python -m steelflow app --profile mvp
```

O app consulta agregados pequenos no DuckDB e usa cache. As 250 mil linhas do snapshot e
os modelos são carregados somente quando o usuário abre/avalia um contexto no Scenario
Lab. Se faltarem artefatos, a interface mostra comandos de recuperação sem traceback.

## Segurança de decisão

- contexto, desgaste, sensores e mediadores não são controles editáveis;
- combinação fora do envelope/OOD é recusada antes de emitir recomendação;
- cenário inseguro não pode receber aprovação;
- aprovação exige checkbox explícito e registra ID/UTC local à sessão;
- JSON e CSV preservam parâmetros, previsões, OOD e estado de revisão;
- `machine_command=false` permanece invariável.

## Power BI

O hand-off contém 5 dimensões, 8 fatos, CSV/Parquet, DAX, Power Query, relacionamentos,
tema, wireframe e checklist. O validador recalculou os SHA-256 dos 26 arquivos (24.482.012
bytes) sem divergências. Nenhum `.pbix` é alegado porque o Power BI Desktop não estava
disponível para validação.

## Evidência automatizada

- smoke test das cinco páginas com artefatos `mvp`;
- inicialização orientativa com artefatos ausentes;
- reconstrução ponta a ponta de cenário pelos modelos congelados;
- recusa sem confirmação e proibição de aprovar cenário recusado;
- leitura dos exports JSON/CSV;
- validação integral do pacote Power BI.

## Limitações abertas

- tudo é sintético, offline e sem validação externa/prospectiva;
- a meta TBH de 5% não foi atingida: melhora final de 0,98%;
- a proxy de TBH do cenário não substitui o modelo TBH oficial;
- risco de parada é invariável aos controles de laminação do mesmo contexto;
- SHAP e associações explicam o modelo/dados, não efeitos de intervenção;
- o Power BI é descritivo; risco, OOD e cenários interativos pertencem ao Streamlit.

## Screenshots reais

Os arquivos abaixo foram capturados do app `mvp` após o smoke test visual e não contêm
dados reais:

- [Executive Overview](images/phase7/executive-overview.png)
- [Root Cause & Explainability](images/phase7/root-cause-explainability.png)
- [Forecast & Risk](images/phase7/forecast-risk.png)
- [Scenario Lab](images/phase7/scenario-lab.png)
- [Model Reliability](images/phase7/model-reliability.png)
