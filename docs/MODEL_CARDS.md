# Model cards — visão consolidada

## Escopo comum

Os dez modelos usam apenas features públicas point-in-time. Treino, tuning, calibração e teste
final são cronologicamente distintos; preprocessadores de Ridge, logística e Random Forest são
ajustados dentro do treino. CatBoost usa early stopping em tuning. Classificadores recebem
calibração sigmoid em janela exclusiva. O teste final foi avaliado uma única vez.

| Modelo | Snapshot | Tipo | Incerteza / calibração | Uso pretendido |
|---|---|---|---|---|
| TBH | Pré-ordem | Regressão | P10/P50/P90 | estimativa sintética antecipada de throughput bom |
| Energia | Rolling | Regressão | P10/P50/P90 | intensidade por tonelada aprovada quando definida |
| Desvio de diâmetro | Rolling | Regressão | P10/P50/P90 | desvio dimensional sintético |
| Excentricidade | Rolling | Regressão | P10/P50/P90 | desvio dimensional sintético |
| Ovalização | Rolling | Regressão | P10/P50/P90 | desvio dimensional sintético |
| Duração de parada | Ativo × 2 h | Regressão condicional | P10/P50/P90 | duração somente se a parada ocorrer |
| Falha de qualidade | Rolling | Classificação | Platt/sigmoid | ranking de risco sintético |
| Retrabalho | Rolling | Classificação | Platt/sigmoid | ranking de risco sintético |
| Refugo | Rolling | Classificação | Platt/sigmoid | evento raro; não usar limiar 0,5 como política |
| Ocorrência de parada | Ativo × 2 h | Classificação | Platt/sigmoid | evento futuro em janela de duas horas |

## Evidência e monitoramento necessário

O relatório de modelagem contém métricas finais, estabilidade, cobertura e orçamento de alerta.
Cada run local também gera um card individual, previsões, métricas segmentadas e TreeSHAP. Em
qualquer implantação hipotética seriam necessários validação externa, intervalos de confiança,
monitoramento de drift/calibração, revisão de thresholds, avaliação de equidade operacional e
aprovação humana.

## Uso proibido

Os modelos não são válidos para operação industrial, certificação, conformidade API 5CT,
comando de equipamentos ou alegação de ganho real. TreeSHAP não transforma associação em causa.
