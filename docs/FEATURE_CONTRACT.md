# Contrato de features v1.0.0

O contrato congelado está em `configs/feature_contract_v1.yaml` e possui SHA-256 lógico `4b44cb01d05ee1203a36b93337b0403c0d7b69920089c3b3ee5ae29cdff0eeb6`. Ele é independente da configuração do gerador para que evoluções de modelagem não alterem a identidade dos dados raw já auditados.

## Snapshots

| Snapshot | Grão | Instante de decisão | Features em `X` | Targets em `y` | `dev` |
|---|---|---|---:|---:|---:|
| `pre_order` | ordem | ordem e lote disponíveis, antes do processo | 12 | 5 | 500 |
| `in_process_rolling` | tubo | término da etapa de laminação | 30 | 8 | 10.500 |
| `asset_window` | ativo × janela de 2 h | início da janela operacional | 17 | 2 | 5.400 |

Cada diretório contém:

- `X.parquet`: somente a lista ordenada e congelada de features;
- `index.parquet`: `sample_key`, identidade auditável, `snapshot_ts` e `feature_max_source_ts`;
- `y.parquet`: targets separados e `target_available_at_ts`;
- `feature_manifest.json`: versão/hash do contrato, linhagem do DuckDB, colunas, contagens e checksums.

O alinhamento entre arquivos é determinístico e ordenado pela chave de entidade. IDs de ordem, tubo, ativo/janela e `simulation_run_id` nunca aparecem em `X`.

## Regras contra vazamento

1. `feature_max_source_ts <= snapshot_ts` para todas as amostras.
2. `target_available_at_ts > snapshot_ts` para todos os targets.
3. `POST_PROCESS`, `DERIVED_POST`, `RESULT` e `METADATA` são proibidos no contrato de `X`.
4. Targets, disposições, massa boa, horas produtivas e proxies diretos são bloqueados por nome e por seleção explícita.
5. Agregações históricas de ativo usam apenas eventos encerrados antes do snapshot; o target observa as duas horas seguintes.
6. O pacote não lê nem referencia `data/ground_truth`.
7. Nenhum imputador, scaler ou encoder é ajustado nesta fase. O contrato fixa `preprocessing_fit_scope: fold_train_only`; a Fase 5 deverá ajustar transformadores somente no fold de treino.

## Target de parada

A janela de duas horas é definida por ativo para preservar a raridade sem reamostragem artificial. No `dev`, 13,6481% das 5.400 janelas contêm pelo menos uma parada futura; duração é zero quando não há evento. A ocorrência e a duração serão modeladas separadamente na Fase 5.

## Limite de uso

O contrato autoriza preparação de matrizes, não treinamento ou recomendação. As variáveis marcadas `recommendable: true` são apenas controláveis elegíveis; limites condicionais, OOD e aprovação humana ainda pertencem às fases posteriores.
