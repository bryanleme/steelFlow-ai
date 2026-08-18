# Dados locais

Este diretório recebe somente dados sintéticos e reproduzíveis. Bases geradas não são versionadas.

Camadas planejadas:

- `raw/`: Parquet imutável criado pelo gerador;
- `curated/`: tipos, unidades, chaves e regras validados;
- `analytics/`: marts e KPIs;
- `features/`: snapshots point-in-time;
- `model_outputs/`: previsões, intervalos, explicações e cenários;
- `ground_truth/`: verdade causal isolada, vedada ao pipeline de features/modelos.

O perfil `test` será o primeiro gerado na Fase 2; depois, o perfil `dev`. O perfil `mvp` só será executado após medição de capacidade.
