# Post para LinkedIn

Em uma das indústrias onde trabalhei, informação não faltava.

O problema aparecia quando os defeitos começavam.

Os parâmetros eram ajustados na tentativa e erro: mudava-se uma variável, observava-se o resultado e tentava-se novamente.

Havia experiência de processo. Havia dados. Mas não havia um ambiente para testar hipóteses de parâmetros e estimar o comportamento provável da máquina antes do próximo ajuste.

Foi dessa lacuna que nasceu o **SteelFlow AI**.

A proposta é simples:

1. combinar diferentes parâmetros de processo;
2. calcular cenários “e se?”;
3. estimar probabilidades e faixas de resultado;
4. comparar alternativas antes da decisão humana.

Para cada hipótese, o sistema mostra risco estimado de falha de qualidade, FPY, produtividade e energia com faixas P10/P50/P90. Se a combinação sair do comportamento histórico ou violar uma restrição, o cenário é recusado.

No MVP, foram avaliadas **20.160 combinações**. O produto publicou **12 cenários** <!-- [claim:PUBLISHED_SCENARIOS] --> que passaram por **9 restrições** <!-- [claim:HARD_CONSTRAINTS] --> e organizou a análise em **5 páginas** <!-- [claim:STREAMLIT_PAGES] -->.

A base possui **12.594.517** registros públicos sintéticos <!-- [claim:MVP_PUBLIC_ROWS] -->.

E nem todo resultado foi positivo: a meta de melhoria do modelo de TBH era **5%** <!-- [claim:TBH_ENGINEERING_TARGET] -->, mas o resultado foi **0,98%** <!-- [claim:TBH_RELATIVE_IMPROVEMENT] -->. Mantive isso visível porque transparência também faz parte de um sistema de decisão.

Uma parte importante dessa experiência foi a forma de construção: o programa foi desenvolvido com **vibe coding**.

Usei IA como parceira para transformar perguntas em protótipos, acelerar código, documentação e testes. Mas velocidade não substituiu critério: métricas, limites e decisões continuaram sendo revisados, testados e auditados.

O objetivo não é substituir o conhecimento de processo — nem o trabalho analítico.

É reduzir o tempo entre uma pergunta, uma hipótese e uma análise que possa ser discutida com evidências.

Escopo importante: o protótipo é offline e **100% sintético**, está **sem controle de máquina** e **não demonstra causalidade industrial**. As saídas são estimativas de modelos, não receitas operacionais.

Se a IA já consegue encurtar o caminho entre uma hipótese e sua análise, **como podemos usá-la para acelerar os processos analíticos sem perder rastreabilidade, senso crítico e responsabilidade?**

Projeto, código e evidências:
https://github.com/bryanleme/steelFlow-ai

#DataEngineering #MachineLearning #Manufacturing #IndustrialAI #VibeCoding #DataScience
