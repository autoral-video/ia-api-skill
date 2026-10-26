# Skill `autoral-api` — API da autoral.me para agentes de IA

Skill no formato [Agent Skills](https://agentskills.io) que ensina assistentes de IA (Claude Code, Claude.ai, Claude Desktop e outros agentes compatíveis) a integrar seus projetos com a **API REST pública da autoral.me**: matrícula de alunos, captura de leads, cupons, produtos e ofertas, pagamentos e reembolsos, assinaturas, quizzes de venda, páginas/landing pages, biblioteca de mídia e webhooks.

Com a skill instalada, basta pedir em linguagem natural:

> "Crie um endpoint no meu backend que recebe o formulário do site e cria o lead na autoral.me"
> "Liste todos os alunos ativos do curso 12 e exporte em CSV"
> "Monte um quiz de venda com 4 perguntas que recomenda entre os checkouts 15 e 18"
> "Receba o webhook `payment.approved` e mande boas-vindas no WhatsApp"

## Conteúdo

```
.claude-plugin/                 # manifesto do plugin + marketplace (Claude Code)
skills/autoral-api/
├── SKILL.md                     # instruções principais + índice de endpoints e escopos
├── references/
│   ├── fundamentos.md           # tokens, escopos, erros, rate limit, paginação, idempotência
│   ├── conteudo.md              # /me, cursos, módulos, aulas, biblioteca de mídia
│   ├── alunos-e-acesso.md       # alunos, matrículas, certificados, perguntas
│   ├── financeiro.md            # pagamentos, reembolsos, assinaturas
│   ├── vendas.md                # produtos, ofertas, checkouts, cupons, leads
│   ├── quiz-funnels.md          # quizzes de venda
│   ├── paginas.md               # páginas públicas e landing pages
│   ├── webhooks.md              # CRUD, eventos, payloads, assinatura HMAC
│   └── clientes.md              # clientes TS/Python/Laravel, receptores de webhook, n8n
└── scripts/
    └── autoral.py               # CLI sem dependências (Python 3.8+)
```

## Pré-requisitos

1. Plano com API (Lite, Pro ou Scale).
2. Token criado por um Super Admin em **Configurações → Tokens de API**, com apenas os escopos necessários.
3. Variáveis de ambiente no projeto (nunca commite o token):

```bash
export AUTORAL_BASE_URL="https://sua-escola.autoral.me"
export AUTORAL_TOKEN="aut_..."
export AUTORAL_WEBHOOK_SECRET="..."   # se for receber webhooks
```

## Instalação

### Claude Code (recomendado — plugin)

```
/plugin install autoral-api --marketplace autoral-video/ia-api-skill
```

Em versões mais antigas do Claude Code, em dois passos:

```
/plugin marketplace add autoral-video/ia-api-skill
/plugin install autoral-api@autoral
```

Atualizar depois: `/plugin marketplace update autoral`.

Para que todo o time receba o plugin ao abrir o projeto, adicione ao `.claude/settings.json` do repositório:

```json
{
  "extraKnownMarketplaces": {
    "autoral": { "source": { "source": "github", "repo": "autoral-video/ia-api-skill" } }
  },
  "enabledPlugins": { "autoral-api@autoral": true }
}
```

### Claude Code (cópia manual da skill)

```bash
git clone https://github.com/autoral-video/ia-api-skill.git /tmp/ia-api-skill
cp -r /tmp/ia-api-skill/skills/autoral-api .claude/skills/      # só neste projeto
# ou
cp -r /tmp/ia-api-skill/skills/autoral-api ~/.claude/skills/    # todos os projetos
```

### Claude.ai / Claude Desktop

1. Baixe o repositório e compacte a skill: `cd skills && zip -r autoral-api.zip autoral-api`
2. Em **Configurações → Capacidades → Skills**, envie `autoral-api.zip`.

### Outros agentes (Cursor, Codex, Gemini CLI, etc.)

Copie `skills/autoral-api/` para o diretório de skills do agente, ou referencie `skills/autoral-api/SKILL.md` nas instruções do projeto (`AGENTS.md`, `.cursorrules`, …).

## CLI incluso

```bash
python3 skills/autoral-api/scripts/autoral.py me                                  # valida token e escopos
python3 skills/autoral-api/scripts/autoral.py get /courses --all                  # lista tudo, segue paginação
python3 skills/autoral-api/scripts/autoral.py post /leads --data @lead.json       # Idempotency-Key automática
python3 skills/autoral-api/scripts/autoral.py upload --file capa.png --field folder_id=3
python3 skills/autoral-api/scripts/autoral.py verify-signature --body-file corpo.json --signature <hex>
```

Faz retry em `429` respeitando `Retry-After`, mostra `X-Request-Id` e nunca envia o token a outro domínio.

## Segurança

- A skill instrui o agente a pedir confirmação antes de reembolsos, cancelamentos de assinatura, remoções definitivas e publicações.
- Um token por integração, com escopo mínimo e expiração em testes.
- Token com `pages:write` publica HTML arbitrário no seu domínio: use só em integrações confiáveis.

## Documentação oficial

Referência completa: repositório [autoral-video/docs](https://github.com/autoral-video/docs). Esta skill foi gerada a partir dele; ao mudar a API, atualize os arquivos em `skills/autoral-api/references/` e incremente `version` em `.claude-plugin/plugin.json` e `marketplace.json`.
