# Registro de riscos

| ID | Risco | Prob. | Impacto | Mitigação / gatilho | Estado |
|---|---|---:|---:|---|---|
| R-001 | Rodas de CatBoost/SHAP/pymoo não compatíveis com Python 3.14 no ambiente local. | Média | Alto | CatBoost 1.2.10, scikit-learn 1.9.0 e SHAP 0.52.0 foram validados; `pymoo` foi separado no extra `optimization` e será verificado na Fase 6. | ML mitigado; otimização aberta |
| R-002 | Escala `mvp` exceder memória ou disco local. | Média | Alto | Escrita incremental e verificação prévia de 286,9 GB livres. O run real ocupou 0,672 GiB raw e levou 410,29 s para 12.594.517 registros. | Mitigado no ambiente local |
| R-003 | Verdade causal vazar para features/modelos. | Média | Crítico | Pacote privado, armazenamento isolado, teste de imports e auditoria somente após manifest de avaliação congelado. | Mitigado e validado na Fase 5 |
| R-004 | Performance aparente vir de mix ou vazamento temporal. | Média | Crítico | Quatro janelas, embargo por disponibilidade de rótulo, três backtests e teste final idempotente. | Mitigado; monitorar drift futuro |
| R-005 | Evento raro insuficiente para calibração/segmentos. | Média | Alto | População natural preservada; 321 refugos e 3.368 paradas no teste final; métricas sob orçamento. | Parcial: suporte existe, PR-AUC de refugo permanece baixo |
| R-006 | Cenários OOD receberem recomendação indevida. | Baixa | Crítico | Guard de envelope condicional, distância histórica, restrições duras e recusa explícita. | Aberto |
| R-007 | Power BI Desktop indisponível impedir `.pbix` validado. | Alta | Médio | Esquema estrela, 13 exports, relações, Power Query e DAX foram entregues; tema/wireframe ficam para a Fase 7; não alegar `.pbix`. | Parcialmente mitigado; limitação aberta |
| R-008 | Ausência de Git reduzir rastreabilidade de mudanças. | Baixa | Médio | Repositório inicializado e sincronizado com o remoto autorizado; manter commits por checkpoint. | Mitigado |
| R-009 | Linguagem de portfólio sugerir resultado real ou causalidade. | Média | Alto | Avisos persistentes, glossário aprovado e auditoria de termos/números antes da publicação. | Aberto |
| R-010 | `make`/`uv` ausentes no Windows. | Alta | Baixo | Documentar e testar comandos equivalentes com `python -m ...`; manter atalhos opcionais. | Mitigado |
| R-011 | Meta de melhoria de TBH não ser atingida. | Alta | Médio | Comparar com a baseline mais forte no teste intocado e impedir alegação favorável. | Materializado: 0,98% contra meta de 5% |
| R-012 | Limiar 0,5 ocultar valor de ranking em evento raro ou induzir política ruim. | Alta | Alto | Reportar PR-AUC, calibração, matriz e recall sob orçamento; deixar thresholds operacionais fora do escopo. | Mitigado na avaliação; decisão operacional proibida |
