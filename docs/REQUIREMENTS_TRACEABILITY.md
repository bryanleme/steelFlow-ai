# Matriz de rastreabilidade

| Requisito | Entregável principal | Fase | Evidência planejada |
|---|---|---:|---|
| Perfis reproduzíveis `test`/`dev`/`mvp` | `configs/simulation_*.yaml`, manifest e hash lógico | 1–2 | testes de configuração e duas gerações isoladas |
| 3 linhas, 3 turnos, 4 graus e 12 produtos | contrato `PlantConfig` e dimensões | 1–2 | validação Pydantic e contratos de dimensão |
| Geração auditável e particionada | `steelflow.generation`, raw Parquet e manifest | 2 | contagens, seeds derivadas, hashes, memória e tempo |
| Mecanismos sintéticos e missingness | config/regra isolada e auditoria posterior | 2 e 5 | testes de isolamento e recuperação de ≥4 mecanismos |
| Integridade e qualidade | `steelflow.validation`, contratos e `data_quality.yaml` | 2 | suíte `tests/data_quality` |
| DuckDB e camadas analíticas | SQL, banco recriável e marts | 3 | testes SQL e reconciliações |
| KPIs documentados | catálogo de KPI e marts por ordem/linha × turno | 3 | fórmulas e testes de divisão por zero |
| Esquema estrela Power BI | dimensões/fatos exportados, relações e DAX | 3 e 7 | validação de schemas, JSON e medidas |
| Feature availability e anti-leakage | registro de disponibilidade e snapshots temporais | 4 | testes de timestamp, pós-processo, ID/target/proxy e fold |
| Baselines obrigatórios | pipeline de baseline versionado | 5 | relatório no mesmo teste temporal |
| CatBoost, calibração e quantis | modelos, artefatos e avaliação | 5 | métricas, cobertura, calibração e segmentos |
| SHAP e explicabilidade | explicações globais, por segmento e cenário | 5 | artefatos e smoke tests |
| NSGA-II com restrições | otimizador, envelopes e alternativas Pareto | 6 | property/constraint tests e recusa OOD |
| Streamlit com cinco páginas | `app/` e componentes | 7 | smoke test e fluxo de cenário |
| Aprovação humana e ausência de controle | guardas de interface e avisos | 7 | teste de confirmação e inspeção visual |
| Pacote Power BI | exports, relações, Power Query, tema, wireframe e DAX | 7 | checksums e validação de arquivos |
| Portfólio honesto/rastreável | cards, case, LinkedIn, carrossel e demo | 8 | auditoria automática de números e linguagem |
| Instalação reproduzível | README, `pyproject.toml`, Makefile opcional | 1 e 8 | ambiente limpo/equivalente e comandos documentados |
