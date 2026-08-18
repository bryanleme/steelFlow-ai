# Evidências leves versionadas

Estes arquivos resumem execuções reais das Fases 2–7 sem versionar Parquet, causal truth,
bancos DuckDB, modelos binários ou manifests completos com centenas de arquivos.

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
python -m steelflow generate --profile mvp
python -m steelflow validate-data --profile mvp
python -m steelflow build-db --profile mvp
python -m steelflow diagnose --profile mvp
python -m steelflow build-features --profile mvp
python -m steelflow train --profile mvp
python -m steelflow evaluate --profile mvp
python -m steelflow optimize-demo --profile mvp
python -m steelflow app --profile mvp --check
```

Os resultados são exclusivamente sintéticos e locais.
