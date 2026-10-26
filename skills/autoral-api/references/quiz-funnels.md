# Quizzes de venda

Quiz faz perguntas, soma pontos por resultado e mostra o(s) checkout(s) do resultado vencedor. Página pública: `https://{dominio}/quiz/{slug}`. Não incluído no plano Autoral Store (403 `plan_feature_unavailable`). Limite: 200 quizzes por conta (422 `platform_limit_exceeded`).

## Pontuação

1. Declare `outcomes`, cada um com `key` local (ex.: `"basico"`).
2. Cada opção aponta pontos para keys em `points` (`{"basico": 2}`), inteiros de −100 a 100. Negativo afasta.
3. Vence o resultado com mais pontos; empate → o que vem primeiro em `outcomes`.
4. Nenhum ponto → resultado com `is_fallback: true` (ou o primeiro).
5. `type: "multiple"` soma os pontos de todas as opções marcadas.

A `key` só existe no payload de criação. Na resposta, `points` vem indexado pelo **ID** do resultado (`{"31": 2}`).

## POST /quiz-funnels — `quiz-funnels:write` · idempotência suportada

Cria tudo numa transação única (ou grava tudo, ou nada).

| Campo | Tipo | Obs. |
|---|---|---|
| `title` | string | **obrig.**, 3–120; aparece na aba do navegador |
| `slug` | string | `[a-zA-Z0-9_-]`, até 80, único; gerado do título se omitido |
| `status` | string | `draft` (padrão) ou `published` (passa pela validação de publicação) |
| `intro` | object | `headline` (≤255, padrão = title), `description` (≤2000), `image_url` (https, ≤2048), `button_label` (≤80, padrão "Começar") |
| `settings` | object | `show_progress` (true), `allow_back` (true) |
| `lead_capture` | object | `enabled` (false), `ask_name` (true), `ask_phone` (false; WhatsApp), `headline` (≤255). E-mail sempre pedido quando ativo; vai pré-preenchido ao checkout e dispara `Lead` no Pixel/CAPI |
| `meta_pixel` | object | `pixel_id` (**string** só dígitos, ≤32; null = herdar), `access_token` (CAPI, ≤512, só escrita — resposta traz `has_access_token`) |
| `outcomes` | object[] | **obrig.**, 1–20 (ver abaixo) |
| `questions` | object[] | **obrig.**, 1–50 (ver abaixo) |

`outcomes[]`:

| Campo | Obs. |
|---|---|
| `key` | **obrig.**, ≤64, única no payload |
| `title` | **obrig.**, ≤255 |
| `description` | ≤2000 |
| `image_url` | https |
| `checkout_ids` | int[], até 10, do tenant, em ordem de exibição |
| `cta_label` | ≤80, padrão "Quero esse" |
| `auto_redirect` | pula a tela de resultado e vai ao checkout; só com **exatamente 1** checkout |
| `is_fallback` | no máximo um |

`questions[]`: `title` (**obrig.**, ≤500), `description` (≤1000), `image_url`, `type` (`single` padrão | `multiple`), `options` (**obrig.**, 2–12) com `label` (**obrig.**, ≤500) e `points` (opcional).

### Validação de publicação (`status: "published"`)
- toda pergunta com texto e ≥ 2 opções;
- ≥ 1 resultado;
- **todo** resultado com ≥ 1 checkout **ativo**.

Falhou → 422 `quiz_not_publishable` com `error.problems: [...]`. Estratégia segura: criar como `draft`, mostrar ao usuário, depois `PATCH {"status":"published"}`.

Erros 422 `validation_error` comuns: `pixel_id` com letras ou numérico em vez de string, `key` repetida, `points` para key inexistente (`questions.0.options.0.points`), checkout de outro tenant, mais de um `is_fallback`.

### Imagens (abertura, pergunta, resultado)
16:9, recortadas pelo centro (`object-fit: cover`), cantos arredondados 14 px. Recomendado **1200 × 675** (mín. 800 × 450), WebP/JPG, ≤ 300 KB, URL https pública. Evite texto na imagem; mantenha rostos longe dos cantos. Opcionais. A miniatura do produto no resultado é a `thumbnail` do curso do checkout (56×56, envie ≥ 168×168). Para hospedar: `POST /media` e use `data.url`.

### Pixel da Meta
Ordem de escolha: (1) `meta_pixel.pixel_id` do quiz → (2) herdado dos checkouts, se **todos** usam o mesmo Pixel próprio (token também herdado) → (3) Pixel de Configurações → Facebook Conversions API. Checkouts com Pixels diferentes não herdam: defina `pixel_id` igual ao do checkout principal. `Purchase` é sempre enviado pelo checkout.

