# Contrato de cenários — v1.0.0

## Finalidade

Este contrato define o artefato consumível pela interface da Fase 7. Um cenário é uma comparação estimada em backtest sintético dentro de um contexto operacional fixo. O artefato nunca representa comando de máquina ou aprovação automática.

## Perfis publicados

- `current`: referência imutável; não é recomendação.
- `conservative`: alternativa Pareto que pondera risco, energia, incerteza, distância histórica e magnitude de mudança.
- `balanced`: alternativa mais próxima do ideal normalizado entre todos os objetivos.
- `productivity`: alternativa Pareto com maior proxy de tonelagem boa por hora.

As três alternativas devem ser distintas em parâmetros. Sempre que a resolução dos modelos permitir, a seleção também prioriza resultados preditivos distintos.

## Campos obrigatórios

Cada JSON contém:

- IDs do cenário e do contexto;
- rótulo, estado, escopo sintético e ausência de alegação causal;
- exigência de aprovação humana;
- hash e valores das features fixas;
- exatamente os 11 parâmetros controláveis, com valor atual, valor proposto e unidade;
- produtividade, qualidade, energia, dimensões e parada;
- intervalos P10/P50/P90 quando disponíveis;
- distância histórica, limiar e estado `in_distribution`;
- nove restrições com observado, máximo, margem e estado;
- restrições ativas e três maiores alterações controláveis.

Para ser publicado, `hard_constraints_pass` e `ood_assessment.in_distribution` devem ser verdadeiros. A interface não deve permitir confirmar uma alternativa sem ação humana explícita.

## Recusa OOD

Uma recusa possui `status: REFUSED_OOD`, `recommendation_issued: false` e `engineering_validation_required: true`. Ela apresenta apenas o diagnóstico necessário para explicar a violação. Nenhum conjunto OOD pode ser reaproveitado como recomendação.

## Semântica de incerteza

P10/P50/P90 são quantis preditivos dos modelos sintéticos, não limites físicos de segurança. Largura excessiva reprova o cenário. A probabilidade de falha é calibrada, enquanto a proxy de TBH é derivada do P50 do surrogate de `actual_tph` e da probabilidade de qualidade.

## Invariantes de contexto

Produto, grau, linha, turno, estado de desgaste/manutenção e mediadores observados não podem mudar entre alternativas. As estimativas de parada são invariantes no contexto porque o modelo de ativo não recebe controles de laminação. A interface deve mostrar essa condição e não sugerir que o otimizador reduziu diretamente o risco de parada.
