#!/usr/bin/env python3
"""Cliente de linha de comando para a API REST da autoral.me.

Somente biblioteca padrão (Python 3.8+). Lê AUTORAL_BASE_URL e AUTORAL_TOKEN
do ambiente; nunca imprime o token.

Exemplos:
  autoral.py me
  autoral.py get /courses --query per_page=100 --all
  autoral.py post /leads --data '{"checkout_id":5,"name":"Ana","email":"ana@x.com"}'
  autoral.py patch /pages/4 --data @pagina.json
  autoral.py delete /access/1234 --data '{"reason":"Encerramento"}'
  autoral.py upload --file capa.png --field folder_id=3 --field alt_text="Capa"
  autoral.py verify-signature --body-file corpo.json --signature <hex>
"""
import argparse
import hashlib
import hmac
import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

USER_AGENT = "autoral-api-skill/1.0"
MAX_RETRIES = 3
MAX_WAIT_SECONDS = 120
IDEMPOTENCY_KEY_RE = re.compile(r"[a-zA-Z0-9_-]{8,128}")


def die(msg, code=2):
    print(f"erro: {msg}", file=sys.stderr)
    sys.exit(code)


def base_url():
    raw = os.environ.get("AUTORAL_BASE_URL", "").strip().rstrip("/")
    if not raw:
        die("defina AUTORAL_BASE_URL (ex.: https://escola.autoral.me)")
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    if not raw.endswith("/api/v1"):
        raw += "/api/v1"
    return raw


def token():
    tok = os.environ.get("AUTORAL_TOKEN", "").strip()
    if not tok:
        die("defina AUTORAL_TOKEN (token aut_... criado em Configurações → Tokens de API)")
    if not tok.startswith("aut_"):
        print("aviso: AUTORAL_TOKEN não começa com 'aut_'", file=sys.stderr)
    return tok


def build_url(base, path, query=None):
    if path.startswith(("http://", "https://")):
        url = path
        # Nunca envie o token para outro host (ex.: next_page_url adulterado).
        target, origin = urllib.parse.urlsplit(url), urllib.parse.urlsplit(base)
        if (target.scheme, target.netloc) != (origin.scheme, origin.netloc):
            die(f"recusado: URL fora do domínio configurado ({url})")
    else:
        url = base + "/" + path.lstrip("/")
    if query:
        sep = "&" if urllib.parse.urlsplit(url).query else "?"
        url += sep + urllib.parse.urlencode(query)
    return url


def parse_kv(items, what):
    out = {}
    for item in items or []:
        if "=" not in item:
            die(f"{what} deve ser chave=valor: {item!r}")
        k, v = item.split("=", 1)
        out[k] = v
    return out


def load_data(value):
    if value is None:
        return None
    if value.startswith("@"):
        path = value[1:]
        if path == "-":
            text = sys.stdin.read()
        else:
            with open(path, encoding="utf-8") as f:
                text = f.read()
    else:
        text = value
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        die(f"--data não é JSON válido: {e}")


def multipart(fields, files):
    boundary = uuid.uuid4().hex
    chunks = []
    for name, value in fields.items():
        chunks.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        )
    for name, path in files.items():
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        filename = os.path.basename(path).replace('"', "")
        with open(path, "rb") as f:
            content = f.read()
        head = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            f"Content-Type: {ctype}\r\n\r\n"
        ).encode()
        chunks.append(head + content + b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def call(method, url, tok, body=None, content_type=None, idempotency_key=None, request_id=None):
    headers = {
        "Authorization": f"Bearer {tok}",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    if content_type:
        headers["Content-Type"] = content_type
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    if request_id:
        headers["X-Request-Id"] = request_id
    # 5xx/rede só são retentados quando repetir é seguro.
    safe_to_retry = method in ("GET", "HEAD") or bool(idempotency_key)

    for attempt in range(MAX_RETRIES + 1):
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            status, hdrs, raw = e.code, e.headers, e.read()
            retry = status == 429 or (status >= 500 and safe_to_retry)
            if retry and attempt < MAX_RETRIES:
                try:
                    wait = int(hdrs.get("Retry-After") or 0)
                except ValueError:
                    wait = 0
                wait = min(max(wait, 1) * 2 ** attempt, MAX_WAIT_SECONDS)
                print(f"HTTP {status}; nova tentativa em {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            return status, hdrs, raw
        except urllib.error.URLError as e:
            if safe_to_retry and attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)
                continue
            die(f"falha de rede: {e.reason}")


def report(status, hdrs):
    parts = [f"HTTP {status}"]
    rid = hdrs.get("X-Request-Id")
    if rid:
        parts.append(f"X-Request-Id: {rid}")
    if hdrs.get("Idempotent-Replay"):
        parts.append("Idempotent-Replay: true")
    remaining = hdrs.get("X-RateLimit-Remaining")
    if remaining is not None:
        parts.append(f"RateLimit-Remaining: {remaining}")
    print(" · ".join(parts), file=sys.stderr)


def decode(raw):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw.decode("utf-8", "replace")}


def emit(status, hdrs, raw):
    report(status, hdrs)
    payload = decode(raw)
    if payload is not None:
        stream = sys.stdout if status < 400 else sys.stderr
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=stream)
    sys.exit(0 if status < 400 else 1)


