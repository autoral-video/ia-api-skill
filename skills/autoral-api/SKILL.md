---
name: autoral-api
description: Integra projetos com a API REST pública da autoral.me (plataforma de cursos online) — cursos, módulos, aulas, alunos, matrículas, pagamentos, reembolsos, assinaturas, cupons, leads, checkouts, produtos, ofertas, certificados, perguntas, biblioteca de mídia, quizzes de venda, páginas/landing pages e webhooks. Use sempre que o usuário mencionar autoral.me, Autoral, tokens `aut_`, ou pedir para matricular alunos, capturar leads, criar cupons, publicar páginas ou quizzes, receber/validar webhooks, sincronizar vendas com CRM/ERP/n8n/Zapier, ou escrever código que chame `/api/v1` de uma escola na autoral.me.
---

# API autoral.me

API REST JSON, versionada em `/api/v1`, multi-tenant, autenticada por Bearer token (`aut_...`) com escopos `recurso:ação`.

## Configuração

| Variável | Exemplo | Uso |
|---|---|---|
| `AUTORAL_BASE_URL` | `https://escola.autoral.me` | Domínio da escola (ou domínio próprio). `/api/v1` é acrescentado. |
| `AUTORAL_TOKEN` | `aut_9W6E...` | Token criado em **Configurações → Tokens de API** (só Super Admin, planos Lite/Pro/Scale). |
| `AUTORAL_WEBHOOK_SECRET` | — | Secret do webhook, para validar `X-Webhook-Signature`. |

O tenant é resolvido **pelo token**, não pelo domínio. Recursos de outro tenant retornam 404.

Nunca escreva o token em código, commits, logs, query string ou na resposta ao usuário. Leia de variável de ambiente / secrets manager. Se o usuário colar um token no chat, use-o só via variável de ambiente e recomende rotação depois.

## Fluxo de trabalho

1. **Validar o token primeiro**: `GET /me` (sem escopo) devolve `abilities`, plano e `api_rate_limit_per_minute`. Confira se os escopos necessários existem antes de planejar a integração — escopos não são editáveis; faltou, o usuário precisa criar outro token no painel.
2. **Abrir a referência do domínio** (tabela abaixo) para parâmetros exatos. Não invente campos: se não está na referência, a API não documenta.
3. **Escrever writes com `Idempotency-Key`** (POST) e tratar o envelope de erro (`error.type`, `error.code`, `error.request_id`).
4. **Iterar listagens até o fim** seguindo `next_page_url` (cursor) ou `links.next` (página).

Para chamadas ad-hoc / exploração use o cliente incluso (só stdlib Python 3.8+):

```bash
python3 scripts/autoral.py me
python3 scripts/autoral.py get /courses --query per_page=100 --all
python3 scripts/autoral.py post /leads --data '{"checkout_id":5,"name":"João","email":"joao@x.com"}'
python3 scripts/autoral.py patch /pages/4 --data @pagina.json
python3 scripts/autoral.py delete /access/1234 --data '{"reason":"Encerramento"}'
python3 scripts/autoral.py upload --file capa.png --field folder_id=3
python3 scripts/autoral.py verify-signature --body-file corpo.json --signature <hex>
```

O script faz retry em 429 (respeita `Retry-After`), gera `Idempotency-Key` automática em POST, imprime `X-Request-Id` no stderr e nunca segue URLs de outro host com o token. Para código de produção do usuário, use os modelos em [references/clientes.md](references/clientes.md).

## Mapa de referências

| Preciso de… | Arquivo |
|---|---|
| Tokens, escopos, erros, rate limit, paginação, idempotência, request-id | [references/fundamentos.md](references/fundamentos.md) |
| `/me`, cursos, módulos, aulas, biblioteca de mídia | [references/conteudo.md](references/conteudo.md) |
| Alunos, matrículas (access), certificados, perguntas | [references/alunos-e-acesso.md](references/alunos-e-acesso.md) |
| Pagamentos, reembolsos, assinaturas | [references/financeiro.md](references/financeiro.md) |
| Produtos, ofertas, checkouts, cupons, leads | [references/vendas.md](references/vendas.md) |
| Quizzes de venda (criar, publicar, estatísticas) | [references/quiz-funnels.md](references/quiz-funnels.md) |
| Páginas públicas / landing pages (HTML) | [references/paginas.md](references/paginas.md) |
| Webhooks: CRUD, eventos, payloads, assinatura HMAC | [references/webhooks.md](references/webhooks.md) |
| Clientes prontos (TypeScript, Python, PHP/Laravel) e receptor de webhook | [references/clientes.md](references/clientes.md) |

## Índice rápido de endpoints

