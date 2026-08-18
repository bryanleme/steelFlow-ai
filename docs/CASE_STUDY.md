# SteelFlow AI — estudo de caso de um MVP sintético e auditável

## Resumo executivo

SteelFlow AI é um protótipo offline de apoio à decisão para uma fábrica fictícia de
tubos OCTG sem costura. O projeto conecta geração de dados, engenharia analítica,
machine learning temporal, incerteza calibrada, explicabilidade, otimização restrita,
Streamlit e um pacote pronto para Power BI.

O conjunto é **100% sintético**, o produto opera **sem controle de máquina** e o projeto
**não demonstra causalidade industrial**. Nenhum dado, limite, cenário ou
resultado representa uma planta real ou valida conformidade API 5CT.

## O problema que o protótipo investiga

Em manufatura, produtividade, qualidade, energia e disponibilidade mudam juntas e
também respondem ao mix. Uma leitura agregada pode atribuir ao processo uma mudança
que veio de produto, grau, linha ou desgaste. O MVP foi desenhado para mostrar uma
alternativa tecnicamente honesta:

1. separar grãos, timestamps e disponibilidade de cada feature;
2. comparar modelos contra baselines fortes em janelas cronológicas;
3. reportar risco e intervalos, não somente previsões pontuais;
4. comparar alternativas apenas dentro do suporte histórico sintético;
5. manter a decisão com uma pessoa e registrar toda limitação relevante.

## O que foi construído

O perfil `mvp` materializou **12.594.517** registros públicos
<!-- [claim:MVP_PUBLIC_ROWS] --> em Parquet particionado e uma verdade causal separada.
O pipeline constrói DuckDB, marts, snapshots point-in-time, dez tarefas preditivas e
artefatos de explicabilidade. O produto final possui **5 páginas**
<!-- [claim:STREAMLIT_PAGES] --> em Streamlit e um modelo estrela com **13 tabelas**
<!-- [claim:POWERBI_TABLES] --> para Power BI.

Na camada de cenários, o NSGA-II fez **20.160** avaliações
<!-- [claim:NSGA_EVALUATIONS] -->. O protótipo publicou **12 cenários**
<!-- [claim:PUBLISHED_SCENARIOS] --> condicionais que passaram pelas **9 restrições**
<!-- [claim:HARD_CONSTRAINTS] -->. As **3 sondas OOD**
<!-- [claim:OOD_PROBES] --> foram recusadas sem emitir recomendação.

## Como a avaliação evitou uma conclusão conveniente

Treino, tuning, calibração e teste final são janelas distintas. O teste final foi
consumido uma única vez e chamadas posteriores reutilizam o mesmo manifest. Para TBH,
a meta de engenharia era superar a baseline mais forte em **5%**
<!-- [claim:TBH_ENGINEERING_TARGET] --> de MAE. O protótipo estimou melhora de apenas
**0,98%** <!-- [claim:TBH_RELATIVE_IMPROVEMENT] -->. Portanto, a meta **não foi atingida**.

Esse resultado negativo é parte do valor do case: a arquitetura não promoveu o modelo
porque ele era mais sofisticado. Para os seis targets contínuos, a cobertura empírica
P10–P90 ficou entre **77,39%** <!-- [claim:INTERVAL_COVERAGE_MIN] --> e **82,13%**
<!-- [claim:INTERVAL_COVERAGE_MAX] --> no conjunto sintético.

## Cenários, não prescrições

Cada alternativa é uma estimativa em backtest, condicionada a produto, grau, linha e
desgaste. A barreira OOD, os limites de mudança e as restrições duras impedem que uma
alternativa fora do envelope seja publicada. O aceite humano é obrigatório e a saída
é apenas JSON/CSV; não existe integração com PLC, MES ou equipamento.

Os valores de cenário são associações aprendidas pelo modelo, não contrafactuais. Eles
representam **potencial de apoio** para formular hipóteses em ambiente sintético, não
instruções operacionais.

## Auditoria da verdade causal

Depois do congelamento da avaliação, um módulo isolado comparou relações públicas com
a verdade conhecida pelo gerador e recuperou **6/6** mecanismos testados
<!-- [claim:CAUSAL_RECOVERY] -->. A verdade não entrou em features, treino, calibração,
seleção ou otimização. O resultado valida a coerência interna da simulação, mas não
autoriza uma alegação causal sobre uma fábrica.

## Resultado e aprendizados

- A separação temporal, a baseline forte e a publicação do critério não atingido foram
  mais importantes do que maximizar uma métrica isolada.
- Intervalos e calibração mudam a conversa de “qual é o número?” para “qual é a faixa e
  quando devemos recusar?”.
- Um otimizador só é apresentável com envelope, OOD, restrições, rastreabilidade e
  aprovação humana.
- Dados sintéticos permitem testar arquitetura e controles, mas não substituem
  validação externa, engenharia de processo ou governança operacional.

## Evidência reproduzível

Os números destacados são verificados por `python -m steelflow audit-portfolio`. O
contrato está em `configs/portfolio_claims.json` e aponta para os resumos versionados em
`artifacts/samples/`. Relatórios técnicos complementares ficam em `docs/`, e os dados e
modelos pesados são recriáveis e permanecem fora do Git.

## Limites para qualquer continuidade

Antes de considerar um piloto real, seriam necessários dados industriais autorizados,
revisão com especialistas, limites API aplicáveis, validação temporal externa,
monitoramento, gestão de mudança, análise de segurança, aprovação jurídica e um modo
somente observacional. Nada neste MVP atende ou substitui essas etapas.
