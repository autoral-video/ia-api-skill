# Webhooks (outgoing)

A plataforma faz POST para a sua URL quando eventos acontecem. Também configuráveis no painel em **Admin → Configurações → Webhooks**, onde fica o histórico de entregas e o botão de reprocessar.

## Endpoints

Objeto webhook: `id`, `name`, `url`, `events` (string[]), `is_active`, `created_at`, `updated_at`. O `secret` nunca é devolvido (exceto na criação, se gerado pelo servidor).

- `GET /webhooks` — `webhooks:read`. Por página. Query: `per_page`, `active`.
- `GET /webhooks/{webhook}` — `webhooks:read`.
- `POST /webhooks` — `webhooks:write`, idempotência suportada.

  | Campo | Tipo | Obs. |
  |---|---|---|
  | `name` | string | **obrig.**, 1–120 |
  | `url` | string | **obrig.**, HTTPS pública (IPs privados/hosts internos recusados — anti-SSRF) |
  | `secret` | string | 32–255; gerado se omitido |
  | `events` | string[] | **obrig.** |
  | `is_active` | bool | padrão `true` |

  **Prefira gerar o secret você mesmo** (`openssl rand -hex 32`) e enviá-lo: assim ele já está no seu cofre e não depende de capturar a resposta. Se omitido, anote o secret da resposta 201 — não há como lê-lo depois.
- `DELETE /webhooks/{webhook}` — `webhooks:write`. 204. Para trocar o secret: criar novo, migrar, remover o antigo.

Não há PATCH: mudar eventos/URL = criar outro e apagar o antigo.

## Eventos

A referência do endpoint `POST /webhooks` lista 8 eventos; a Central de Ajuda documenta 23. Se a API recusar algum com 422, use o painel ou reduza aos 8 da primeira tabela.

| Evento (referência da API) | Quando |
|---|---|
| `payment.approved` | Pagamento único aprovado |
| `payment.failed` | Pagamento recusado/erro |
| `subscription.created` | Primeira cobrança da assinatura aprovada |
| `subscription.updated` | Mudança de status |
| `subscription.canceled` | Cancelada |
| `student.enrolled` | Acesso concedido |
| `access.revoked` | Acesso revogado |
| `refund.created` | Reembolso processado |

| Eventos adicionais (Central de Ajuda) | Quando |
|---|---|
| `payment.pending` | PIX/boleto gerado, aguardando |
| `payment.chargeback` | Contestação |
| `subscription.renewed` | Renovação aprovada |
| `subscription.past_due` | Entrou em atraso |
| `subscription.payment_failed` | Falha em fatura de renovação |
| `enrollment.expired` | Acesso temporário expirou |
| `certificate.issued` | Certificado emitido |
| `waitlist.joined` / `waitlist.promoted` / `waitlist.expired` | Lista de espera de turma |
| `lesson.completed` | Aula concluída |
| `course.completed` | 100% do curso |
| `assignment.submitted` / `assignment.reviewed` | Tarefas de turma |
| `community.post_created` | Post na comunidade |

## Formato da entrega

```http
POST /seu-endpoint
Content-Type: application/json
X-Webhook-Event: payment.approved
X-Webhook-Id: evt_01hj8q1k2t3r5v7x9z2b4d6f_12
X-Webhook-Signature: <hmac-sha256 hex>

{
  "id": "evt_01hj8q1k2t3r5v7x9z2b4d6f_12",
  "event": "payment.approved",
  "created_at": "2026-06-16T12:00:00Z",
  "data": { }
}
```

Objeto `user` padrão (na maioria dos eventos): `{"id", "email", "name", "phone", "phone_country"}` — `phone` pode ser null. Eventos de turma trazem `class_id` / `class_name`.

Em `data`, IDs como `payment_id`, `subscription_id`, `access_id` aparecem como string nos exemplos — trate como string ou converta com cuidado. `amount` é **decimal** (`497.00`), não centavos.

### Payloads (`data`)

