# Checklist de entrega Power BI

## Conteúdo verificável

- [x] 5 dimensões e 8 fatos em CSV e Parquet.
- [x] Contagem, tamanho e SHA-256 de cada export em `export_manifest.json`.
- [x] Relacionamentos `1:*` e filtro unidirecional documentados.
- [x] Função Power Query parametrizada para carregamento local.
- [x] Medidas DAX com divisão segura e médias ponderadas.
- [x] Tema industrial JSON versionado.
- [x] Wireframe de quatro páginas, navegação e avisos de uso.
- [x] Validador automático dos 26 arquivos exportados.

## Validação no Power BI Desktop

1. Defina `SteelFlowExportRoot` conforme `POWER_QUERY.md`.
2. Importe `theme/steelflow-industrial.json`.
3. Carregue as 13 consultas e aplique os relacionamentos de `RELATIONSHIPS.md`.
4. Cole as medidas de `measures/steelflow_measures.dax`.
5. Monte as páginas conforme `WIREFRAME.md` e confira totais contra o manifest.

Nenhum `.pbix` está incluído ou declarado: o Power BI Desktop não faz parte do ambiente
automatizado validado. O pacote entregue é reproduzível, revisável e não depende de nuvem.
