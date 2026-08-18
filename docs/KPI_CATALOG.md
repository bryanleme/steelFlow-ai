# Catálogo de KPIs

> Todos os indicadores usam exclusivamente dados sintéticos. Limites dimensionais, mecânicos e operacionais são internos e simulados; não representam API 5CT nem desempenho de fábrica real.

O contrato executável está em `analytics.kpi_catalog`. As razões retornam `NULL` quando o denominador é zero, em vez de inventar zero ou infinito. O grão executivo é data × linha × turno; o mart de ordens oferece a visão equivalente por ordem.

| KPI | Fórmula | Grão | Unidade | Filtro | Campos de origem | Divisão por zero |
|---|---|---|---|---|---|---|
| Good Tonnes | `SUM(good_mass_t)` | data × linha × turno; ordem | t | massa aprovada na primeira passagem | `tubes.good_mass_t` | não aplicável |
| Productive Hours | `SUM(productive_hours)` | data × linha × turno; ordem | h | tubos processados | `tubes.productive_hours` | não aplicável |
| TBH / GTPH | `SUM(good_mass_t) / SUM(productive_hours)` | data × linha × turno; ordem | t/h | massa boa em primeira passagem | `tubes.good_mass_t`, `tubes.productive_hours` | `NULL` |
| FPY | `SUM(approved_first_pass) / COUNT(tube_id)` | data × linha × turno; ordem | razão | todas as disposições | `tubes.approved_first_pass`, `tube_id` | `NULL` |
| Availability | `productive_hours / (productive_hours + downtime_minutes / 60)` | data × linha × turno | razão | parada não planejada | produção e `downtime_events.duration_minutes` | `NULL` |
| Performance | `MIN(total_tonnes / (42 t/h × productive_hours), 1)` | data × linha × turno | razão | capacidade analítica interna simulada de 42 t/h | massa total e horas produtivas | `NULL` |
| Quality | `good_tonnes / total_tonnes` | data × linha × turno | razão | primeira passagem | massa boa e massa total | `NULL` |
| OEE | `Availability × Performance × Quality` | data × linha × turno | razão | componentes internos simulados | componentes acima | `NULL` se algum componente for `NULL` |
| Scrap Rate | `COUNT(disposition='SCRAP') / COUNT(tube_id)` | data × linha × turno; ordem | razão | todas as disposições | `tubes.disposition`, `tube_id` | `NULL` |
| Rework Rate | `COUNT(disposition='REWORK') / COUNT(tube_id)` | data × linha × turno; ordem | razão | todas as disposições | `tubes.disposition`, `tube_id` | `NULL` |
| Energy per Good Tonne | `SUM(energy_kwh) / SUM(good_mass_t uma vez por tubo)` | data × linha × turno; ordem | kWh/t | massa boa em primeira passagem | `energy_events.energy_kwh`, `tubes.good_mass_t` | `NULL` |
| Unplanned Downtime | `SUM(duration_minutes)` | data × linha × turno | min | eventos não planejados | `downtime_events.duration_minutes` | não aplicável |
| Outer Diameter Deviation | `AVG(measured_value)` | data × produto × linha | mm | `outer_diameter_deviation_mm` | `quality_results` | `NULL` sem inspeções |
| Wall Eccentricity | `AVG(measured_value)` | data × produto × linha | % | `wall_eccentricity_pct` | `quality_results` | `NULL` sem inspeções |
| Ovality | `AVG(measured_value)` | data × produto × linha | % | `ovality_pct` | `quality_results` | `NULL` sem inspeções |
| Simulated Mechanical Conformance | `SUM(passed) / COUNT(quality_result_id)` | data × produto × linha | razão | escoamento e tração simulados | `quality_results.passed`, `characteristic` | `NULL` |
| Next-window Downtime Probability | probabilidade calibrada do modelo | ativo × janela operacional | probabilidade | alvo `next_window_downtime` | artefato congelado do modelo/otimização | `NULL` no esquema estrela descritivo; servido pelo app |

## Regras de agregação

- TBH nunca é calculado como média de TBHs atômicos; soma-se massa boa e horas antes da divisão.
- FPY, refugo e retrabalho no Power BI são médias ponderadas por `tube_count`.
- `energy_events` contém três etapas por tubo. O mart de energia remove essa repetição da massa boa antes de calcular kWh/t.
- A Fase 7 consome probabilidades calibradas diretamente dos artefatos congelados no app.
  O mart DuckDB e a medida Power BI permanecem deliberadamente vazios para não duplicar
  previsões sem chave de atualização/linhagem; nenhuma probabilidade é fabricada no banco.
- O valor de 42 t/h é uma referência exclusivamente interna e simulada para o componente Performance; não é capacidade publicada ou validada de equipamento real.
