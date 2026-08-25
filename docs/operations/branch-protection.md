# Branch protection e gate de merge

Configuração administrativa que protege `develop` e `main` do repositório
`Arthur-Diego/orquestrador-studio`. Não vive em arquivo versionado no GitHub; este documento
é a fonte reproduzível para aplicação e auditoria.

## Política

- `develop` recebe alterações somente por Pull Request, com os checks `build-and-test` e
  `task-id-check` verdes e a branch atualizada em relação à base.
- `main` é protegida contra push direto e recebe código somente por PR de promoção a partir
  de `develop`.
- Repositório de uma pessoa: `required_approving_review_count` é `0` (o GitHub não permite
  aprovar o próprio PR). A revisão humana acontece na leitura do corpo do PR (gate `ft-pr`)
  antes do merge. Ao entrar um segundo colaborador, subir para `1`.

Os nomes `build-and-test` e `task-id-check` são contrato operacional com
`.github/workflows/`; renomear o job exige atualizar a proteção.

## Aplicação via GitHub CLI

```bash
gh auth status

gh api --method PUT repos/Arthur-Diego/orquestrador-studio/branches/develop/protection --input - <<'JSON'
{
  "required_status_checks": {"strict": true, "contexts": ["build-and-test", "task-id-check"]},
  "enforce_admins": true,
  "required_pull_request_reviews": {"dismiss_stale_reviews": true, "required_approving_review_count": 0},
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON

gh api --method PUT repos/Arthur-Diego/orquestrador-studio/branches/main/protection --input - <<'JSON'
{
  "required_status_checks": null,
  "enforce_admins": true,
  "required_pull_request_reviews": {"dismiss_stale_reviews": true, "required_approving_review_count": 0},
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON
```

## Validação

```bash
gh api repos/Arthur-Diego/orquestrador-studio/branches/develop --jq '{name, protected}'
gh api repos/Arthur-Diego/orquestrador-studio/branches/main --jq '{name, protected}'
gh api repos/Arthur-Diego/orquestrador-studio/branches/develop/protection --jq '{required_status_checks, enforce_admins}'
```

Esperado: push direto em `develop`/`main` rejeitado; PR para `develop` só mergeável com os
dois checks verdes.
