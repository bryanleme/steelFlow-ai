# Relatório diagnóstico sintético — Fase 4

> Análise retrospectiva de uma simulação offline. Os resultados abaixo são associações descritivas, não causalidade industrial demonstrada, ganho realizado ou evidência de uma fábrica real.

## Método reproduzível

O comando `python -m steelflow diagnose --profile dev` exporta sete tabelas em CSV e Parquet, acompanhadas por manifest, contagens e SHA-256:

| Tema | Objeto | Método |
|---|---|---|
| Tendência | `diagnostic_daily_trend` | TBH, FPY, OEE, energia e mudanças entre janelas data × linha × turno |
| Mix | `diagnostic_mix_adjustment` | TBH esperado pela mediana produto × grau × linha, ponderada pelas horas produtivas do mix observado |
| Pareto | `mart_loss_pareto` | retrabalho, refugo e impacto sintético de parada em toneladas equivalentes |
| Controle TBH | `diagnostic_spc_tbh` | centro e limites de três sigmas por linha, estimados nos primeiros 30% das datas |
| Controle de qualidade | `diagnostic_spc_quality` | centro e limites de três sigmas por linha e característica |
| Interações | `diagnostic_process_interactions` | células produto × grau × linha × tercil de velocidade × tercil de uniformidade |
| Associações | `diagnostic_segment_associations` | correlações segmentadas entre processo, TBH e excentricidade |

Limites de controle só são chamados de confiáveis quando a linha/segmento possui pelo menos cinco observações de baseline. Um sinal de controle não é automaticamente falha de especificação; limites de qualidade e processo continuam internos e simulados.

## Evidência do perfil `dev`

O perfil de 30 dias produziu 4.549 linhas diagnósticas e passou em 8/8 verificações. A leitura abaixo é descritiva:

- TBH global sintético: 19,173687 t/h; FPY: 0,860762.
- Inclinação linear diária do TBH: -0,041453 t/h por dia no período simulado. Não foi aplicado teste causal ou atribuição de causa.
- A diferença média não ponderada entre TBH observado e TBH esperado pelo mix foi -0,289542 t/h nas 90 células linha × data; o maior desvio absoluto foi 3,357837 t/h.
- Parada não planejada foi a maior categoria do Pareto, com 6.345,926270 toneladas equivalentes de impacto sintético. Essa estimativa pode exceder a produção física porque representa impacto potencial agregado do gerador, não massa real perdida.
- Foram marcados 3 sinais de controle de TBH em 90 janelas com limites suportados e 24 sinais de qualidade em 2.826 células suportadas. Sinais pedem investigação; não comprovam causa nem não conformidade normativa.
- A maior amplitude de TBH entre células de interação foi 8,078230 t/h para `OCTG_10` × `L80` × `LINE_01`. O contraste combina velocidade e uniformidade em tercis e pode refletir confusão residual, suporte desigual ou não linearidade.

## Uso correto

As tabelas servem para priorizar perguntas, segmentos e gráficos da futura interface. O baseline de mix usa todo o período e, por isso, é estritamente diagnóstico: ele não entra nas matrizes de features nem no teste futuro. Nenhum ranking de operador é produzido; turno é somente contexto de calendário.

O perfil `test`, com apenas dois dias, verifica execução e contratos. Sua inclinação e seus limites de controle não devem ser interpretados analiticamente, pois não há suporte temporal suficiente.
