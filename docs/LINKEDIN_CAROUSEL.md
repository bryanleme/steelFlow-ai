# Carrossel LinkedIn — SteelFlow AI

Arquivo final para envio: `SteelFlow_AI_LinkedIn_Carousel.pptx`.

Formato: 1080 × 1350 px, três slides e uma mensagem principal por tela.

## Slide 1 — O problema que eu vi

**Havia dados. Faltava testar hipóteses.**

Quando os defeitos apareciam, os parâmetros eram ajustados na tentativa e erro.

Rodapé: protótipo offline · dados **100% sintéticos**.

## Slide 2 — A proposta

**Testar hipóteses antes de ajustar.**

O SteelFlow AI combina parâmetros, estima probabilidades e faixas P10/P50/P90, compara alternativas e recusa cenários sem suporte histórico.

- **12 cenários** <!-- [claim:PUBLISHED_SCENARIOS] --> publicados;
- **9 restrições** <!-- [claim:HARD_CONSTRAINTS] --> obrigatórias;
- **3 sondas OOD** <!-- [claim:OOD_PROBES] --> recusadas.

## Slide 3 — A mudança

**Da tentativa e erro ao teste de hipóteses.**

O sistema não substitui o especialista. Ele organiza evidências para que a decisão humana compare cenários antes de agir.

github.com/bryanleme/steelFlow-ai

Rodapé: protótipo educacional · **sem controle de máquina** · **não demonstra causalidade industrial**.

## Notas de rastreabilidade — não entram nas telas

- o perfil MVP processou **12.594.517** registros públicos sintéticos
  <!-- [claim:MVP_PUBLIC_ROWS] -->;
- a meta de melhoria do TBH foi **5%**
  <!-- [claim:TBH_ENGINEERING_TARGET] --> e o resultado, **0,98%**
  <!-- [claim:TBH_RELATIVE_IMPROVEMENT] -->;
- a cobertura P10–P90 observada ficou entre **77,39%**
  <!-- [claim:INTERVAL_COVERAGE_MIN] --> e **82,13%**
  <!-- [claim:INTERVAL_COVERAGE_MAX] --> nos seis alvos contínuos;
- o otimizador executou **20.160** avaliações
  <!-- [claim:NSGA_EVALUATIONS] -->;
- o pacote Power BI contém **13 tabelas**
  <!-- [claim:POWERBI_TABLES] --> verificadas;
- o aplicativo possui **5 páginas**
  <!-- [claim:STREAMLIT_PAGES] -->.
