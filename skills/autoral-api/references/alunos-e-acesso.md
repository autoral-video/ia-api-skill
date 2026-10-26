# Alunos, matrículas, certificados e perguntas

## Alunos

Objeto aluno (user com role `student`): `id`, `name`, `email`, `phone`, `phone_country`, `email_verified_at`, `last_login_at`, `active_accesses_count`, `created_at`.

### GET /students — `students:read`
Cursor. Query: `per_page`, `cursor`. Não há filtro por e-mail documentado: para achar um aluno pelo e-mail, itere a lista (e guarde cache local `email → id`).

### GET /students/{student} — `students:read`

### POST /students/{student}/access — `students:write` · idempotência suportada
Matricula o aluno num curso. Se já existe matrícula ativa para `(aluno, curso)`, **estende** a expiração ou faz upgrade para vitalício. Dispara webhook `student.enrolled`.

| Campo | Tipo | Obs. |
|---|---|---|
| `course_id` | int | **obrigatório**, do tenant |
| `type` | string | **obrigatório**: `lifetime`, `temporary`, `subscription` |
| `duration` | string | `monthly`, `quarterly`, `semiannual`, `annual` (para `temporary`/`subscription`) |
| `days` | int | dias customizados; sobrepõe `duration` |
| `class_id` | int | turma (opcional) |
| `notes` | string | auditoria, ex.: "Cortesia comercial" |

```bash
curl https://$DOMINIO/api/v1/students/42/access \
  -H "Authorization: Bearer $AUTORAL_TOKEN" \
  -H "Idempotency-Key: enroll-42-course-1-pedido-981" \
  -H "Content-Type: application/json" \
  -d '{"course_id": 1, "type": "temporary", "duration": "annual"}'
```

Resposta 201 = objeto matrícula (abaixo). 422 com `errors.course_id` se curso não existe.

### DELETE /students/{student}/access/{access} — `students:write`
Soft revoke (`is_active=false`, histórico preservado). Corpo opcional `{"reason": "..."}` (vai para `notes`). 204. Dispara `access.revoked`. Se `access.user_id` ≠ `{student}` → 404.

## Matrículas (Access)

Objeto matrícula: `id`, `user_id`, `course_id`, `checkout_id`, `subscription_id`, `class_id`, `type`, `duration`, `is_active`, `granted_at`, `expires_at` (null = vitalício), `created_at`.

### GET /access — `access:read`
Cursor. Query: `per_page`, `cursor`, `course_id`, `user_id`, `active_only` (`true`/`false`).

### GET /access/{access} — `access:read`

### POST /access — `access:write` · idempotência suportada
Igual a conceder acesso, mas com `user_id` no corpo: `user_id` (obrig.), `course_id` (obrig.), `type` (obrig.), `duration`, `days`, `class_id`, `notes`.

```json
{"user_id": 42, "course_id": 1, "type": "temporary", "days": 30}
```

### DELETE /access/{access} — `access:write`
Soft revoke. Corpo opcional `{"reason": "..."}`. 204.

### Receitas

- **Alunos ativos de um curso**: `GET /access?course_id=1&active_only=true` (iterar cursor) → `user_id`s → `GET /students/{id}` se precisar de nome/e-mail.
- **Cortesia em massa**: para cada aluno `POST /students/{id}/access` com `Idempotency-Key` determinística (`cortesia-{campanha}-{user}-{course}`), respeitando o rate limit.
- **Não existe criação de aluno via API.** O aluno passa a existir quando compra, é importado no painel ou se cadastra. Para "matricular por e-mail" de alguém sem conta, use o fluxo de checkout/importação no painel.

## Certificados — `certificates:read`

Objeto: `id`, `user_id`, `course_id`, `certificate_number` (ex.: `CERT-2026-000050`), `completion_percentage` (decimal string), `issued_at`, `expires_at`, `revoked_at`.

- `GET /certificates` — cursor. Query: `per_page`, `course_id`, `user_id`.
- `GET /certificates/{certificate}`

Evento em tempo real: webhook `certificate.issued`.

## Perguntas em aulas — `questions:read`

Objeto: `id`, `user_id` (quem perguntou), `lesson_id`, `question`, `answer`, `answered_by`, `status` (`pending` | `viewed` | `answered`), `viewed_at`, `answered_at`, `created_at`.

- `GET /questions` — cursor. Query: `per_page`, `status`, `lesson_id`.
- `GET /questions/{question}`

Somente leitura: responder perguntas é feito no painel. Uso típico: alerta (Slack/e-mail) de `status=pending` para a equipe.
