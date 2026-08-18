# Relatório de otimização — Fase 6

## Escopo e resultado

A Fase 6 implementa comparação de cenários multiobjetivo exclusivamente sobre dados e modelos sintéticos congelados. O pacote `mvp` executou 20.160 avaliações com NSGA-II (pymoo 0.6.2), publicou quatro cenários para cada uma das três linhas e passou 14/14 verificações. Os 12 cenários publicados satisfazem 100% das restrições duras; três sondas fora da distribuição foram recusadas sem recomendação.

Os resultados devem ser chamados de **cenários estimados em backtest sintético**. Não são contrafactuais causais, receitas operacionais, validação metalúrgica nem controle de máquina. Toda alternativa exige aprovação humana e validação de engenharia antes de qualquer transposição para ambiente real.

## Fronteira de decisão

Somente as 11 features marcadas simultaneamente como `CONTROLLABLE` e `recommendable: true` no snapshot `in_process_rolling` podem variar:

- temperaturas das três zonas de reaquecimento, tempo de encharque e temperatura de saída;
- velocidade e abertura de laminação, posição do mandril e taxa de redução;
- velocidade de saída e vazão de lubrificação.

Produto, grau, linha, turno, desgaste, manutenção, degradação de sensor e todas as features mediadoras/observadas permanecem fixos. Os controles de tratamento térmico não pertencem ao snapshot congelado e, portanto, não são otimizados. O produto exato condiciona implicitamente a família dimensional/espessura e preserva compatibilidade de receita neste protótipo.

## Envelope histórico e OOD

Cada contexto usa apenas a janela temporal `train`. O suporte é procurado na seguinte hierarquia:

1. produto × grau × linha × faixa de desgaste;
2. produto × grau × linha;
3. produto × grau;
4. grau × linha.

São exigidas ao menos 150 observações. Os limites marginais usam P02–P98, intersectados com limites internos simulados e com a mudança máxima permitida em relação ao cenário atual. A distância conjunta usa kNN (`k=5`) no espaço normalizado; o limiar é o P95 das distâncias do suporte.

Uma alternativa só pode ser publicada quando permanece dentro de todos os limites marginais e sua razão `distância / limiar` é menor ou igual a 1. Sondas que violam essa regra recebem `REFUSED_OOD`, nenhuma recomendação e uma solicitação explícita de validação de engenharia.

## Modelos e produtividade

Os modelos congelados da Fase 5 fornecem risco calibrado de falha, energia e resultados dimensionais com quantis. Como o modelo TBH original usa o snapshot `pre_order` e não possui os controles de laminação, não seria legítimo usá-lo como função responsiva.

Foi treinado um surrogate auxiliar de `actual_tph` no snapshot de laminação, somente em `train`, com `tuning` para early stopping. A avaliação foi feita exclusivamente em `calibration`; o teste final não foi reaberto:

| Métrica de calibração | Resultado |
|---|---:|
| MAE do ponto | 0,623 t/h |
| MAE P50 | 0,619 t/h |
| R² do ponto | 0,8887 |
| Cobertura P10–P90 | 80,33% |
| Largura média P10–P90 | 2,016 t/h |

A proxy de TBH estimado é `actual_tph P50 × (1 − probabilidade calibrada de falha)`, equivalente a uma estimativa de tonelagem boa por hora. Não é o TBH oficial da Fase 5, não possui alegação sobre o teste final e não transforma associação preditiva em efeito causal.

Os modelos de parada usam o snapshot de ativo e não possuem os controles de laminação. Assim, risco e duração de parada são mantidos como objetivos e restrições, mas são invariantes entre alternativas do mesmo contexto. O artefato sinaliza essa limitação em cada cenário.

## Objetivos e restrições

O NSGA-II minimiza seis funções:

1. negativo da proxy de TBH estimado;
2. probabilidade calibrada de falha de qualidade;
3. energia P50 por tonelada boa;
4. probabilidade de parada;
5. duração esperada de parada;
6. magnitude normalizada da intervenção.

As nove restrições duras cobrem distância histórica, risco de qualidade, risco/duração de parada, largura dos intervalos de produtividade e energia, desvio de diâmetro externo, excentricidade e ovalização. Limites condicionais, mudança máxima e compatibilidade de contexto são impostos pelo espaço de decisão antes dessas nove verificações.

## Demonstração reproduzível

| Contexto | Linha | Suporte condicional | Pontos Pareto viáveis |
|---|---|---:|---:|
| `context-01-line_01` | LINE_01 | 627 | 42 |
| `context-02-line_02` | LINE_02 | 778 | 96 |
| `context-03-line_03` | LINE_03 | 844 | 96 |

Cada contexto publica `current`, `conservative`, `balanced` e `productivity`, com P10/P50/P90, restrições ativas, distância histórica, maiores alterações controláveis e contexto fixo verificável por hash. Duas reconstruções completas com a mesma configuração e semente produziram o hash lógico `0bacb0178932cd55c12e6947744cad3281218cf2d17d2e057c383774525eae92`.

## Limitações abertas

- Todos os dados, limites e resultados são sintéticos.
- Modelos de árvore produzem regiões de previsão constantes; o objetivo de mínima intervenção preserva compromissos úteis, mas não cria resolução ausente nos modelos.
- A estimativa de produtividade ainda requer validação externa e teste prospectivo antes de uso real.
- Compatibilidade dimensional é representada pelo produto congelado, não por uma regra metalúrgica certificada.
- Parada é invariante aos controles de laminação na versão atual.
- A Fase 7 integrou cenários à interface com controles contratados, recálculo pelos modelos
  congelados, confirmação humana e exportação auditável. O Power BI permanece descritivo;
  risco, OOD e cenários interativos pertencem ao app para preservar a linhagem congelada.
