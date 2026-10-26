# Clientes prontos

Modelos para colar no projeto do usuário. Todos: token via variável de ambiente, `Accept: application/json`, `Idempotency-Key` em POST, retry em 429 com `Retry-After`, erro tipado com `request_id`, iteração das duas paginações. Adapte ao estilo do projeto (logger, framework HTTP, tipagem) em vez de copiar cegamente.

## TypeScript / JavaScript (Node 18+, Deno, Bun, Workers — `fetch` nativo)

```ts
// autoral.ts
export class AutoralError extends Error {
  constructor(
    public status: number,
    public type: string,
    public code: string | undefined,
    public requestId: string | undefined,
    public errors?: Record<string, string[]>,
    public body?: unknown,
  ) {
    super(`[autoral ${status} ${type}${code ? `/${code}` : ""}] request_id=${requestId ?? "?"}`);
  }
}

type Query = Record<string, string | number | boolean | undefined>;

export class Autoral {
  private base: string;
  constructor(
    domain = process.env.AUTORAL_BASE_URL!,
    private token = process.env.AUTORAL_TOKEN!,
    private maxRetries = 3,
  ) {
    if (!domain || !token) throw new Error("Defina AUTORAL_BASE_URL e AUTORAL_TOKEN");
    const d = domain.replace(/\/+$/, "").replace(/\/api\/v1$/, "");
    this.base = (d.startsWith("http") ? d : `https://${d}`) + "/api/v1";
  }

  async request<T = any>(
    method: string,
    path: string,
    opts: { query?: Query; body?: unknown; idempotencyKey?: string } = {},
  ): Promise<T> {
    const url = path.startsWith("http") ? new URL(path) : new URL(this.base + path);
    if (url.origin !== new URL(this.base).origin) throw new Error("URL fora do domínio configurado");
    for (const [k, v] of Object.entries(opts.query ?? {})) if (v !== undefined) url.searchParams.set(k, String(v));

    const headers: Record<string, string> = {
      Authorization: `Bearer ${this.token}`,
      Accept: "application/json",
    };
    if (opts.body !== undefined) headers["Content-Type"] = "application/json";
    if (method === "POST") headers["Idempotency-Key"] = opts.idempotencyKey ?? crypto.randomUUID();

    for (let attempt = 0; ; attempt++) {
      const res = await fetch(url, {
        method,
        headers,
        body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
      });
      if (res.status === 429 && attempt < this.maxRetries) {
        const wait = Number(res.headers.get("Retry-After") ?? 1) * 1000 * 2 ** attempt;
        await new Promise((r) => setTimeout(r, wait));
        continue;
      }
      if (res.status === 204) return undefined as T;
      const json: any = await res.json().catch(() => ({}));
      if (!res.ok) {
        const e = json.error ?? {};
        throw new AutoralError(res.status, e.type ?? "unknown", e.code, e.request_id ?? res.headers.get("X-Request-Id") ?? undefined, e.errors, json);
      }
      return json as T;
    }
  }

  /** Itera qualquer listagem (cursor ou página) até o fim. */
  async *paginate<T = any>(path: string, query: Query = {}): AsyncGenerator<T> {
    let next: string | null = path;
    let q: Query | undefined = { per_page: 100, ...query };
    while (next) {
      const page: any = await this.request("GET", next, { query: q });
      yield* page.data as T[];
      next = page.next_page_url ?? page.links?.next ?? null;
      q = undefined; // a URL seguinte já carrega os filtros
    }
  }

  me = () => this.request("GET", "/me");
  grantAccess = (studentId: number, body: { course_id: number; type: "lifetime" | "temporary" | "subscription"; duration?: string; days?: number; class_id?: number; notes?: string }, key?: string) =>
    this.request("POST", `/students/${studentId}/access`, { body, idempotencyKey: key });
  createLead = (body: { checkout_id: number; name: string; email: string; phone?: string; metadata?: Record<string, unknown> }, key?: string) =>
    this.request("POST", "/leads", { body, idempotencyKey: key });
}

// uso
// const api = new Autoral();
// for await (const s of api.paginate("/students")) console.log(s.email);
```

## Python (requests)

```python
# autoral.py
import os, time, uuid
import requests

