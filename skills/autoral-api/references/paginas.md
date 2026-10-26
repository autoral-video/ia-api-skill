# Páginas públicas (termos, políticas, landing pages)

Página pública: `https://{dominio}/p/{slug}` — só responde com `is_published: true` (senão 404). Mesmo recurso de **Configurações → Páginas** no painel. Não incluído no plano Autoral Store (403). Limites: `max_landing_pages` do plano (402) e 200 por conta (422 `platform_limit_exceeded`).

⚠️ `content` é publicado como HTML sem filtro. Quem tem token com `pages:write` publica qualquer HTML/JS no domínio da escola.

Objeto página: `id`, `title`, `slug`, `public_url`, `content` (só no show/create/update), `meta_title`, `meta_description`, `render_mode`, `og_title`, `og_image`, `canonical_url`, `is_published`, `is_homepage`, `tracking_disabled`, `order`, `created_at`, `updated_at`.

## POST /pages — `pages:write` · idempotência suportada

| Campo | Tipo | Obs. |
|---|---|---|
| `title` | string | **obrig.**, ≤255 |
| `slug` | string | minúsculas, números, hífens, ≤255, único; gerado do título (com `-1`, `-2`) se omitido |
| `content` | string | HTML, ≤200.000 chars; aceita variáveis |
| `render_mode` | string | `layout` (padrão) ou `document` |
| `meta_title` | string | ≤255; padrão = `title` |
| `meta_description` | string | ≤500; vira `og:description` |
| `og_title` | string | ≤255; padrão `meta_title` → `title` |
| `og_image` | string | URL **https**, ≤2048; ideal 1200×630 (1,91:1), JPG/PNG, ≤1 MB |
| `canonical_url` | string | http/https; vira `og:url` |
| `is_published` | bool | padrão `false` |
| `is_homepage` | bool | raiz `/` do domínio; só com publicada; desmarca a anterior |
| `tracking_disabled` | bool | padrão `false`; recomendado `true` em termos/privacidade |

### `render_mode`

- **`layout`**: `content` entra no `<body>` do layout da plataforma (Tailwind compilado só com classes que o app usa, Alpine.js, tema da conta). Bom para termos/políticas/FAQ. Não conte com classes Tailwind arbitrárias — podem não existir no CSS compilado; use HTML semântico ou `<style>` inline.
- **`document`**: `content` é o documento inteiro (`<!DOCTYPE html>`, `<head>`, `<body>`, CSS/JS próprios ou de CDN). A plataforma não carrega layout/CSS/JS/tema; só injeta:
  - antes de `</head>`: `<title>` (se faltar), meta SEO/compartilhamento (`description`, `canonical`, `og:*`, `twitter:*`) e scripts globais do cabeçalho (Configurações → Scripts);
  - antes de `</body>`, se `tracking_disabled=false`: banner LGPD, Pixel Meta, GA4/GTM e eventos (`page_view`, rolagem, tempo, cliques em elementos com `data-track` e em links de checkout). ~3 KB.

  Não duplique no `<head>` as tags que a plataforma injeta — use os campos da API. Sem `</head>`/`</body>`, os blocos vão para o início/fim do HTML.

Rastrear CTA: `<a href="/checkout/meu-curso" data-track="click_cta">Quero</a>`.

### Variáveis dinâmicas (trocadas só na página pública)

`{{site_name}}`, `{{site_url}}`, `{{year}}`, `{{logo_url}}`, `{{contact_email}}`.

### Exemplos

```json
{
  "title": "Política de Privacidade",
  "content": "<h1>Privacidade</h1><p>© {{year}} {{site_name}}</p>",
  "meta_description": "Como tratamos seus dados",
  "is_published": true,
  "tracking_disabled": true
}
```

```json
{
  "title": "Black Friday",
  "slug": "black-friday",
  "render_mode": "document",
  "content": "<!DOCTYPE html><html lang=\"pt-BR\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>Black Friday</title><style>body{margin:0;font-family:system-ui}</style></head><body><h1>Oferta</h1><a href=\"/checkout/meu-curso\" data-track=\"click_cta\">Quero</a></body></html>",
  "meta_description": "50% off só esta semana",
  "og_title": "Black Friday: 50% off",
  "og_image": "https://cdn.exemplo.com/black-friday.jpg",
  "is_published": false
}
```

Para HTML grande, monte o JSON com um serializador (Python `json.dumps`, JS `JSON.stringify`) — não escape aspas na mão. Com o script: grave `{"content": ...}` num arquivo e use `--data @arquivo.json`.

Erros 422 comuns: `title` ausente, `slug` fora do formato ou em uso, `content` > 200.000, `render_mode` inválido, `og_image` sem https.

## GET /pages — `pages:read`
Por página. Query: `per_page`, `page`, `published` (`1` publicadas, `0` rascunhos). **Sem `content`** (pode ter 200 KB). Ordem: `order`, depois `title`.

## GET /pages/{page} — `pages:read`
Com `content` cru (variáveis não substituídas).

## PATCH /pages/{page} — `pages:write`
Parcial; campos ausentes ficam. Não conta no limite do plano. `content` substitui o HTML inteiro. `null` em `meta_title`/`og_title` volta ao padrão; em `og_image`/`canonical_url` remove. `slug` novo derruba o link antigo. `is_published: false` tira do ar. `is_homepage: true` troca a página inicial.

Para editar um trecho: `GET /pages/{id}` → alterar `content` localmente → `PATCH` com o `content` completo.

## DELETE /pages/{page} — `pages:write`
204, **definitivo**; slug fica livre. Se era `is_homepage`, a raiz do domínio volta a redirecionar para o login.

## Fluxo recomendado para landing page gerada por IA
1. Subir imagens com `POST /media` → usar `url`.
2. `POST /pages` com `render_mode: "document"`, `is_published: false`.
3. Mostrar `public_url` ao usuário (só abre quando publicada — combine revisão) e publicar com `PATCH {"is_published": true}` após aprovação.
