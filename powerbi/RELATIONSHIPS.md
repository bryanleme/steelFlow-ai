# Relacionamentos do modelo Power BI

> Modelo exclusivamente sintético. Use filtro unidirecional das dimensões para os fatos e cardinalidade `1:*`. Não habilite relações fato-fato.

| Dimensão (1) | Chave | Fato (*) | Chave |
|---|---|---|---|
| `dim_date` | `date_key` | `fact_line_shift`, `fact_order`, `fact_quality`, `fact_energy`, `fact_downtime`, `fact_maintenance`, `fact_losses`, `fact_asset_condition` | `date_key` |
| `dim_product` | `product_key` | `fact_order`, `fact_quality` | `product_key` |
| `dim_line` | `line_key` | todos os fatos | `line_key` |
| `dim_shift` | `shift_key` | `fact_line_shift`, `fact_order`, `fact_energy`, `fact_downtime`, `fact_losses` | `shift_key` |
| `dim_asset` | `asset_key` | `fact_downtime`, `fact_maintenance` | `asset_key` |

`dim_date[full_date]` deve ser marcada como tabela de datas. `fact_line_shift` é o fato executivo principal; as demais tabelas servem a drill-through de ordens, qualidade, energia, perdas e ativos. Campos textuais duplicados nos fatos são conveniências auditáveis, não substituem as relações por chave.
