# Modelo analítico da Fase 3

## Objetivo

Transformar os Parquets públicos e validados da Fase 2 em um banco DuckDB recriável, com linhagem, marts reconciliados, snapshots point-in-time preliminares e um pacote estrela compacto para Power BI. Nenhum objeto analítico lê `data/ground_truth`.

## Camadas

| Schema | Persistência | Finalidade |
|---|---|---|
| `raw` | views | leitura direta dos Parquets imutáveis da execução |
| `curated` | tabelas | fronteira estável das 15 tabelas públicas, com índices de unicidade |
| `analytics` | dimensões, fatos, marts e views | KPIs, reconciliações, Pareto, condição de ativos e exportação |
| `features` | tabelas point-in-time | snapshots pré-ordem, durante laminação e ativo × janela, sem targets pós-processo |
| `model_outputs` | tabelas vazias | contrato para previsões e cenários de fases futuras |
| `metadata` | tabelas | linhagem da construção e grãos contratados |

O arquivo final fica em `data/analytics/<profile>/<simulation_run_id>/steelflow.duckdb`. A construção usa diretórios temporários irmãos e só promove banco e exports depois que todas as validações passam. `--force` remove apenas os dois diretórios da execução determinística selecionada.

## Dimensões e fatos

- Dimensões conformadas: data, produto, linha, turno e ativo, todas com chaves substitutas estáveis dentro da execução.
- Fatos atômicos: produção por tubo, resultado de qualidade, energia por etapa, parada e manutenção.
- Marts: desempenho por ordem; desempenho executivo por data × linha × turno; qualidade; energia; parada/manutenção; condição de ativo; perdas para Pareto.
- O catálogo `metadata.table_contracts` registra grão, chave primária e regra de partição da camada curated.
- O catálogo `analytics.kpi_catalog` é a versão executável de `docs/KPI_CATALOG.md`.

## Snapshots temporais

`features.pre_order_snapshot` contém uma linha por ordem no instante em que ordem e lote já estão disponíveis. `features.in_process_rolling_snapshot` contém uma linha por tubo ao fim da laminação e limita sensores a `feature_available_at_ts <= snapshot_ts`. `features.asset_window_snapshot` cria uma linha por ativo e janela de duas horas, usando somente históricos encerrados antes do início da janela.

O contrato v1.0.0 seleciona apenas colunas disponíveis, remove IDs/targets/proxies de `X` e grava índice e targets em artefatos separados. Transformadores continuam inexistentes e, quando introduzidos, deverão ser ajustados somente no fold de treino.

## Diagnósticos

Seis tabelas `analytics.diagnostic_*` e o Pareto de perdas cobrem tendências, ajuste de mix, SPC, interações e associações segmentadas. São objetos retrospectivos; particularmente, o baseline de mix de período completo é proibido como feature.

## Auditoria e reconciliação

A construção falha se a validação raw falhar. Depois do SQL e antes da promoção, são verificados:

- seis schemas e linhagem completa da execução;
- contagens das 15 tabelas curated contra o manifest raw;
- unicidade dos grãos de ordem, linha × turno e qualidade;
- massa boa e horas produtivas entre fatos, mart de ordens e mart executivo;
- energia, inspeções e minutos de parada entre fatos e marts;
- fórmula de TBH após agregação, ranges de OEE e tratamento de denominador zero;
- timestamps dos snapshots e ausência de campos pós-processo;
- chaves do esquema estrela e hashes/contagens dos 13 exports;
- ausência de referência à verdade causal em views analíticas.

## Limitações atuais

- `model_outputs` está vazio até as Fases 5–6; não há previsão de risco nem recomendação nesta fase.
- O contrato de features está congelado, mas nenhuma transformação ou divisão temporal foi ajustada ainda.
- O pacote Power BI entrega CSV/Parquet, relações, consultas e DAX como código verificável. Nenhum `.pbix` foi criado ou declarado.
- Todos os números são medições de uma simulação offline; não expressam ganho, ROI, conformidade ou causalidade industrial real.