| Evento | Campos |
|---|---|
| `payment.approved` | `payment_id`, `user` (+ `class_id`, `class_name`), `amount`, `currency`, `gateway` |
| `payment.pending` | `gateway_payment_id`, `checkout_id`, `customer_email`, `user` (null p/ lead anônimo), `amount`, `currency`, `payment_method`, `gateway` |
| `payment.failed` | `gateway_payment_id`, `checkout_id`, `customer_email`, `user` (pode ser null), `amount`, `currency`, `gateway` |
| `payment.chargeback` | `payment_id`, `user`, `amount`, `currency`, `gateway` |
| `subscription.created` | `subscription_id`, `user` (+ turma), `checkout_id`, `amount`, `currency`, `gateway` |
| `subscription.updated` | `subscription_id`, `user`, `status`, `previous_status`, `gateway` |
| `subscription.renewed` | `subscription_id`, `payment_id`, `user`, `amount`, `currency`, `gateway` |
| `subscription.past_due` | `subscription_id`, `user`, `status`, `previous_status`, `gateway` |
| `subscription.payment_failed` | `subscription_id`, `user`, `invoice_id`, `amount`, `currency`, `gateway` |
| `subscription.canceled` | `subscription_id`, `user`, `amount`, `currency`, `gateway` |
| `student.enrolled` | `access_id`, `user`, `course` {`id`,`name`}, `type` (`lifetime`/`temporary`/`subscription`/`trial`), `granted_by` (`payment`/`admin`/`import`…) |
| `access.revoked` | `access_id`, `user`, `course_id`, `reason` |
| `enrollment.expired` | `access_id`, `user`, `course`, `expired_at` |
| `refund.created` | `refund_request_id`, `payment_id`, `user`, `amount`, `external_refund_id`, `gateway` (iniciado pela operadora: `amount_refunded` no lugar de `refund_request_id`/`external_refund_id`) |
| `certificate.issued` | `certificate_id`, `certificate_number`, `verification_code`, `user`, `course` |
| `waitlist.*` | `waitlist_entry_id`, `class_id`, `class_name`, `position`, `status` (`waiting`/`promoted`/`expired`), `user` (`id` null se ainda sem conta) |
| `lesson.completed` | `lesson` {`id`,`title`}, `course`, `user` |
| `course.completed` | `course`, `user` |
| `assignment.submitted` | `submission_id`, `assignment` {`id`,`title`,`class_id`,`class_name`}, `user`, `is_late`, `submitted_at` |
| `assignment.reviewed` | `review_id`, `submission_id`, `status` (`approved`/`needs_revision`/`rejected`), `score`, `assignment`, `user` (aluno) |
| `community.post_created` | `post_id`, `group` {`id`,`class_id`,`class_name`}, `user` |

## Validar assinatura

`X-Webhook-Signature` = HMAC-SHA256 em **hex** do **corpo bruto** com o secret. Calcule antes de qualquer parse/reserialização; compare em tempo constante; rejeite com 401 se não bater.

(A página de boas práticas da documentação cita `X-Signature`; o header real descrito em "Segurança e entregas" é `X-Webhook-Signature`. Se não chegar, inspecione os headers recebidos.)

Exemplos de receptor em [clientes.md](clientes.md). Teste local com o script:

```bash
AUTORAL_WEBHOOK_SECRET=... python3 scripts/autoral.py verify-signature --body-file corpo.json --signature <hex>
```

## Entrega e reenvio

- Responder **2xx** em até **10 s**. Qualquer outro status ou timeout = falha.
- Até 5 tentativas, backoff ≈ 30 s, 2 min, 8 min, 32 min, 2,6 h; depois **Descartado** (reprocessável no painel).
- Status no painel: Pendente, Entregue, Falhou, Descartado.

Boas práticas do receptor:
1. Validar assinatura.
2. **Deduplicar por `id`** (`evt_...`) — reenvios mandam o mesmo id. Guarde ids processados (tabela com unique, Redis `SETNX` com TTL de alguns dias).
3. Responder 200 rápido e processar em fila/background (10 s de timeout).
4. Não confiar na ordem de chegada; use `created_at` e/ou consulte a API (`GET /payments/{id}`) quando o estado importar.
