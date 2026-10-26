# Produtos, ofertas, checkouts, cupons e leads

Modelo: **Curso** → **Produto** (SKU ligado a um curso) → **Ofertas** (preço/forma de cobrança) → **Checkout** (página de venda, aponta para uma oferta). Checkouts só são criados no painel; pela API dá para criar produto e oferta e depois o usuário liga a oferta a um checkout no painel.

Nenhum destes recursos tem endpoint de edição (PATCH): só criar, ler e remover.

## Produtos

Objeto: `id`, `name`, `description`, `course_id`, `is_active`, `offers_count`, `created_at`, `updated_at`.

- `GET /products` — `products:read`. Por página. Query: `per_page`, `page`, `course_id`, `active`.
- `GET /products/{product}` — `products:read`.
- `POST /products` — `products:write`, idempotência suportada.

  | Campo | Tipo | Obs. |
  |---|---|---|
  | `name` | string | **obrig.**, 1–120 |
  | `description` | string | até 2000 |
  | `course_id` | int | **obrig.**, do tenant |
  | `is_active` | bool | padrão `true` |

  Erros: 402 `plan_limit_exceeded` (`max_products` do plano), 422 (`course_id` inválido). Limite de plataforma: 500 produtos.
- `DELETE /products/{product}` — `products:write`. Soft delete **em cascata nas ofertas**. Checkouts que usam essas ofertas param. 204.

## Ofertas

Objeto: `id`, `product_id`, `name`, `payment_type` (`one_time` | `subscription`), `price` (decimal string), `currency` (uppercase), `billing_period` (`month` | `quarter` | `semester` | `year`, só assinatura), `schedule_iterations` (nº de cobranças antes de encerrar, ou null), `is_active`, `created_at`.

- `GET /offers` — `offers:read`. Por página. Query: `per_page`, `page`, `product_id`, `active`.
- `GET /offers/{offer}` — `offers:read`.
- `POST /offers` — `offers:write`, idempotência suportada.

  | Campo | Tipo | Obs. |
  |---|---|---|
  | `product_id` | int | **obrig.** |
  | `name` | string | **obrig.**, 1–120 |
  | `payment_type` | string | **obrig.** `one_time` / `subscription` |
  | `price` | number | **obrig.**, decimal ≥ 0 (199.90, **não** centavos) |
  | `currency` | string | **obrig.**, ISO 4217 (`BRL`) |
  | `billing_period` | string | obrigatório se `subscription` |
  | `schedule_iterations` | int | parcelamento com fim (ex.: 12) |
  | `is_active` | bool | padrão `true` |

  Limites: 50 ofertas por produto, 500 por tenant.
- `DELETE /offers/{offer}` — `offers:write`. Soft delete. Se ligada a checkout ativo, o checkout para de funcionar. 204.

## Checkouts — `checkouts:read` (somente leitura)

Objeto: `id`, `name`, `slug` (URL pública), `course_id`, `offer_id`, `class_id`, `access_type` (`lifetime` | `temporary` | `subscription`), `is_active`, `sales_count`, `payment_methods` (ex.: `["card","pix","boleto"]`), `allow_refund`, `refund_days_limit`.

- `GET /checkouts` — cursor. Query: `per_page`, `active`.
- `GET /checkouts/{checkout}`.

Os IDs de checkout são necessários em `POST /leads` (`checkout_id`) e nos resultados de quiz (`checkout_ids`). Link público de compra: `https://{dominio}/checkout/{slug}`.

## Cupons

Objeto: `id`, `code` (uppercase), `name`, `discount_type` (`percentage` | `fixed`), `discount_value` (decimal string), `usage_limit`, `per_customer_limit`, `usage_count`, `single_use`, `is_active`, `starts_at`, `expires_at`, `applies_to_all_products`.

- `GET /coupons` — `coupons:read`. Por página. Query: `per_page`, `page`, `active`.
- `GET /coupons/{coupon}` — `coupons:read`.
- `POST /coupons` — `coupons:write`, idempotência suportada.

  | Campo | Tipo | Obs. |
  |---|---|---|
  | `code` | string | **obrig.**, 1–50, `[A-Z0-9_-]`, salvo em maiúsculas, único no tenant |
  | `name` | string | nome amigável |
  | `discount_type` | string | **obrig.** `percentage` / `fixed` |
  | `discount_value` | number | **obrig.** 25 = 25% ou R$ 25,00 |
  | `usage_limit` | int | total |
  | `per_customer_limit` | int | por cliente |
  | `single_use` | bool | |
  | `is_active` | bool | padrão `true` |
  | `starts_at`, `expires_at` | data ISO | `expires_at` > `starts_at` |
  | `applies_to_all_products` | bool | padrão `true` |

  Código duplicado → 422 `errors.code`. Para cupons únicos por cliente, gere códigos aleatórios (ex.: `VIP-7F3K9Q`) e trate 422 gerando outro.
- `DELETE /coupons/{coupon}` — `coupons:write`. Soft delete; usos passados preservados. 204.

## Leads

Objeto: `id`, `checkout_id`, `name`, `email`, `phone`, `payment_method`, `status` (`pending` | `abandoned` | `completed`), `converted_at`, `created_at`.

- `GET /leads` — `leads:read`. Cursor. Query: `per_page`, `cursor`, `status`, `checkout_id`.
- `GET /leads/{lead}` — `leads:read`.
- `POST /leads` — `leads:write`, idempotência suportada. Cria com `status=pending`; entra em sequências de e-mail e automação de carrinho abandonado.

  | Campo | Tipo | Obs. |
  |---|---|---|
  | `checkout_id` | int | **obrig.**, do tenant |
  | `name` | string | **obrig.**, 1–120 |
  | `email` | string | **obrig.**, até 180 |
  | `phone` | string | até 32 (formato E.164 recomendado: `+5511999999999`) |
  | `payment_method` | string | até 32 |
  | `metadata` | object | livre: UTMs, referrer, id externo |

  IP e User-Agent são capturados da própria request — não envie no corpo.

```bash
curl https://$DOMINIO/api/v1/leads \
  -H "Authorization: Bearer $AUTORAL_TOKEN" \
  -H "Idempotency-Key: lead-form-contato-8812" \
  -H "Content-Type: application/json" \
  -d '{"checkout_id": 5, "name": "João Silva", "email": "joao@example.com",
       "phone": "+5511999999999",
       "metadata": {"utm_source": "facebook", "utm_campaign": "blackfriday"}}'
```

Formulário em site: **nunca** chame a API direto do navegador (exporia o token). Faça o form postar para o seu backend/serverless, que chama `POST /leads`.

## Receita: lançar oferta nova

1. `GET /courses` → `course_id`.
2. `POST /products` `{name, course_id}` → `product_id`.
3. `POST /offers` `{product_id, name, payment_type, price, currency[, billing_period]}`.
4. Usuário vincula a oferta a um checkout no painel (não há API).
5. Opcional: `POST /coupons` para a campanha; `POST /quiz-funnels` ou `POST /pages` apontando para o checkout.
