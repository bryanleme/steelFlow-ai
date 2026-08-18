# Importação com Power Query

1. Execute `python -m steelflow build-db --profile mvp`.
2. No Power BI Desktop, crie um parâmetro de texto chamado `SteelFlowExportRoot`
   apontando para `powerbi/exports/mvp/<simulation_run_id>` no clone local.
3. Crie uma consulta em branco chamada `LoadSteelFlowCsv`, abra o Editor Avançado e cole `powerbi/load_export_csv.pq`.
4. Para cada arquivo abaixo, crie uma consulta em branco com a expressão indicada e use o nome à esquerda.
5. Aplique tipos no modelo e configure os relacionamentos de `RELATIONSHIPS.md`.

| Consulta | Expressão M |
|---|---|
| `dim_date` | `= LoadSteelFlowCsv("dim_date.csv")` |
| `dim_product` | `= LoadSteelFlowCsv("dim_product.csv")` |
| `dim_line` | `= LoadSteelFlowCsv("dim_line.csv")` |
| `dim_shift` | `= LoadSteelFlowCsv("dim_shift.csv")` |
| `dim_asset` | `= LoadSteelFlowCsv("dim_asset.csv")` |
| `fact_line_shift` | `= LoadSteelFlowCsv("fact_line_shift.csv")` |
| `fact_order` | `= LoadSteelFlowCsv("fact_order.csv")` |
| `fact_quality` | `= LoadSteelFlowCsv("fact_quality.csv")` |
| `fact_energy` | `= LoadSteelFlowCsv("fact_energy.csv")` |
| `fact_downtime` | `= LoadSteelFlowCsv("fact_downtime.csv")` |
| `fact_maintenance` | `= LoadSteelFlowCsv("fact_maintenance.csv")` |
| `fact_losses` | `= LoadSteelFlowCsv("fact_losses.csv")` |
| `fact_asset_condition` | `= LoadSteelFlowCsv("fact_asset_condition.csv")` |

O arquivo `export_manifest.json` registra contagens e SHA-256 de cada CSV e Parquet. CSV é usado aqui por compatibilidade simples; os Parquets equivalentes permanecem disponíveis. Não há atualização online, gateway ou dependência de nuvem no MVP.
