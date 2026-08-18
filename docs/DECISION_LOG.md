# Registro de decisões

Todas as decisões abaixo são reversíveis por nova evidência, mas não serão reabertas sem impedimento material.

| ID | Data | Decisão | Razão | Consequência |
|---|---|---|---|---|
| D-001 | 2026-08-18 | Tratar o diretório como projeto novo. | A auditoria não encontrou arquivos nem documentos prévios e o diretório não foi reconhecido pelo Git. | Não houve migração ou alteração existente a preservar; inicialização Git fica fora do escopo sem solicitação explícita. |
| D-002 | 2026-08-18 | Suportar Python `>=3.11,<3.15`; validar a fundação no 3.14 local. | O único interpretador encontrado foi 3.14.6 e o requisito aceita 3.11 ou superior compatível. | Dependências binárias de dados/ML serão verificadas novamente antes da Fase 2/5. |
| D-003 | 2026-08-18 | Usar `pip` + `venv` como caminho universal e manter `uv`/Makefile opcionais. | `uv` e `make` não estão disponíveis no ambiente Windows auditado. | Todos os atalhos possuem comando Python equivalente documentado. |
| D-004 | 2026-08-18 | Separar dependências em extras `data`, `ml`, `app` e `dev`. | A Fase 1 precisa de instalação leve; pacotes pesados só agregam valor em fases posteriores. | `.[dev]` valida a fundação; `.[all]` será instalado quando necessário. |
| D-005 | 2026-08-18 | Adotar configuração YAML validada por Pydantic estrito e imutável. | Chaves desconhecidas, ranges inválidos e perfis incoerentes devem falhar cedo. | O hash lógico é calculado após normalização tipada e ordenação canônica. |
| D-006 | 2026-08-18 | Interpretar `start_date` e `end_date` como datas inclusivas. | Remove ambiguidade entre 30 dias de `dev` e 24 meses de `mvp`. | `dev` cobre 2025-01-01 a 2025-01-30; `mvp`, 2024-01-01 a 2025-12-31. |
| D-007 | 2026-08-18 | Definir um perfil `test` de 2 dias e 24 ordens. | CI e testes de reprodutibilidade precisam de ciclo muito menor que `dev`. | O perfil mantém as três linhas, três turnos, quatro graus e doze produtos. |
| D-008 | 2026-08-18 | Reservar os comandos finais na CLI, fazendo-os retornar código 2 até a fase correta. | O contrato de interface fica estável sem fingir que pipelines futuros existem. | Makefile já expõe os nomes esperados e falha com mensagem verificável. |
| D-009 | 2026-08-18 | Proibir overwrite por padrão e aceitar apenas output relativo, sem `..`. | Reduz risco de sobrescrever artefatos ou escrever fora do projeto. | Uma sobrescrita futura exigirá opção explícita e alvo resolvido/validado. |
| D-010 | 2026-08-18 | Manter metadados causais em configuração versionada com política explícita de acesso. | A geração e a auditoria precisam conhecer mecanismos; features/modelos/otimização não podem acessá-los. | A Fase 2 adicionará testes arquiteturais e armazenamento isolado da verdade latente. |
| D-011 | 2026-08-18 | Executar as verificações em `.venv` local, e não no diretório global de pacotes do usuário. | O Python isolado do ambiente não enxergou a instalação em `site-packages` do usuário. | O caminho validado coincide com o bootstrap documentado e evita depender do `PATH` global. |
