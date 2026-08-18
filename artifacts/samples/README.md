# Evidências leves versionadas

Estes arquivos resumem execuções reais das Fases 2–3 sem versionar Parquet, causal truth, bancos DuckDB ou manifests completos com centenas de arquivos.

Recrie e valide os dados com:

```bash
python -m steelflow generate --profile test
python -m steelflow validate-data --profile test
python -m steelflow generate --profile dev
python -m steelflow validate-data --profile dev
python -m steelflow build-db --profile test
python -m steelflow build-db --profile dev
python -m steelflow diagnose --profile test
python -m steelflow build-features --profile test
python -m steelflow diagnose --profile dev
python -m steelflow build-features --profile dev
```

Os resultados são exclusivamente sintéticos e locais.
