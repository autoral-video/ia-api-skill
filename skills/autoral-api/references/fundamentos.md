# Fundamentos da API autoral.me

## Sumário
- Base URL e autenticação
- Tokens e planos
- Escopos
- Envelope de erro e códigos
- Rate limiting
- Paginação
- Idempotência
- Request ID
- Segurança

## Base URL e autenticação

```
https://{dominio-da-escola}/api/v1
```

`{dominio-da-escola}` = subdomínio `*.autoral.me` ou domínio próprio. O tenant vem do **token**, não do `Host`; um token nunca acessa outra tenant.

Todo request autenticado:

```http
Authorization: Bearer aut_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Accept: application/json
Content-Type: application/json   (em POST/PATCH/DELETE com corpo)
```

Formato do token: prefixo `aut_` + 40 caracteres de entropia + 8 de CRC32. Guardado como SHA-256 no servidor: só é exibido uma vez, na criação.

Ordem de validação no servidor: token existe → não revogado (401 `token_revoked`) → não expirado (401 `token_expired`) → tenant ativo (403 `tenant_inactive`) → IP permitido (403 `ip_not_allowed`) → escopo da rota (403) → rate limit (429).

## Tokens e planos

- Criados **apenas no painel** (Configurações → Tokens de API), por Super Admin. Não há endpoint para criar tokens.
- Campos na criação: `name`, `description`, `scopes` (imutáveis depois), `expires_at` opcional, `allowed_ips` opcional (IPv4/IPv6/CIDR, um por linha).
- Revogação: imediata, irreversível, soft (fica para auditoria). Revogados/expirados não contam no limite.

| Plano | API | Máx. tokens | Requests/min |
|---|---|---|---|
| Free | ❌ (402) | 0 | — |
| Lite | ✅ | 3 | 60 |
| Pro | ✅ | 10 | 300 |
| Scale | ✅ | 50 | 1.200 |
| Custom | ✅ | sob consulta | sob consulta |

Agência com várias escolas: um token por tenant.

IP allowlist: bom para servidor com IP fixo; **não** usar com Zapier/Make, Lambda/Cloud Run sem NAT, redes residenciais/móveis.

## Escopos

| Escopo | Permite |
|---|---|
| `courses:read` | Listar/ver cursos, listar módulos do curso |
| `courses:write` | (reservado, sem endpoints) |
| `modules:read` | Listar aulas de um módulo |
| `lessons:read` | Ver aula |
| `media-library:read` / `:write` | Listar/ver · enviar/remover arquivos da Biblioteca de Mídia |
| `students:read` / `:write` | Listar/ver alunos · conceder/revogar acesso |
| `access:read` / `:write` | Listar/ver matrículas · criar/remover matrículas |
| `payments:read` | Listar/ver pagamentos |
| `payments:refund` | Reembolsar (**sensível**) |
| `subscriptions:read` | Listar/ver assinaturas |
| `subscriptions:cancel` | Cancelar no gateway (**sensível**) |
| `coupons:read` / `:write` | Listar/ver · criar/remover cupons |
| `leads:read` / `:write` | Listar/ver · criar leads |
| `checkouts:read` | Listar/ver checkouts |
| `products:read` / `:write` | Listar/ver · criar/remover produtos |
| `offers:read` / `:write` | Listar/ver · criar/remover ofertas |
| `quiz-funnels:read` / `:write` | Listar/ver/estatísticas · criar/atualizar/publicar/remover quizzes |
| `pages:read` / `:write` | Listar/ver · criar/atualizar/publicar/remover páginas públicas |
| `certificates:read` | Listar/ver certificados |
| `questions:read` | Listar/ver perguntas de aulas |
| `webhooks:read` / `:write` | Listar/ver · criar/remover webhooks |

Combinações recomendadas (menor privilégio):

| Integração | Escopos |
|---|---|
| Dashboard somente leitura | `courses:read modules:read lessons:read students:read payments:read subscriptions:read coupons:read leads:read checkouts:read certificates:read` |
| Matrícula (n8n/Zapier/CRM) | `students:read students:write courses:read` |
| Formulário externo → lead | `leads:write checkouts:read` |
| Gestão financeira | `payments:read payments:refund subscriptions:read subscriptions:cancel` |
| Geração de quizzes (IA) | `quiz-funnels:read quiz-funnels:write checkouts:read` |
| CMS / landing pages | `pages:read pages:write` (+ `media-library:write` para imagens) |
| Provisionar webhooks | `webhooks:read webhooks:write` |

## Envelope de erro e códigos

```json
{
  "error": {
    "type": "validation_error",
    "title": "Mensagem legível em pt-BR.",
    "status": 422,
    "code": "field.specific.code",
    "errors": { "campo": ["mensagem"] },
    "request_id": "uuid-v4"
  }
}
```

`errors` só em `validation_error`. Alguns erros trazem extras: `retry_after` (429), `problems` (quiz não publicável).

| HTTP | Significado |
|---|---|
| 200 / 201 / 202 / 204 | OK / Criado / Aceito (ex.: reembolso) / Sem conteúdo (DELETE) |
| 400 | Corpo malformado |
| 401 | Token ausente, inválido, revogado, expirado |
| 402 | Limite do plano (`plan_limit_exceeded`) ou plano sem API |
| 403 | Sem escopo, IP bloqueado, tenant inativo, recurso fora do plano |
| 404 | Inexistente **ou de outro tenant** |
| 422 | Validação / regra de negócio |
| 429 | Rate limit |
| 500 / 502 | Erro interno / falha no gateway externo |