| Método e rota | Escopo |
|---|---|
| `GET /me` | — |
| `GET /courses` · `GET /courses/{id}` · `GET /courses/{id}/modules` | `courses:read` |
| `GET /modules/{id}/lessons` | `modules:read` |
| `GET /lessons/{id}` | `lessons:read` |
| `GET /media` · `GET /media/{id}` | `media-library:read` |
| `POST /media` (multipart) · `DELETE /media/{id}` | `media-library:write` |
| `GET /students` · `GET /students/{id}` | `students:read` |
| `POST /students/{id}/access` · `DELETE /students/{id}/access/{access}` | `students:write` |
| `GET /access` · `GET /access/{id}` | `access:read` |
| `POST /access` · `DELETE /access/{id}` | `access:write` |
| `GET /payments` · `GET /payments/{id}` | `payments:read` |
| `POST /payments/{id}/refunds` | `payments:refund` ⚠️ |
| `GET /subscriptions` · `GET /subscriptions/{id}` | `subscriptions:read` |
| `DELETE /subscriptions/{id}` | `subscriptions:cancel` ⚠️ |
| `GET /coupons` · `GET /coupons/{id}` | `coupons:read` |
| `POST /coupons` · `DELETE /coupons/{id}` | `coupons:write` |
| `GET /leads` · `GET /leads/{id}` | `leads:read` |
| `POST /leads` | `leads:write` |
| `GET /checkouts` · `GET /checkouts/{id}` | `checkouts:read` |
| `GET /products` · `GET /products/{id}` | `products:read` |
| `POST /products` · `DELETE /products/{id}` | `products:write` |
| `GET /offers` · `GET /offers/{id}` | `offers:read` |
| `POST /offers` · `DELETE /offers/{id}` | `offers:write` |
| `GET /certificates` · `GET /certificates/{id}` | `certificates:read` |
| `GET /questions` · `GET /questions/{id}` | `questions:read` |
| `GET /quiz-funnels` · `GET /quiz-funnels/{id}` · `GET /quiz-funnels/{id}/stats` | `quiz-funnels:read` |
| `POST /quiz-funnels` · `PATCH /quiz-funnels/{id}` · `DELETE /quiz-funnels/{id}` | `quiz-funnels:write` |
| `GET /pages` · `GET /pages/{id}` | `pages:read` |
| `POST /pages` · `PATCH /pages/{id}` · `DELETE /pages/{id}` | `pages:write` |
| `GET /webhooks` · `GET /webhooks/{id}` | `webhooks:read` |
| `POST /webhooks` · `DELETE /webhooks/{id}` | `webhooks:write` |

## Ações que exigem confirmação explícita do usuário

Antes de executar contra uma conta real, mostre o que será feito e peça confirmação para:

- `POST /payments/{id}/refunds` — devolve dinheiro no gateway e revoga o acesso ligado ao pagamento.
- `DELETE /subscriptions/{id}` — cancela no gateway, irreversível, aluno perde acesso na hora.
- `DELETE /media/{id}` e `DELETE /pages/{id}` — remoção definitiva.
- `DELETE /products/{id}` (apaga também as ofertas) e `DELETE /offers/{id}` — podem quebrar checkouts ativos.
- `DELETE /quiz-funnels/{id}` — link sai do ar; slug fica reservado para sempre.
- Publicar página/quiz (`is_published: true`, `status: "published"`) ou trocar `slug` (o link antigo para de funcionar).
- Qualquer operação em massa (loops de matrícula, cupons, leads): rode primeiro em 1 item.

## Armadilhas frequentes

- **Dinheiro em formatos diferentes**: `payments.amount` e `refund.amount` = inteiro em **centavos**; `subscriptions.amount`, `offers.price`, `coupons.discount_value` = decimal (string na resposta); quiz stats `revenue_cents` = centavos; payload de webhook `amount` = decimal (`497.00`).
- **Duas paginações**: cursor (`students`, `access`, `payments`, `subscriptions`, `leads`, `checkouts`, `certificates`, `questions`) vs. página (`courses`, `modules/…/lessons`, `coupons`, `webhooks`, `products`, `offers`, `media`, `quiz-funnels`, `pages`). `per_page` máx. 100 (acima é truncado em silêncio). Ordem fixa: `id` decrescente (páginas: `order`, `title`). Sem `?sort=`.
- **Não existe via API**: criar/editar tokens, criar checkout, editar curso/módulo/aula, editar cupom/produto/oferta (só criar e remover), editar perguntas/opções/resultados de quiz já criado.
- **Matrícula**: `POST /students/{id}/access` e `POST /access` são equivalentes; se já houver matrícula ativa, estende/vira vitalícia em vez de duplicar. Revogar é soft (`is_active=false`).
- **Lead**: `checkout_id` obrigatório — liste checkouts antes. IP/User-Agent são capturados da request; em integração server-side eles serão do seu servidor.
- **Webhook**: `secret` aparece só na resposta de criação; não há como ler depois. Assinatura no header `X-Webhook-Signature` (HMAC-SHA256 hex do corpo bruto).
- **DELETE com corpo**: revogar acesso aceita `{"reason": "..."}` no body — algumas libs HTTP descartam body em DELETE; confirme que o seu cliente envia.
- **Upload de mídia**: `multipart/form-data`, envie `Accept: application/json` para receber erros em JSON.
- **Erro 403 sem `code`** = falta escopo. 402 = limite do plano. 404 em ID que "existe" = outro tenant ou recurso removido.
- Sempre registre `X-Request-Id` / `error.request_id` em falhas — é o que o suporte da autoral.me pede.
