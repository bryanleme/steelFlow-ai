# Pacote Power BI

> Protótipo offline com dados 100% sintéticos. Limites e resultados são internos e simulados; não há validação API 5CT, controle de máquina, ganho ou ROI real.

A Fase 3 entrega um esquema estrela compacto e recriável:

- 5 dimensões e 8 fatos em CSV e Parquet;
- `export_manifest.json` com linhagem, contagens, bytes e SHA-256;
- [relacionamentos](RELATIONSHIPS.md) com cardinalidade e direção de filtro;
- [procedimento Power Query](POWER_QUERY.md) e função M reutilizável;
- [medidas DAX](measures/steelflow_measures.dax) para KPIs executivos e qualidade.

Gere ou atualize o pacote com:

```powershell
.venv\Scripts\python -m steelflow build-db --profile dev --force
```

Os dados ficam em `powerbi/exports/<profile>/<simulation_run_id>/` e são ignorados pelo Git porque são recriáveis. Os contratos, código e documentação permanecem versionados.

Nenhum arquivo `.pbix` foi criado ou declarado. Tema, wireframe e eventual validação no Power BI Desktop pertencem à Fase 7.