| `type` ou `code` | Status | Causa / ação |
|---|---|---|
| `missing_token` | 401 | Sem header `Authorization` |
| `invalid_token` | 401 | Token mal-formado ou inexistente |
| `token_revoked` | 401 | Revogado — pedir novo token |
| `token_expired` | 401 | Passou de `expires_at` |
| `tenant_inactive` | 403 | Conta suspensa |
| `ip_not_allowed` | 403 | IP fora da allowlist |
| (403 sem code) / `authorization_error` | 403 | Falta escopo |
| `plan_feature_unavailable` | 403 | Plano não inclui o recurso (ex.: mídia, quizzes, páginas no plano Autoral Store) |
| `plan_limit_exceeded` | 402 | Limite do plano (produtos, páginas…) |
| `platform_limit_exceeded` | 422 | Limite de segurança (200 quizzes, 200 páginas, 500 produtos, 500 ofertas) |
| `invalid_idempotency_key` | 422 | Chave fora de `^[a-zA-Z0-9_-]{8,128}$` |
| `validation_error` | 422 | Ver `errors` |
| `quiz_not_publishable` | 422 | Ver `problems` |
| `payment_not_refundable` | 422 | Pagamento inelegível |
| `subscription_already_canceled` | 422 | Já cancelada |
| `upload_rejected` | 422 | Arquivo grande demais, MIME inválido ou armazenamento esgotado (motivo em `title`) |
| `gateway_cancel_failed` | 502 | Gateway falhou — tentar de novo em alguns minutos |
| `rate_limited` | 429 | Esperar `Retry-After` |
| `not_found` | 404 | — |

## Rate limiting

Por **token + tenant** (não por IP). Limite = plano (veja `GET /me` → `data.plan.api_rate_limit_per_minute`). Vários tokens não somam cota de forma útil — limite de infra do tenant continua.

Headers: `Retry-After` (segundos), `X-RateLimit-Limit`, `X-RateLimit-Remaining`.

Estratégia: em 429 esperar `Retry-After` × 2^tentativa; em carga em massa, espaçar requisições (`60 / limite` segundos) e usar `Idempotency-Key`.

## Paginação

`per_page`: padrão 25, máximo 100 (acima é truncado sem erro).

**Por página (length-aware)** — `courses`, `courses/{id}/modules`, `modules/{id}/lessons`, `coupons`, `webhooks`, `products`, `offers`, `media`, `quiz-funnels`, `pages`. Parâmetro `page`.

```json
{
  "data": [],
  "links": { "first": "…?page=1", "last": "…?page=10", "prev": "…", "next": "…?page=3" },
  "meta": { "current_page": 2, "from": 26, "last_page": 10, "per_page": 25, "to": 50, "total": 247 }
}
```

**Cursor** — `students`, `access`, `payments`, `subscriptions`, `leads`, `checkouts`, `certificates`, `questions`. Parâmetro `cursor`.

```json
{
  "data": [],
  "path": "…/payments",
  "per_page": 50,
  "next_cursor": "eyJpZCI6MTIzfQ",
  "next_page_url": "…/payments?cursor=eyJpZCI6MTIzfQ&per_page=50",
  "prev_cursor": null,
  "prev_page_url": null
}
```

Iteração genérica: siga `next_page_url` (cursor) ou `links.next` (página) até `null`. Os filtros já vêm embutidos nessas URLs.

Ordem: `id` decrescente (mais recente primeiro). Sem ordenação customizada.

## Idempotência

Header opcional `Idempotency-Key` em POST. Documentado para: `POST /students/{id}/access`, `/access`, `/payments/{id}/refunds`, `/coupons`, `/leads`, `/webhooks`, `/products`, `/offers`, `/media`, `/quiz-funnels`, `/pages`. DELETE é idempotente por natureza.

- Formato: `^[a-zA-Z0-9_-]{8,128}$` (UUID v4 serve).
- Cache 24 h por `(tenant, token, chave, sha256(método|rota|corpo))` — mesmo key + corpo diferente = nova execução.
- Replay devolve a resposta original com header `Idempotent-Replay: true`.
- Só respostas < 500 são cacheadas; 5xx pode ser retentado com a mesma chave.

Gere chaves **determinísticas** a partir da operação de negócio quando possível (`enroll-{user}-{course}-{pedido}`, `lead-{form}-{id_externo}`, `refund-{payment}`), para que reprocessar a mesma fila não duplique.

## Request ID

Toda resposta tem `X-Request-Id`. Você pode enviar o seu (8–64 chars `[a-zA-Z0-9-]`) e o servidor reaproveita — útil para tracing ponta a ponta. Em erro também vem em `error.request_id`. Ao reportar bug ao suporte: `request_id`, endpoint, corpo (sem segredos), timestamp UTC, **ID** do token (nunca o valor).

## Segurança

- Um token por integração, escopo mínimo, `expires_at` em testes (1–7 dias) e integrações beta (30 dias); produção sem expiração com revisão semestral.
- Guardar em `.env` não commitado, secrets manager, GitHub/GitLab secrets, cofres do n8n/Zapier. Nunca em código, logs, chat, URL.
- Rotação: criar novo → trocar na integração → conferir `last_used_at` subindo (via `GET /me`) → revogar o antigo.
- Vazamento: revogar já, auditar ações no período (sobretudo `students:write`, `payments:refund`), reverter efeitos, LGPD (DPO/ANPD) se houver dados pessoais.
- Token com `pages:write` publica HTML arbitrário no domínio da escola — só em integrações confiáveis.
