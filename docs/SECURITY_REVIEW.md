# Revisão de segurança para publicação

## Parecer

**PASS após remediação.** A revisão não encontrou credenciais, chaves privadas, tokens,
senhas, caminhos pessoais, CPF válido, endereço de rede privada ou arquivo de dados
sensível no conteúdo publicável. Os dados industriais são integralmente sintéticos.

## Escopo verificado

- 150 arquivos rastreados antes dos novos materiais de publicação;
- todos os oito commits então alcançáveis pela `main`;
- nomes e extensões de arquivos com risco de segredo;
- conteúdo textual e URLs com credenciais embutidas;
- metadados de autoria dos commits;
- cinco screenshots PNG versionados;
- configuração do remoto e regras do `.gitignore`.

As buscas de alta confiança cobriram chaves privadas e formatos comuns de tokens AWS,
GitHub, OpenAI, Slack e Google, JWTs, URLs autenticadas e atribuições genéricas de
segredo. Possíveis sequências numéricas foram adicionalmente verificadas pelo algoritmo
de dígitos de CPF; nenhuma era válida.

## Achado e remediação

O endereço pessoal usado originalmente como autor dos commits estava exposto no
metadado Git. O conteúdo dos commits não possuía o endereço, mas o histórico permitia
consultá-lo.

Com autorização explícita do proprietário:

1. foi criado e verificado um bundle local temporário;
2. os oito commits foram reescritos para o endereço GitHub `noreply` da conta;
3. a árvore final foi comparada antes/depois e permaneceu idêntica;
4. a `main` foi atualizada com `--force-with-lease`;
5. referências e bundle temporários que continham os metadados antigos foram removidos;
6. a nova história foi varrida novamente e passou sem achados.

O GitHub alerta que reescritas mudam hashes e exigem novo clone ou rebase cuidadoso de
cópias anteriores. Também é possível que visualizações antigas permaneçam em caches ou
clones externos. Consulte a documentação oficial sobre
[remoção de dados sensíveis](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
e [e-mail de commits](https://docs.github.com/en/account-and-profile/how-tos/email-preferences/setting-your-commit-email-address?platform=windows).

## Prevenção adicionada

- o e-mail local deste repositório agora usa o endereço `noreply` do GitHub;
- `.gitignore` bloqueia arquivos de ambiente, certificados, chaves, cofres e arquivos
  comuns de credenciais, preservando apenas `.env.example`;
- `scripts/security_audit.ps1` repete a busca sem imprimir valores potencialmente
  sensíveis e falha com código diferente de zero quando encontra risco;
- materiais de publicação devem usar somente caminhos relativos e números cobertos pelo
  contrato `configs/portfolio_claims.json`.

Execute antes de cada publicação:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/security_audit.ps1 -History
python -m steelflow audit-portfolio
```

## Limitações

A busca por padrões reduz risco, mas não substitui rotação imediata se uma credencial
real for exposta, revisão humana ou secret scanning do provedor. Nenhum segredo foi
encontrado nesta revisão, portanto não houve credencial a revogar.
