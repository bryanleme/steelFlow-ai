# Registro de riscos

| ID | Risco | Prob. | Impacto | Mitigação / gatilho | Estado |
|---|---|---:|---:|---|---|
| R-001 | Rodas de CatBoost/SHAP/pymoo não compatíveis com Python 3.14 no ambiente local. | Média | Alto | Manter suporte-fonte `>=3.11`; testar extra por pacote antes da Fase 5; usar Python 3.12/3.13 em venv se houver incompatibilidade comprovada. | Aberto |
| R-002 | Escala `mvp` exceder memória ou disco local. | Média | Alto | Escrita incremental, partição mensal, medição no `dev`, estimativa por tabela e verificação de espaço antes do `mvp`. `dev` ocupou 30,35 MB raw em 19,05 s. | Mitigado; verificar antes do `mvp` |
| R-003 | Verdade causal vazar para features/modelos. | Média | Crítico | Pacote privado, armazenamento isolado, lista de acesso, teste de imports e auditoria executada em processo separado. | Mitigado na Fase 4; revalidar na modelagem |
| R-004 | Performance aparente vir de mix ou vazamento temporal. | Média | Crítico | Diagnóstico de mix separado; contrato point-in-time; `X`/índice/`y` separados; split em quatro janelas e backtesting ainda necessários. | Parcialmente mitigado; Fase 5 aberta |
| R-005 | Evento raro insuficiente para calibração/segmentos. | Média | Alto | Não balancear a população; medir suporte e reportar intervalos. `dev`: 0,819% de refugo e 13,6481% das janelas ativo × 2 h com parada. | Suporte preliminar presente; calibração aberta |
| R-006 | Cenários OOD receberem recomendação indevida. | Baixa | Crítico | Guard de envelope condicional, distância histórica, restrições duras e recusa explícita. | Aberto |
| R-007 | Power BI Desktop indisponível impedir `.pbix` validado. | Alta | Médio | Esquema estrela, 13 exports, relações, Power Query e DAX foram entregues; tema/wireframe ficam para a Fase 7; não alegar `.pbix`. | Parcialmente mitigado; limitação aberta |
| R-008 | Ausência de Git reduzir rastreabilidade de mudanças. | Baixa | Médio | Repositório inicializado e sincronizado com o remoto autorizado; manter commits por checkpoint. | Mitigado |
| R-009 | Linguagem de portfólio sugerir resultado real ou causalidade. | Média | Alto | Avisos persistentes, glossário aprovado e auditoria de termos/números antes da publicação. | Aberto |
| R-010 | `make`/`uv` ausentes no Windows. | Alta | Baixo | Documentar e testar comandos equivalentes com `python -m ...`; manter atalhos opcionais. | Mitigado |
