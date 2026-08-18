# Dicionário de dados v0 — camada raw sintética

## Convenções

- Todos os timestamps são UTC e timezone-aware na geração.
- IDs são strings determinísticas com prefixo de entidade.
- Toda tabela inclui `simulation_run_id`.
- Limites com prefixo `internal_simulated_` não são normativos.
- Grão e chaves abaixo se aplicam dentro de um run.

## Tabelas

| Tabela | Grão | PK | FKs principais | `test` | `dev` | Partição |
|---|---|---|---|---:|---:|---|
| `dim_products` | combinação sintética de produto | `product_code` | — | 12 | 12 | não |
| `dim_lines` | linha produtiva | `line_id` | — | 3 | 3 | não |
| `dim_shifts` | turno | `shift_id` | — | 3 | 3 | não |
| `dim_assets` | ativo por linha/tipo | `asset_id` | `line_id` | 15 | 15 | não |
| `feature_availability` | definição de feature | `feature_name` | — | 43 | 43 | não |
| `production_orders` | ordem | `order_id` | produto, linha, turno, lote | 24 | 500 | data programada |
| `billet_batches` | lote de tarugo por ordem | `billet_batch_id` | `order_id` | 24 | 500 | data programada |
| `tubes` | tubo rastreável | `tube_id` | ordem, lote, produto, linha, turno | 480 | 10.500 | data programada |
| `process_parameters` | parâmetros e mediadores por tubo | `tube_id` | ordem, produto, linha, turno | 480 | 10.500 | data programada |
| `stage_events` | tubo × etapa | `stage_event_id` | tubo, ordem, linha | 3.456 | 75.600 | data programada |
| `sensor_windows` | tubo × sensor × janela | `sensor_window_id` | tubo, ordem, linha | 15.360 | 336.000 | data programada |
| `quality_results` | tubo × característica | `quality_result_id` | tubo, ordem, linha | 2.880 | 63.000 | data programada |
| `energy_events` | tubo × etapa energética | `energy_event_id` | tubo, ordem, linha | 1.440 | 31.500 | data programada |
| `downtime_events` | parada não planejada | `downtime_event_id` | linha, ativo | 40 | 820 | início da parada |
| `maintenance_events` | intervenção de manutenção | `maintenance_event_id` | linha, ativo | 3 | 18 | data programada |

## Colunas por domínio

### `production_orders`

- Identidade/linhagem: `order_id`, `billet_batch_id`, `simulation_run_id`.
- Tempo: `scheduled_start_ts`, `release_ts`, `prediction_time_ts`.
- Contexto: `product_code`, `grade_family`, `line_id`, `shift_id`, `priority_code`, `committed_sequence`, `ambient_temperature_c`.
- Volume: `quantity_tubes`, `target_tonnes`.

### `billet_batches`

- Rastreabilidade: `billet_batch_id`, `order_id`, `heat_code`, `supplier_code`, `received_ts`, `traceability_status`.
- Química sintética: `carbon_pct`, `manganese_pct`, `chromium_pct`, `molybdenum_pct`.
- Geometria: `billet_diameter_mm`, `billet_mass_kg`.

### `tubes`

- Identidade/contexto: `tube_id`, `order_id`, `billet_batch_id`, `tube_sequence`, produto, grau, linha e turno.
- Tempo: `actual_start_ts`, `actual_end_ts`.
- Resultado: `tube_mass_kg`, `approved_first_pass`, `disposition`, `good_mass_t`, `productive_hours`, `actual_tph`.

`actual_tph` é um resultado pós-processo por tubo. O KPI executivo TBH é reconciliado como soma de `good_mass_t` dividida pela soma de `productive_hours`, nunca como média simples de `actual_tph`.

### `process_parameters`

- Estado inicial: `tool_wear_index`, `hours_since_maintenance`, `maintenance_deferred`, `sensor_degradation_index`, `ambient_temperature_c`.
- Reaquecimento: três temperaturas de zona, `soak_time_min`, `reheat_exit_temp_c`, `thermal_uniformity_index`.
- Laminação: `roll_speed_rpm`, `roll_gap_mm`, `mandrel_position_mm`, `reduction_rate_pct`, `exit_speed_m_s`, `lubrication_flow_l_min`, `rolling_load_index`.
- Tratamento térmico: flag de aplicação, temperatura/tempo de austenitização, atraso/vazão/temperatura de têmpera e temperatura/tempo de revenimento.

Parâmetros de tratamento térmico são nulos quando não aplicáveis.

### `stage_events`

- Etapas base: `ORDER_RELEASE`, `BILLET_RECEIPT`, `REHEATING`, `PIERCING_ELONGATION`, `ROLLING_SIZING`, `INSPECTION`, `DISPOSITION`.
- Etapa opcional: `HEAT_TREATMENT`.
- Tempo/estado: `event_start_ts`, `event_end_ts`, `duration_minutes`, `event_status`, `stage_sequence`.

### `sensor_windows`

- Sensores: temperatura de forno, temperatura de saída, velocidade, carga, lubrificação, vibração, potência e vazão de têmpera.
- Janela: `window_index`, início, fim e `feature_available_at_ts`.
- Estatísticas: `mean_value`, `minimum_value`, `maximum_value`, `standard_deviation`, `slope`, `amplitude`, `out_of_range_pct`.
- Qualidade: `missingness_type`, `data_quality_status`, `unit`.

As estatísticas são nulas quando a janela é ausente ou não aplicável.

### `quality_results`

- Características: desvio de diâmetro externo, excentricidade, ovalização, limite de escoamento sintético, resistência à tração sintética e indicação NDT simulada.
- Medição: `measured_value`, limites internos inferior/superior, `unit`, `passed`, `inspection_ts`.

### `energy_events`

- Etapa, timestamp e `energy_kwh`.
- `good_mass_t` e `energy_per_good_tonne_kwh_t`.
- Intensidade é nula quando não há massa aprovada na primeira passagem, evitando divisão por zero.

### `downtime_events`

- Ativo/linha, motivo, início/fim, duração e impacto estimado sintético.
- Contexto pré-evento: horas desde manutenção, degradação de sensor e manutenção postergada.
- Todos os registros são marcados `unplanned = true`.

### `maintenance_events`

- Ativo/linha, tipo, início programado/real, fim, duração, postergação e status.

## Disponibilidade de features

O registro `feature_availability` usa exatamente:

`PLAN`, `PRE_PROCESS`, `IN_PROCESS_REHEAT`, `IN_PROCESS_ROLLING`, `IN_PROCESS_HT`, `POST_PROCESS`, `DERIVED_POST` e `METADATA`.

Somente features `CONTROLLABLE` podem ter `recommendable = true`. Contexto, mediadores, resultados e metadados nunca são recomendáveis.
