# Carrossel LinkedIn — SteelFlow AI

Arquivo final para envio: `SteelFlow_AI_LinkedIn_Carousel.pptx`.

Formato: 1080 × 1350 px, cinco slides e uma mensagem principal por tela.

## Slide 1 — O problema e a proposta

**Dados para comparar decisões.**

Quando um defeito aparece, a plataforma ajuda a trocar tentativa e erro por hipóteses comparáveis.

Rodapé: protótipo offline · dados **100% sintéticos**.

## Slide 2 — A plataforma

**Cinco páginas. Uma jornada de decisão.**

O fluxo reúne visão geral, influências, previsão e risco, teste de cenários e confiabilidade do modelo. O aplicativo possui **5 páginas** <!-- [claim:STREAMLIT_PAGES] --> e uma exploração complementar no Power BI, com **13 tabelas** <!-- [claim:POWERBI_TABLES] --> verificadas.

## Slide 3 — Previsão e risco

**A previsão mostra valor, risco e faixa.**

O SteelFlow AI mostra probabilidades e faixas P10/P50/P90 para colocar produtividade, energia, qualidade e parada em contexto.

Nos seis alvos contínuos, a cobertura P10–P90 observada ficou entre **77,39%** <!-- [claim:INTERVAL_COVERAGE_MIN] --> e **82,13%** <!-- [claim:INTERVAL_COVERAGE_MAX] -->.

## Slide 4 — Teste de cenários

**Mude parâmetros. Compare cenários.**

A plataforma recalcula resultados, compara alternativas e bloqueia hipóteses fora do histórico.

- **12 cenários** <!-- [claim:PUBLISHED_SCENARIOS] --> publicados;
- **9 restrições** <!-- [claim:HARD_CONSTRAINTS] --> obrigatórias;
- **3 sondas OOD** <!-- [claim:OOD_PROBES] --> recusadas.

## Slide 5 — Convite

**Explore a plataforma.**

Veja as telas, teste o fluxo e questione os limites. O sistema organiza evidências para a decisão humana; não substitui o especialista.

github.com/bryanleme/steelFlow-ai

Rodapé: protótipo educacional · **sem controle de máquina** · **não demonstra causalidade industrial**.

## Notas de rastreabilidade — não entram nas telas

- o perfil MVP processou **12.594.517** registros públicos sintéticos
  <!-- [claim:MVP_PUBLIC_ROWS] -->;
- a meta de melhoria do TBH foi **5%**
  <!-- [claim:TBH_ENGINEERING_TARGET] --> e o resultado, **0,98%**
  <!-- [claim:TBH_RELATIVE_IMPROVEMENT] -->;
- o otimizador executou **20.160** avaliações
  <!-- [claim:NSGA_EVALUATIONS] -->;