class AutoralError(Exception):
    def __init__(self, status, payload, request_id):
        err = (payload or {}).get("error", {})
        self.status, self.type, self.code = status, err.get("type"), err.get("code")
        self.errors, self.request_id, self.payload = err.get("errors"), err.get("request_id") or request_id, payload
        super().__init__(f"[autoral {status} {self.type}/{self.code}] {err.get('title')} request_id={self.request_id}")

class Autoral:
    def __init__(self, domain=None, token=None, max_retries=3, timeout=30):
        domain = (domain or os.environ["AUTORAL_BASE_URL"]).rstrip("/").removesuffix("/api/v1")
        self.base = (domain if domain.startswith("http") else f"https://{domain}") + "/api/v1"
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token or os.environ['AUTORAL_TOKEN']}",
                               "Accept": "application/json"})
        self.max_retries, self.timeout = max_retries, timeout

    def request(self, method, path, *, params=None, json=None, idempotency_key=None, files=None, data=None):
        url = path if path.startswith("http") else self.base + path
        if not url.startswith(self.base):
            raise ValueError("URL fora do domínio configurado")
        headers = {}
        if method == "POST":
            headers["Idempotency-Key"] = idempotency_key or str(uuid.uuid4())
        for attempt in range(self.max_retries + 1):
            r = self.s.request(method, url, params=params, json=json, files=files, data=data,
                               headers=headers, timeout=self.timeout)
            if r.status_code == 429 and attempt < self.max_retries:
                time.sleep(int(r.headers.get("Retry-After", 1)) * 2 ** attempt)
                continue
            break
        if r.status_code == 204:
            return None
        payload = r.json() if r.content else {}
        if not r.ok:
            raise AutoralError(r.status_code, payload, r.headers.get("X-Request-Id"))
        return payload

    def paginate(self, path, **params):
        """Itera cursor ou página até o fim."""
        params.setdefault("per_page", 100)
        url, p = path, params
        while url:
            page = self.request("GET", url, params=p)
            yield from page["data"]
            url = page.get("next_page_url") or (page.get("links") or {}).get("next")
            p = None

    def upload_media(self, file_path, folder_id=None, alt_text=None):
        with open(file_path, "rb") as f:
            data = {k: v for k, v in {"folder_id": folder_id, "alt_text": alt_text}.items() if v is not None}
            return self.request("POST", "/media", files={"file": f}, data=data)

# uso
# api = Autoral()
# api.request("POST", "/students/42/access", json={"course_id": 1, "type": "lifetime"},
#             idempotency_key="enroll-42-1-pedido-981")
```

## PHP / Laravel (Http client)

```php
// app/Services/Autoral.php
namespace App\Services;

use Illuminate\Http\Client\PendingRequest;
use Illuminate\Http\Client\RequestException;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;

class Autoral
{
    private string $base;

    public function __construct(?string $domain = null, private ?string $token = null)
    {
        $domain = rtrim($domain ?? config('services.autoral.base_url'), '/');
        $domain = preg_replace('#/api/v1$#', '', $domain);
        $this->base = (str_starts_with($domain, 'http') ? $domain : "https://{$domain}") . '/api/v1';
        $this->token ??= config('services.autoral.token');
    }

    private function http(): PendingRequest
    {
        return Http::baseUrl($this->base)
            ->withToken($this->token)
            ->acceptJson()
            ->timeout(30)
            ->retry(3, function (int $attempt, \Throwable $e) {
                $retryAfter = $e instanceof RequestException ? (int) $e->response->header('Retry-After') : 0;
                return max(1, $retryAfter) * 1000 * (2 ** ($attempt - 1));
            }, fn (\Throwable $e) => $e instanceof RequestException && $e->response->status() === 429);
    }

    public function get(string $path, array $query = []): array
    {
        return $this->http()->get($path, $query)->throw()->json();
    }

    public function post(string $path, array $body, ?string $idempotencyKey = null): array
    {
        return $this->http()
            ->withHeaders(['Idempotency-Key' => $idempotencyKey ?? (string) Str::uuid()])
            ->post($path, $body)->throw()->json();
    }

    public function patch(string $path, array $body): array
    {
        return $this->http()->patch($path, $body)->throw()->json();
    }

    public function delete(string $path, array $body = []): void
    {
        $this->http()->delete($path, $body)->throw();
    }

