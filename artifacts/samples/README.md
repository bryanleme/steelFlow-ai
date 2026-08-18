# Evidências leves versionadas

Estes arquivos resumem execuções reais da Fase 2 sem versionar Parquet, causal truth ou manifests completos com centenas de arquivos.

Recrie e valide os dados com:

```bash
python -m steelflow generate --profile test
python -m steelflow validate-data --profile test
python -m steelflow generate --profile dev
python -m steelflow validate-data --profile dev
```

Os resultados são exclusivamente sintéticos e locais.