### Exemplo

```json
{
  "title": "Descubra seu próximo passo",
  "status": "draft",
  "intro": { "headline": "Qual caminho é o seu?", "description": "Responda 2 perguntas rápidas." },
  "lead_capture": { "enabled": true, "ask_name": true, "ask_phone": true },
  "outcomes": [
    { "key": "basico", "title": "Comece pelo básico", "checkout_ids": [12], "is_fallback": true },
    { "key": "mentoria", "title": "Mentoria individual", "checkout_ids": [15], "cta_label": "Quero a mentoria", "auto_redirect": true }
  ],
  "questions": [
    { "title": "Você já vende online?", "options": [
      { "label": "Ainda não", "points": { "basico": 2 } },
      { "label": "Sim, todo mês", "points": { "mentoria": 3 } }
    ]},
    { "title": "O que você quer agora?", "type": "multiple", "options": [
      { "label": "Aprender o passo a passo", "points": { "basico": 1 } },
      { "label": "Acompanhamento próximo", "points": { "mentoria": 1, "basico": -1 } },
      { "label": "Só curiosidade" }
    ]}
  ]
}
```

Resposta 201: quiz completo com `id`, `slug`, `public_url`, `outcomes[].id`, `questions[].id`, `options[].id`, `points` por ID, `meta_pixel.has_access_token`, `published_at`.

## GET /quiz-funnels — `quiz-funnels:read`
Por página. Query: `per_page`, `page`, `status` (`draft` | `published`). Sem estrutura de perguntas: `id`, `title`, `slug`, `status`, `public_url`, `intro`, `settings`, `lead_capture`, `meta_pixel`, `questions_count`, `published_at`, `created_at`, `updated_at`.

## GET /quiz-funnels/{quizFunnel} — `quiz-funnels:read`
Tudo da listagem + `outcomes[]` (ordem de desempate) e `questions[]` com `options[]` (`id`, `label`, `points` por ID de resultado).

## PATCH /quiz-funnels/{quizFunnel} — `quiz-funnels:write`
Parcial (inclusive dentro de `intro`, `settings`, `lead_capture`, `meta_pixel`). Campos: `title`, `slug` (link antigo morre), `status` (`published` valida; `draft` tira do ar), `intro`, `settings`, `lead_capture`, `meta_pixel` (`access_token` ausente mantém, `null` remove; `pixel_id: null` volta a herdar e remove o token).

**Não altera perguntas, opções nem resultados** (isso apagaria respostas e estatísticas). Para mudar a estrutura: editor do painel ou criar quiz novo.

## DELETE /quiz-funnels/{quizFunnel} — `quiz-funnels:write`
Soft delete, 204. Link público vira 404 na hora; vendas atribuídas permanecem. **Slug fica reservado** (não reutilizável).

## GET /quiz-funnels/{quizFunnel}/stats — `quiz-funnels:read`
Query: `from`, `to` (`Y-m-d`; padrão últimos 30 dias até hoje; máx. 1 ano). Sessão = visitante que abriu o quiz (robôs de preview e prefetch excluídos). Venda atribuída quando o comprador chega ao checkout pelo botão do resultado.

```json
{
  "data": {
    "from": "2026-10-01", "to": "2026-10-18",
    "totals": { "views": 1240, "started": 806, "completed": 590, "leads": 512, "clicks": 233, "purchases": 41, "revenue_cents": 807700 },
    "drop_off": [ { "step": 1, "question_id": 90, "title": "…", "reached": 771 } ],
    "answers": [ { "question_id": 90, "title": "…", "answered": 771,
                   "options": [ { "option_id": 401, "label": "…", "count": 498, "percent": 64.6 } ] } ],
    "outcomes": [ { "outcome_id": 31, "title": "…", "completed": 402, "clicks": 160, "purchases": 33, "revenue_cents": 650100 } ],
    "sources": [ { "source": "instagram", "views": 880, "completed": 431, "purchases": 30, "revenue_cents": 591000 } ]
  }
}
```

`sources`: top 10 `utm_source` (`null` = direto). Em múltipla escolha, `percent` soma > 100. Taxas úteis: início = started/views, conclusão = completed/started, conversão = purchases/views.

## Gerando quizzes com IA — checklist
1. `GET /checkouts?active=true` e escolher checkout(s) por resultado com o usuário.
2. 3–7 perguntas, 2–5 opções cada; todo resultado deve ser alcançável (alguma opção pontua para ele).
3. Marcar um `is_fallback`.
4. Criar como `draft`, revisar `public_url` com o usuário, publicar via PATCH.
