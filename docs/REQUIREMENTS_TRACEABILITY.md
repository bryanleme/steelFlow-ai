# Matriz de rastreabilidade

| Requisito | Entregável principal | Fase | Evidência planejada |
|---|---|---:|---|
| Perfis reproduzíveis `test`/`dev`/`mvp` | `configs/simulation_*.yaml`, manifest e hash lógico | 1–2 | testes de configuração e duas gerações isoladas |
| 3 linhas, 3 turnos, 4 graus e 12 produtos | contrato `PlantConfig` e dimensões | 1–2 | validação Pydantic e contratos de dimensão |
| Geração auditável e particionada | `steelflow.generation`, raw Parquet e manifest | 2 | contagens, seeds derivadas, hashes, memória e tempo |
| Mecanismos sintéticos e missingness | config/regra isolada e auditoria posterior | 2 e 5 | teste de imports e auditoria posterior PASS com 6/6 mecanismos |
| Integridade e qualidade | `steelflow.validation`, contratos e `data_quality.yaml` | 2 | suíte `tests/data_quality` |
| DuckDB e camadas analíticas | SQL, banco recriável e marts | 3 | 43 checks por perfil, 15 contagens curated e reconciliações |
| KPIs documentados | catálogo de 17 KPIs e marts por ordem/linha × turno | 3 | contrato completo e testes de fórmula/divisão por zero |
| Esquema estrela Power BI | 5 dimensões, 8 fatos exportados, relações e DAX | 3 e 7 | PASS: 13 tabelas/26 arquivos, 24.482.012 bytes e checksums; `.pbix` não declarado |
| Feature availability e anti-leakage | contrato v1.0.0 e três snapshots `X`/índice/`y` | 4 | 27 checks por perfil: timestamp, pós-processo, ID/target/proxy, hash e `fold_train_only` |
| Diagnóstico e ajuste de mix | sete tabelas reproduzíveis de tendência, mix, SPC, Pareto e interações | 4 | 8 checks por perfil e relatório com linguagem não causal |
| Baselines obrigatórios | pipeline de baseline versionado | 5 | mediana/prior, condicionado, linear/logística e RF no mesmo teste final |
| CatBoost, calibração e quantis | modelos, artefatos e avaliação | 5 | dez tarefas; Platt em quatro classificadores; MultiQuantile em seis regressões; 50/50 checks |
| SHAP e explicabilidade | explicações globais, por segmento e cenário | 5 | 30 Parquets TreeSHAP, 218 recortes de métricas e dez cenários por tarefa |
| NSGA-II com restrições | otimizador, envelopes e alternativas Pareto | 6 | 20.160 avaliações; 234 Pareto viáveis; 12/12 cenários seguros; 3/3 recusas OOD; 14/14 checks |
| Cenários auditáveis e incerteza | contrato JSON e relatório de otimização | 6 | quatro perfis por contexto, P10/P50/P90, distância, restrições ativas e hash lógico repetido |
| Streamlit com cinco páginas | `app/` e componentes | 7 | PASS: cinco AppTests com artefatos `mvp` e screenshots reais |
| Aprovação humana e ausência de controle | guardas de interface e avisos | 7 | PASS: recusa sem aceite, confirmação explícita e `machine_command=false` |
| Pacote Power BI | exports, relações, Power Query, tema, wireframe e DAX | 7 | PASS: validador de JSON/DAX e SHA-256 dos 26 exports |
| Portfólio honesto/rastreável | cards, case, LinkedIn, carrossel e demo | 8 | auditoria automática de números e linguagem |
| Instalação reproduzível | README, `pyproject.toml`, Makefile opcional | 1 e 8 | ambiente limpo/equivalente e comandos documentados |
