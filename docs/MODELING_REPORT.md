# Relatório de modelagem temporal

> Todos os resultados deste documento vêm de uma simulação offline. Não são resultados de
> uma planta real, validação normativa, ganho operacional ou instrução de controle.

## Linhagem e desenho experimental

O perfil `mvp` materializou 12.594.517 registros públicos entre 2024-01-01 e 2025-12-31.
O run de modelagem usa `simulation_run_id=sim-mvp-v0.1.0-740ec922f950`, contrato de features
`1.0.0` (`4b44cb01…`) e contrato de modelagem `1.0.0` (`4330948e…`). O treino levou 211,09 s
no ambiente local com Python 3.14.6, CatBoost 1.2.10 e scikit-learn 1.9.0.

Cada snapshot foi dividido cronologicamente em treino (55%), tuning (20%), calibração (10%)
e teste final (15%). Rótulos que só ficaram disponíveis depois do início da janela seguinte
foram embargados: 37 ordens, 75 tubos e 45 janelas de ativo. O teste final não participou de
fit, early stopping, seleção de configuração ou calibração. A avaliação final foi executada
uma vez; chamadas posteriores reutilizam o manifest.

| Snapshot | Treino | Tuning | Calibração | Teste final | Embargo |
|---|---:|---:|---:|---:|---:|
| Pré-ordem | 6.589 | 2.385 | 1.189 | 1.800 | 37 |
| Rolling por tubo | 137.469 | 49.969 | 24.987 | 37.500 | 75 |
| Ativo × 2 h | 72.345 | 26.310 | 13.140 | 19.740 | 45 |

Três backtests expansivos ficaram inteiramente antes de calibração/teste. O MAE de TBH variou
de 2,065 a 2,178 t/h; PR-AUC variou de 0,382 a 0,402 para falha de qualidade e de 0,194 a
0,231 para ocorrência de parada.

## Modelos comparados

Regressões usam mediana global, mediana condicionada por produto/grau/linha quando disponível,
Ridge regularizado, Random Forest e CatBoostRegressor. Classificações usam prior global, taxa
condicionada suavizada, regressão logística regularizada, Random Forest e CatBoostClassifier.
Pesos de classe são aplicados apenas durante o fit; a população e as prevalências nunca são
reamostradas. Os classificadores CatBoost são calibrados por
`CalibratedClassifierCV(method="sigmoid")` exclusivamente na janela de calibração.

Seis alvos contínuos possuem CatBoost `MultiQuantile` para P10/P50/P90. A duração de parada é
condicional à ocorrência positiva. Energia por tonelada boa é avaliada somente quando o alvo é
definido; valores sem tonelada aprovada não são imputados como zero.

## Resultado no teste cronológico final

| Tarefa | Métrica principal CatBoost | Resultado adicional |
|---|---:|---:|
| TBH | MAE 2,137 t/h; RMSE 2,851; R² 0,439 | cobertura 77,39% |
| Energia por tonelada boa | MAE 10,417 kWh/t; R² 0,520 | cobertura 82,13% |
| Desvio de diâmetro externo | MAE 0,264 mm; R² -0,001 | cobertura 78,50% |
| Excentricidade de parede | MAE 0,145 p.p.; R² 0,930 | cobertura 79,89% |
| Ovalização | MAE 0,133 p.p.; R² 0,402 | cobertura 79,63% |
| Duração condicional de parada | MAE 15,133 min; R² -0,047 | cobertura 77,58% |
| Falha de qualidade | PR-AUC 0,417; ROC-AUC 0,726 | Brier 0,112; ECE 0,0157 |
| Retrabalho | PR-AUC 0,407; ROC-AUC 0,729 | Brier 0,107; ECE 0,0150 |
| Refugo | PR-AUC 0,0136; ROC-AUC 0,620 | Brier 0,00848; ECE 0,00053 |
| Ocorrência de parada | PR-AUC 0,255; ROC-AUC 0,673 | Brier 0,133; ECE 0,00229 |

O objetivo de engenharia era reduzir o MAE de TBH em pelo menos 5% contra a baseline mais
forte. A mediana condicionada obteve 2,158 t/h e o CatBoost 2,137 t/h: melhora relativa de
apenas **0,98%**. O critério não foi atingido. A pequena diferença e a variação dos backtests
não sustentam alegação de superioridade relevante.

Nos eventos raros, o limiar fixo 0,5 não é uma política operacional adequada: refugo e parada
ficaram sem positivos nesse limiar. Por isso o pacote registra curvas/ranking e recall sob
orçamento de alerta. Com orçamento de 10%, o recall foi 30,1% para falha, 31,1% para retrabalho,
20,9% para refugo e 16,8% para parada. Nenhum desses limites foi validado para uso real.

## Explicabilidade e segmentos

Cada uma das dez tarefas possui TreeSHAP global, por produto/grau/linha quando aplicável e dez
cenários locais. Há 218 recortes de métricas por produto, grau, linha, mês e faixa de desgaste,
respeitando suporte mínimo de 100 linhas. SHAP descreve contribuição preditiva do modelo base;
não identifica causalidade.

O benchmark local de inferência, após warm-up e sem I/O, usou cinco repetições de lotes com
1.000 linhas. As medianas ficaram entre 2,95 e 4,40 ms por lote (0,0029–0,0044 ms por linha).
São medidas desta máquina e destes artefatos, não SLA.

## Auditoria causal posterior

Somente depois do congelamento dos modelos e da avaliação, o módulo isolado de auditoria leu
a verdade causal sintética. O critério combinou direção de associação por Spearman (|ρ| ≥ 0,08)
com ao menos uma feature pública esperada entre as 20 maiores contribuições TreeSHAP. Foram
recuperados 6/6 mecanismos testados: complexidade de mix, uniformidade térmica × desgaste,
velocidade × janela térmica, resposta térmica por grau/espessura, horas acumuladas × degradação
de sensor e drift temporal. Isso valida a recuperabilidade do gerador, não causalidade real.

## Limitações e decisão

- Dois alvos contínuos tiveram R² ligeiramente negativo; o modelo não agrega valor sobre uma
  constante para explicar variância nesses recortes, embora ainda forneça um benchmark.
- PR-AUC de refugo permanece baixo apesar da calibração; suporte e separação são limitados.
- Calibração e cobertura podem degradar fora do período sintético observado.
- Não há otimização, recomendação, OOD guard ou controle de máquina nesta fase.
- A próxima fase deve tratar modelos como superfícies condicionais com incerteza e pode recusar
  cenários; não deve esconder o não atingimento do objetivo de TBH.

Detalhes por tarefa estão em [MODEL_CARDS.md](MODEL_CARDS.md). Os artefatos completos são
recriados localmente em `data/model_outputs/` e não são versionados; o resumo auditável leve
está em `artifacts/samples/phase_5_modeling_summaries.json`.
