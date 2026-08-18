# Dados locais

Este diretório recebe somente dados sintéticos e reproduzíveis. Bases geradas não são versionadas.

Camadas implementadas:

- `raw/`: Parquet imutável criado pelo gerador;
- `curated/`: tipos, unidades, chaves e regras validados;
- `analytics/`: marts e KPIs;
- `features/`: snapshots point-in-time;
- `model_outputs/`: previsões, intervalos, explicações e cenários;
- `ground_truth/`: verdade causal isolada, vedada ao pipeline de features/modelos.

Os perfis `test`, `dev` e `mvp` foram materializados e validados. O perfil `mvp`
produziu 12.594.517 registros públicos em 0,672 GiB de Parquet raw no ambiente local.
Esses resultados pertencem exclusivamente à simulação.

As camadas pesadas permanecem fora do Git e podem ser reconstruídas pelos comandos do
README raiz. Manifests e resumos leves em `artifacts/samples/` preservam a evidência
necessária sem versionar dados ou modelos.
