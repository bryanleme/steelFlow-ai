# Wireframe do relatório Power BI

> Relatório offline sobre dados 100% sintéticos. Os visuais apoiam investigação e não
> representam validação API 5CT, ganho real ou comando de máquina.

Use uma página 16:9, fundo `#071421`, cartões `#0D2234` e a ordem de leitura abaixo.
O tema versionado está em `theme/steelflow-industrial.json`.

## 1. Executive Overview

| Linha | Composição |
|---|---|
| Cabeçalho | Título, execução sintética e filtros de data, linha, turno, produto e grau |
| KPIs | TBH, FPY, OEE, energia/t boa e parada não planejada |
| Tendência | TBH e FPY por mês; small multiples por linha |
| Diagnóstico | gap ajustado por mix e Pareto de perdas |
| Rodapé | aviso sintético, atualização local e link para drill-through |

## 2. Quality & Losses

| Linha | Composição |
|---|---|
| KPIs | conformidade mecânica simulada, refugo, retrabalho e FPY |
| Visuais | característica por produto/grau, Pareto de perda e tendência de conformidade |
| Detalhe | tabela de ordem e característica para drill-through, sem inferência causal |

## 3. Energy & Downtime

| Linha | Composição |
|---|---|
| KPIs | energia/t boa, minutos de parada, disponibilidade e eventos |
| Visuais | energia por linha/turno, árvore de decomposição e Pareto de causa/ativo |
| Detalhe | histórico de manutenção e condição do ativo |

## 4. Reliability & Governance

O Power BI não replica o runtime dos modelos. Esta página documenta linhagem, horário de
atualização, contagens do manifest, limitações e links para o app Streamlit, que permanece
a superfície oficial para risco calibrado, OOD, explicações e cenários interativos.

## Navegação e acessibilidade

- Use dimensões para filtros unidirecionais; nunca relacione fatos diretamente.
- Use texto além de cor para estado e mantenha contraste mínimo de 4,5:1.
- Exiba unidades no título ou subtítulo de todo visual.
- Preserve os avisos “sintético”, “não causal” e “sem comando de máquina”.
- Não apresente a medida deliberadamente vazia de risco futuro como zero.
