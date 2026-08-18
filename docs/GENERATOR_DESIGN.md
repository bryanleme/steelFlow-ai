# Design do gerador sintético

## Separação arquitetural

- `generation/_ground_truth.py`: parâmetros latentes e equações causais sintéticas.
- `generation/generator.py`: orquestra entidades, partições e eventos públicos.
- `generation/seeds.py`: seed principal, namespaces e RNGs por partição.
- `generation/ids.py`: IDs e run ID determinísticos.
- `generation/writer.py`: Parquet incremental, contagens e hashes.
- `validation/raw_data.py`: contratos públicos; deliberadamente não importa a verdade causal.

A verdade por tubo é gravada em `data/ground_truth`, enquanto a camada pública vai para `data/raw`. Teste arquitetural falha se `features`, `models` ou `optimization` importarem o módulo privado.

## Mecanismos versionados — truth `0.1.0`

1. **Mix e complexidade:** geometria/complexidade latente reduz o throughput-base; produtos complexos tornam-se mais frequentes ao longo do período, permitindo agregações com efeito de mix.
2. **Uniformidade × desgaste:** excentricidade cresce com `(1 - uniformidade térmica) × desgaste`.
3. **Velocidade × janela térmica:** velocidade melhora throughput apenas quando temperatura e uniformidade estão na janela; fora dela há penalidade de defeito e produtividade.
4. **Tratamento térmico:** resposta de austenitização/têmpera/revenimento muda por grau e espessura.
5. **Paradas:** risco cresce com horas desde manutenção, desgaste, degradação do sensor e postergação.
6. **Drift:** calibração evolui por tendência e componente periódica por linha.
7. **Missingness:** MCAR, MAR, falhas contíguas em bloco e estado não aplicável são rotulados.
8. **Eventos raros:** refugo/NDT/paradas são raros ou esparsos, mas dependem de variáveis observáveis; a população não é artificialmente balanceada.

Os componentes latentes são armazenados apenas para auditoria posterior: complexidade, drift, alvo térmico, estado da janela, penalidade velocidade-térmica, interação de excentricidade, mismatch térmico, degradação, risco de parada e probabilidade NDT.

## Atomicidade e sobrescrita

Cada run é escrito primeiro em diretórios `.staging`. O diretório só é promovido após todas as tabelas e manifests serem concluídos. Em falha, o staging é removido e um manifest de falha é salvo em `artifacts/runs`.

Um run existente bloqueia nova geração. `--force` remove somente os diretórios finais derivados do perfil/configuração corrente, após validação do pai permitido.

## Hashes

- Hash de configuração: JSON canônico do bundle Pydantic.
- Hash lógico por tabela: linhas na ordem determinística, JSON canônico e SHA-256 incremental.
- Hash físico: SHA-256 de cada Parquet.
- Hash do dataset: combinação ordenada dos hashes lógicos de tabelas.
- Manifest: SHA-256 em arquivo sidecar.

Timestamps de execução podem variar entre reruns; IDs, dados lógicos e arquivos Parquet permanecem iguais com a mesma versão, configuração e seed.