    /** @return \Generator<array> */
    public function paginate(string $path, array $query = []): \Generator
    {
        $url = $path;
        $query = ['per_page' => 100] + $query;
        while ($url) {
            $page = $this->http()->get($url, $query)->throw()->json();
            yield from $page['data'];
            $url = $page['next_page_url'] ?? ($page['links']['next'] ?? null);
            $query = [];
        }
    }
}

// config/services.php
// 'autoral' => ['base_url' => env('AUTORAL_BASE_URL'), 'token' => env('AUTORAL_TOKEN'), 'webhook_secret' => env('AUTORAL_WEBHOOK_SECRET')],
// Em erro: $e->response->json('error.request_id')
```

## Receptores de webhook

Regras: corpo **bruto** no HMAC, comparação em tempo constante, deduplicar por `id`, responder 2xx em < 10 s e processar em background.

### Node / Express

```ts
import express from "express";
import crypto from "node:crypto";

const app = express();
app.post("/webhooks/autoral", express.raw({ type: "application/json" }), async (req, res) => {
  const expected = crypto.createHmac("sha256", process.env.AUTORAL_WEBHOOK_SECRET!).update(req.body).digest("hex");
  const got = req.header("X-Webhook-Signature") ?? "";
  if (got.length !== expected.length || !crypto.timingSafeEqual(Buffer.from(got), Buffer.from(expected))) {
    return res.sendStatus(401);
  }
  const evt = JSON.parse(req.body.toString("utf8"));
  if (await alreadyProcessed(evt.id)) return res.sendStatus(200); // dedupe
  res.sendStatus(200);
  queue.push(evt); // processa fora do ciclo da request
});
```

### Python / FastAPI

```python
import hmac, hashlib, os
from fastapi import FastAPI, Request, Response, BackgroundTasks

app = FastAPI()

@app.post("/webhooks/autoral")
async def autoral_webhook(request: Request, bg: BackgroundTasks):
    raw = await request.body()
    expected = hmac.new(os.environ["AUTORAL_WEBHOOK_SECRET"].encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, request.headers.get("X-Webhook-Signature", "")):
        return Response(status_code=401)
    evt = await request.json()
    if not mark_processed_once(evt["id"]):   # ex.: INSERT ... ON CONFLICT DO NOTHING
        return Response(status_code=200)
    bg.add_task(handle_event, evt)
    return Response(status_code=200)
```

### Laravel

```php
// routes/api.php
Route::post('/webhooks/autoral', function (Illuminate\Http\Request $request) {
    $expected = hash_hmac('sha256', $request->getContent(), config('services.autoral.webhook_secret'));
    abort_unless(hash_equals($expected, (string) $request->header('X-Webhook-Signature')), 401);

    $evt = $request->json()->all();
    if (! Cache::add("autoral-evt:{$evt['id']}", true, now()->addDays(7))) {
        return response()->noContent(); // duplicado
    }
    \App\Jobs\HandleAutoralEvent::dispatch($evt);
    return response()->noContent();
});
```

### Roteamento de eventos (exemplo)

```ts
switch (evt.event) {
  case "payment.approved":     /* CRM: marcar cliente; data.amount é decimal */ break;
  case "student.enrolled":     /* boas-vindas no WhatsApp com data.user.phone */ break;
  case "subscription.past_due":/* régua de cobrança */ break;
  case "refund.created":       /* estornar comissão */ break;
  default: /* ignorar eventos não tratados, mas responder 200 */
}
```

## n8n / Zapier / Make

- Node HTTP Request: `Authorization: Bearer {{token}}` via credencial "Header Auth" (não em campo de texto livre).
- Em POST, `Idempotency-Key` com expressão determinística, ex.: `lead-{{$json.form_id}}-{{$json.submission_id}}`.
- Paginação no n8n: opção "Pagination" → "Response contains next URL" com `{{$response.body.next_page_url}}` (cursor) ou `{{$response.body.links.next}}` (página); condição de parada quando vazio.
- Webhook trigger: n8n não valida HMAC sozinho — adicione um node Code/Crypto que calcula `HMAC-SHA256(rawBody, secret)` e compara com `X-Webhook-Signature` (habilite "Raw Body" no node Webhook).
- Não use IP allowlist com Zapier/Make (IPs mudam).
