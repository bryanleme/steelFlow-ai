# Auditoria da verdade causal sintética

## Resultado

**PASS — 6/6 mecanismos recuperados** <!-- [claim:CAUSAL_RECOVERY] -->, contra um
critério mínimo previamente definido de quatro mecanismos. O resultado mede a coerência
interna do gerador e da análise pública; não é evidência de causalidade industrial.

## Fronteira de isolamento

A verdade causal é criada pelo gerador em `data/ground_truth/`, separada dos Parquets
públicos. Os pacotes `features`, `models` e `optimization` são proibidos por teste de
importar o módulo privado ou ler esse diretório. Treino, tuning, calibração, seleção de
modelo, explicabilidade e otimização usam somente campos públicos disponíveis no tempo.

A auditoria é executada **depois** que o manifest da avaliação final foi congelado. Ela
não altera features, hiperparâmetros, thresholds, previsões, SHAP ou cenários. O artefato
de auditoria registra explicitamente `training_truth_access = false` e
`audited_after_evaluation_freeze = true`.

## Método

Para cada mecanismo pré-registrado, o auditor verifica duas evidências independentes no
conjunto público:

1. associação direcional/rankeada coerente com a relação projetada no gerador;
2. presença da feature pública esperada entre as vinte maiores contribuições TreeSHAP
   da tarefa relacionada.

A amostra auditada contém 37.500 linhas sintéticas. Os seis mecanismos cobrem efeito de
mix, interação entre uniformidade térmica e desgaste do mandril, interação entre
velocidade e janela térmica, tratamento térmico por grau e espessura, degradação de
sensor acumulada e drift temporal do processo.

## Interpretação correta

“Recuperado” significa que o pipeline encontrou, após o congelamento, uma assinatura
pública compatível com a estrutura conhecida da simulação. Isso ajuda a detectar um
gerador incoerente ou uma modelagem incapaz de refletir seus sinais.

Não significa que:

- SHAP identificou uma causa;
- os parâmetros sintéticos correspondem a uma planta;
- uma intervenção produzirá o efeito estimado;
- limites simulados satisfazem API 5CT;
- cenários podem ser enviados a equipamentos.

## Evidência e reprodução

- resumo versionado: `artifacts/samples/phase_5_modeling_summaries.json`;
- resultado completo recriável: `evaluation/audit/causal_recovery.json` dentro do run
  local de modelos;
- teste de fronteira: suíte automatizada de isolamento da verdade causal;
- auditoria de números publicados: `python -m steelflow audit-portfolio`.

Toda publicação deve descrever este resultado como auditoria posterior em um conjunto
sintético, nunca como descoberta ou validação causal industrial.
