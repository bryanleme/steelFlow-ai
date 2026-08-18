# Registro de riscos

| ID | Risco | Prob. | Impacto | Mitigação / gatilho | Estado |
|---|---|---:|---:|---|---|
| R-001 | Rodas de CatBoost/SHAP/pymoo não compatíveis com Python 3.14 no ambiente local. | Média | Alto | Manter suporte-fonte `>=3.11`; testar extra por pacote antes da Fase 5; usar Python 3.12/3.13 em venv se houver incompatibilidade comprovada. | Aberto |
| R-002 | Escala `mvp` exceder memória ou disco local. | Média | Alto | Escrita incremental, partição mensal, medição no `dev`, estimativa por tabela e verificação de espaço antes do `mvp`. | Aberto |
| R-003 | Verdade causal vazar para features/modelos. | Média | Crítico | Pacote e armazenamento isolados, lista de acesso, teste de imports e auditoria executada em processo separado. | Aberto |
| R-004 | Performance aparente vir de mix ou vazamento temporal. | Média | Crítico | Baseline condicionado, split temporal em quatro janelas, backtesting e testes point-in-time. | Aberto |
| R-005 | Evento raro insuficiente para calibração/segmentos. | Média | Alto | Dimensionar taxas plausíveis no `test`/`dev`, medir suporte e reportar intervalos; não equilibrar artificialmente a população. | Aberto |
| R-006 | Cenários OOD receberem recomendação indevida. | Baixa | Crítico | Guard de envelope condicional, distância histórica, restrições duras e recusa explícita. | Aberto |
| R-007 | Power BI Desktop indisponível impedir `.pbix` validado. | Alta | Médio | Entregar esquema estrela, exports, relações, Power Query, tema, wireframe e DAX; declarar limitação sem alegar `.pbix`. | Aberto |
| R-008 | Ausência de Git reduzir rastreabilidade de mudanças. | Alta | Médio | Manter versões nos arquivos/configurações e manifests; solicitar inicialização somente se o usuário autorizar. | Aberto |
| R-009 | Linguagem de portfólio sugerir resultado real ou causalidade. | Média | Alto | Avisos persistentes, glossário aprovado e auditoria de termos/números antes da publicação. | Aberto |
| R-010 | `make`/`uv` ausentes no Windows. | Alta | Baixo | Documentar e testar comandos equivalentes com `python -m ...`; manter atalhos opcionais. | Mitigado |
