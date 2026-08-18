# Model card — SteelFlow AI MVP

## Visão geral

Este card resume o sistema de dez tarefas do perfil `mvp`. Cards individuais e métricas
por tarefa são recriados dentro de cada run; a visão tabular consolidada está em
`MODEL_CARDS.md`.

## Uso pretendido

Explorar, exclusivamente em dados sintéticos, estimativas temporais de TBH, energia,
desvios dimensionais, duração e ocorrência de parada, falha de qualidade, retrabalho e
refugo. As saídas podem apoiar demonstração, estudo de arquitetura, análise de risco e
formulação de hipóteses.

## Dados e separação temporal

- perfil: `mvp`, de 2024-01-01 a 2025-12-31;
- treino, tuning, calibração e teste final cronologicamente distintos;
- embargo de rótulos conforme a disponibilidade de cada snapshot;
- verdade causal sintética fora de features e treinamento;
- teste final consumido uma única vez e protegido por manifest idempotente.

## Famílias e saídas

Baselines simples e condicionais são comparadas com CatBoost. Regressões publicam
P10/P50/P90; classificações recebem calibração sigmoid em janela exclusiva. TreeSHAP
global, por segmento e local descreve associações do modelo.

## Desempenho-chave

Para TBH, a baseline condicionada obteve MAE 2,158 t/h e o CatBoost, 2,137 t/h. A
melhora relativa foi 0,98%, abaixo da meta prévia de 5%; portanto, o critério de
engenharia não foi atingido. A cobertura P10–P90 dos seis alvos contínuos variou de
77,39% a 82,13%. Nos quatro classificadores, ECE ficou entre 0,00053 e 0,01572.

As métricas pertencem ao teste cronológico de uma simulação e não estimam desempenho em
produção.

## Limitações e riscos

- os dados não representam física completa, fábrica, fornecedor, operador ou produto;
- desempenho sintético não transfere automaticamente para dados industriais;
- TreeSHAP e cenários não demonstram causalidade;
- o alvo de refugo é raro e mantém PR-AUC baixa;
- alguns segmentos têm suporte reduzido;
- drift e calibração precisariam de monitoramento contínuo em qualquer piloto;
- limites são internos e não validam API 5CT.

## Uso proibido

Controle ou ajuste de equipamento, prescrição de receita, certificação, avaliação de
pessoas, alegação de ganho/ROI, decisão autônoma ou uso em segurança crítica.

## Monitoramento necessário para um piloto hipotético

Qualidade e completude de dados, PSI/KS por feature, drift por produto/grau/linha,
erro e cobertura por janela e segmento, ECE e curvas de calibração, prevalência,
taxa de recusa OOD, violações de restrição, latência, overrides humanos e incidentes.
Thresholds e limites exigiriam aprovação formal de processo, qualidade e segurança.

## Governança

O MVP é offline, não envia comandos e exige aceite humano no laboratório de cenários.
Qualquer mudança de dados, features, modelo ou limites invalida os hashes atuais e exige
nova avaliação. Consulte `MODELING_REPORT.md`, `FEATURE_CONTRACT.md`,
`SCENARIO_CONTRACT.md`, `CAUSAL_GROUND_TRUTH_AUDIT.md` e `RISK_REGISTER.md`.
