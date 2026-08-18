# Carrossel LinkedIn — SteelFlow AI

Arquivo final para envio: `SteelFlow_AI_LinkedIn_Carousel.pptx`.

Formato sugerido: 1080 × 1350 px, dez slides, leitura curta e um único argumento por
tela. As notas de fonte podem ficar pequenas no rodapé.

## Slide 1 — Um digital twin pode dizer “não sei”?

**SteelFlow AI**

Um MVP de dados e ML industrial feito para estimar, restringir e recusar — não para
prometer resultado de fábrica.

Rodapé: portfólio educacional, **100% sintético**.

## Slide 2 — O problema

Dados podem ser abundantes e a decisão continuar retrospectiva. Produtividade,
qualidade, energia, manutenção, mix e desgaste se movem juntos.

Sem separar tempo e contexto, correlação vira explicação e um dashboard vira falsa
confiança.

## Slide 3 — A escala do experimento

O perfil MVP gerou **12.594.517** registros públicos
<!-- [claim:MVP_PUBLIC_ROWS] -->, com Parquet particionado, IDs determinísticos,
manifests e verdade causal isolada.

Rodapé: escala sintética; não é volume de uma planta real.

## Slide 4 — Da fonte ao produto

YAML → Parquet → DuckDB → snapshots point-in-time → modelos temporais → cenários →
**5 páginas** <!-- [claim:STREAMLIT_PAGES] --> Streamlit + **13 tabelas**
<!-- [claim:POWERBI_TABLES] --> Power BI.

## Slide 5 — Métrica sem maquiagem

Meta de TBH: melhorar MAE em **5%** <!-- [claim:TBH_ENGINEERING_TARGET] --> contra a
melhor baseline.

Resultado em teste cronológico: **0,98%** <!-- [claim:TBH_RELATIVE_IMPROVEMENT] -->.

**A meta não foi atingida.** Um modelo complexo não ganha por decreto.

## Slide 6 — Incerteza faz parte da resposta

Nos seis alvos contínuos, os intervalos P10–P90 tiveram cobertura empírica entre
**77,39%** <!-- [claim:INTERVAL_COVERAGE_MIN] --> e **82,13%**
<!-- [claim:INTERVAL_COVERAGE_MAX] --> no conjunto sintético.

Previsão pontual sem faixa não conta a história inteira.

## Slide 7 — Otimização com guardrails

O NSGA-II executou **20.160** avaliações <!-- [claim:NSGA_EVALUATIONS] --> e publicou
**12 cenários** <!-- [claim:PUBLISHED_SCENARIOS] --> condicionais, sob **9 restrições**
<!-- [claim:HARD_CONSTRAINTS] --> duras.

São estimativas em backtest, não receitas de processo.

## Slide 8 — Saber recusar é uma feature

As **3 sondas OOD** <!-- [claim:OOD_PROBES] --> foram bloqueadas e não receberam
recomendação.

Fora do envelope histórico sintético, a resposta correta é: evidência insuficiente.

## Slide 9 — O que torna o case confiável

- teste final consumido uma vez;
- verdade causal fora do treino;
- calibração em janela exclusiva;
- hashes e contratos versionados;
- aceite humano obrigatório;
- **sem controle de máquina**.

## Slide 10 — O limite é parte do produto

SteelFlow AI **não demonstra causalidade industrial**, não valida API 5CT e não alega
ganho real.

Ele mostra potencial de apoio à decisão, arquitetura ponta a ponta e honestidade sobre
o que os dados permitem afirmar.

Próximo passo: dados autorizados, revisão de processo, validação externa em modo
observacional, monitoramento e governança antes de qualquer piloto.

github.com/bryanleme/steelFlow-ai