def idempotency_for(args):
    if args.method != "POST" or args.no_idempotency:
        return None
    key = args.idempotency_key or str(uuid.uuid4())
    if not IDEMPOTENCY_KEY_RE.fullmatch(key):
        die("Idempotency-Key deve casar com ^[a-zA-Z0-9_-]{8,128}$")
    print(f"Idempotency-Key: {key}", file=sys.stderr)
    return key


def cmd_request(args):
    base, tok = base_url(), token()
    query = parse_kv(args.query, "--query")
    if args.all:
        if args.method != "GET":
            die("--all só vale para GET")
        query.setdefault("per_page", "100")
        url, items, pages = build_url(base, args.path, query), [], 0
        while url:
            if pages >= args.max_pages:
                print(f"aviso: parou em --max-pages={args.max_pages}", file=sys.stderr)
                break
            status, hdrs, raw = call("GET", url, tok, request_id=args.request_id)
            if status >= 400:
                emit(status, hdrs, raw)
            page = decode(raw) or {}
            items.extend(page.get("data") or [])
            nxt = page.get("next_page_url") or (page.get("links") or {}).get("next")
            url = build_url(base, nxt) if nxt else None
            pages += 1
        print(f"{len(items)} itens em {pages} página(s)", file=sys.stderr)
        print(json.dumps({"data": items, "count": len(items)}, ensure_ascii=False, indent=2))
        return

    data = load_data(args.data)
    body = json.dumps(data).encode() if data is not None else None
    status, hdrs, raw = call(
        args.method,
        build_url(base, args.path, query),
        tok,
        body=body,
        content_type="application/json" if body is not None else None,
        idempotency_key=idempotency_for(args),
        request_id=args.request_id,
    )
    emit(status, hdrs, raw)


def cmd_me(args):
    status, hdrs, raw = call("GET", build_url(base_url(), "/me"), token(), request_id=args.request_id)
    emit(status, hdrs, raw)


def cmd_upload(args):
    base, tok = base_url(), token()
    if not os.path.isfile(args.file):
        die(f"arquivo não encontrado: {args.file}")
    body, ctype = multipart(parse_kv(args.field, "--field"), {"file": args.file})
    args.method = "POST"
    status, hdrs, raw = call(
        "POST", build_url(base, "/media"), tok, body=body, content_type=ctype,
        idempotency_key=idempotency_for(args), request_id=args.request_id,
    )
    emit(status, hdrs, raw)


def cmd_verify(args):
    secret = os.environ.get(args.secret_env, "")
    if not secret:
        die(f"defina {args.secret_env} com o secret do webhook")
    with open(args.body_file, "rb") as f:
        raw = f.read()
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    if hmac.compare_digest(expected, args.signature.strip().lower()):
        print("assinatura válida")
        return
    print("assinatura INVÁLIDA (confira se o corpo é o bruto recebido, sem reformatar)", file=sys.stderr)
    sys.exit(1)


def main():
    p = argparse.ArgumentParser(description="Cliente CLI da API autoral.me")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--request-id", help="X-Request-Id próprio (8-64 chars [a-zA-Z0-9-])")

    me = sub.add_parser("me", help="GET /me: valida token, escopos e plano")
    common(me)
    me.set_defaults(func=cmd_me)

    for method in ("get", "post", "patch", "delete"):
        sp = sub.add_parser(method, help=f"{method.upper()} em uma rota de /api/v1")
        sp.add_argument("path", help="ex.: /courses ou /students/42/access")
        sp.add_argument("--query", "-q", action="append", metavar="k=v", help="parâmetro de query (repetível)")
        sp.add_argument("--data", "-d", help="corpo JSON, @arquivo.json ou @- (stdin)")
        sp.add_argument("--idempotency-key", help="chave própria (padrão em POST: UUID aleatório)")
        sp.add_argument("--no-idempotency", action="store_true", help="não envia Idempotency-Key")
        sp.add_argument("--all", action="store_true", help="GET: segue a paginação até o fim")
        sp.add_argument("--max-pages", type=int, default=500, help="limite de páginas com --all")
        common(sp)
        sp.set_defaults(func=cmd_request, method=method.upper())

    up = sub.add_parser("upload", help="POST /media (multipart)")
    up.add_argument("--file", required=True)
    up.add_argument("--field", action="append", metavar="k=v", help="folder_id=3, alt_text=...")
    up.add_argument("--idempotency-key")
    up.add_argument("--no-idempotency", action="store_true")
    common(up)
    up.set_defaults(func=cmd_upload)

    vs = sub.add_parser("verify-signature", help="valida X-Webhook-Signature de um corpo salvo")
    vs.add_argument("--body-file", required=True, help="corpo bruto exatamente como recebido")
    vs.add_argument("--signature", required=True, help="valor do header X-Webhook-Signature")
    vs.add_argument("--secret-env", default="AUTORAL_WEBHOOK_SECRET", help="variável com o secret")
    vs.set_defaults(func=cmd_verify)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
