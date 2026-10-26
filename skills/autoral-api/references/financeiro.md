# Pagamentos, reembolsos e assinaturas

## Pagamentos

Objeto pagamento:

| Campo | Tipo | Obs. |
|---|---|---|
| `id` | int | interno |
| `public_id` | string | UUID |
| `user_id`, `checkout_id`, `subscription_id` | int\|null | |
| `gateway` | string | `stripe`, `pagarme` (webhooks também mostram `pagarme`) |
| `method` | string | `card`, `pix`, `boleto`… |
| `status` | string | `pending`, `succeeded`, `failed`, `refunded` |
| `amount` | int | **centavos** (19990 = R$ 199,90) |
| `original_amount`, `discount_amount`, `gateway_fee`, `net_amount` | int | centavos |
| `currency` | string | ISO 4217 |
| `installments` | int | parcelas |
| `created_at`, `updated_at` | ISO 8601 | |

### GET /payments — `payments:read`
Cursor. Query: `per_page`, `cursor`, `status`, `gateway`, `user_id`. Sem filtro de data documentado: para relatório por período, itere (ordem é `id` desc) e pare quando `created_at` ficar antes do início do período.

### GET /payments/{payment} — `payments:read`

### POST /payments/{payment}/refunds — `payments:refund` · idempotência **obrigatória na prática**
Cria `RefundRequest`, aprova automaticamente, processa no gateway e **revoga o acesso** vinculado. Dispara `refund.created`.

| Campo | Tipo | Obs. |
|---|---|---|
| `reason` | string | vai para o audit log |
| `amount` | int | parcial em **centavos**; omitido = total |

```bash
curl https://$DOMINIO/api/v1/payments/5001/refunds \
  -H "Authorization: Bearer $AUTORAL_TOKEN" \
  -H "Idempotency-Key: refund-5001" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Cliente solicitou cancelamento"}'
```

Resposta **202**: `{"data": {"refund_request_id": 77, "payment_id": 5001, "status": "refunded"}}`.

Elegível só se: `status = succeeded`; sem RefundRequest pendente/processado; checkout com `allow_refund = true`; dentro de `refund_days_limit` (ver `GET /checkouts/{id}`). Senão 422 `payment_not_refundable`.

Antes de chamar: confirmar com o usuário (valor, aluno, motivo). Use chave determinística `refund-{payment_id}` para nunca reembolsar duas vezes.

## Assinaturas

Objeto assinatura: `id`, `user_id`, `checkout_id`, `gateway`, `status` (`active`, `trialing`, `past_due`, `canceled`), `amount` (**decimal string**, ex.: `"199.90"`), `currency`, `billing_period` (`month`, `year`…), `current_period_start`, `current_period_end`, `trial_ends_at`, `canceled_at`, `ended_at`, `cancel_at`.

### GET /subscriptions — `subscriptions:read`
Cursor. Query: `per_page`, `cursor`, `status`, `user_id`.

### GET /subscriptions/{subscription} — `subscriptions:read`

### DELETE /subscriptions/{subscription} — `subscriptions:cancel`
Cancela **imediatamente** no gateway, sem período de carência; aluno perde acesso. Irreversível.

Resposta **200** (não 204): `{"data": {"id": 9001, "status": "canceled", "canceled_at": "...", "ended_at": "..."}}`.

Erros: 422 `subscription_already_canceled`; 502 `gateway_cancel_failed` (tentar de novo em alguns minutos).

## Receitas

- **MRR aproximado**: `GET /subscriptions?status=active` (iterar) → somar `amount` normalizando `billing_period` (`year` ÷ 12). Lembrar que `amount` é decimal string.
- **Faturamento líquido**: `GET /payments?status=succeeded` → somar `net_amount` (centavos) por `currency`.
- **Inadimplência**: `GET /subscriptions?status=past_due` ou webhooks `subscription.past_due` / `subscription.payment_failed`.
- Para reação em tempo real prefira webhooks (`payment.approved`, `refund.created`, `subscription.*`) a polling.
