# Identidade, conteúdo e Biblioteca de Mídia

Tudo somente leitura, exceto mídia (upload/remoção). Não há endpoints para criar ou editar cursos, módulos e aulas.

## GET /me — sem escopo

Valida token e mostra escopos, tenant e plano.

```json
{
  "data": {
    "token": {
      "id": 12, "name": "n8n produção", "description": "Sync de leads",
      "abilities": ["courses:read", "students:write"],
      "last_used_at": "2026-05-05T19:30:00+00:00", "expires_at": null,
      "created_at": "2026-05-05T18:00:00+00:00"
    },
    "tenant": { "id": 1, "name": "Minha Escola" },
    "plan": { "slug": "pro", "name": "Pro", "api_rate_limit_per_minute": 300, "max_api_tokens": 10 },
    "limits": { "remaining_api_tokens": 7 }
  }
}
```

`plan.slug`: `free`, `lite`, `pro`, `scale`.

## Cursos — `courses:read`

### GET /courses
Paginação por página. Query: `per_page` (1–100), `page`.

Campos: `id`, `name`, `slug`, `description`, `short_description`, `thumbnail` (URL|null), `cover_image` (URL|null), `is_active`, `is_featured`, `sequential_lessons`, `sequential_modules`, `modules_count`, `created_at`, `updated_at`.

### GET /courses/{course}
Um curso (mesmos campos). Curso de outro tenant → 404.

### GET /courses/{course}/modules
Paginação por página. Campos: `id`, `course_id`, `name`, `description`, `sort_order`, `is_active`, `lessons_count`, `created_at`, `updated_at`.

## Aulas

### GET /modules/{module}/lessons — `modules:read`
Paginação por página (`per_page`). Campos: `id`, `module_id`, `type` (`video` | `article` | `quiz`), `title`, `slug`, `description`, `duration_seconds`, `sort_order`, `is_active`, `is_free` (preview gratuito), `created_at`, `updated_at`.

### GET /lessons/{lesson} — `lessons:read`
Uma aula (mesmos campos).

Árvore completa de um curso: `GET /courses/{id}/modules` → para cada módulo `GET /modules/{id}/lessons` (exige os três escopos `courses:read`, `modules:read` e, para detalhe, `lessons:read`).

## Biblioteca de Mídia

Exige o recurso no plano; senão 403 `plan_feature_unavailable`.

Objeto mídia: `id`, `name` (nome original), `kind` (`image` | `document` | `audio`), `mime_type`, `size` (bytes), `url` (pública, CDN), `folder_id`, `alt_text`, `width`/`height` (px, imagens), `duration` (s, áudios), `tags` (string[]), `created_at`.

### GET /media — `media-library:read`
Paginação por página. Query: `per_page`, `page`, `kind`, `folder_id`, `search` (parcial no nome).

### GET /media/{media} — `media-library:read`

### POST /media — `media-library:write` · idempotência suportada
`multipart/form-data`. Envie `Accept: application/json`.

| Campo | Tipo | Obs. |
|---|---|---|
| `file` | arquivo | obrigatório |
| `folder_id` | int | pasta precisa existir no tenant |
| `alt_text` | string | até 255 |

| `kind` | Extensões | Máx. |
|---|---|---|
| image | jpg, jpeg, png, webp, gif | 5 MB |
| document | pdf, docx, xlsx | 30 MB |
| audio | mp3, wav | 30 MB |

Conta no armazenamento do plano. Resposta 201 = objeto mídia. Erros: 422 `validation_error` (extensão) ou 422 `upload_rejected` (tamanho, MIME real, armazenamento — motivo em `title`).

```bash
curl https://$DOMINIO/api/v1/media \
  -H "Authorization: Bearer $AUTORAL_TOKEN" -H "Accept: application/json" \
  -F "file=@capa-curso.png" -F "folder_id=3" -F "alt_text=Capa do curso"
```

Uso típico: subir imagem → usar `data.url` em `og_image` de página ou `image_url` de quiz.

### DELETE /media/{media} — `media-library:write`
204. **Definitivo**: arquivo sai do storage; páginas que usam a URL quebram.
