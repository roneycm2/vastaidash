#!/usr/bin/env python3
"""
Login 7k.bet.br (manual / humano-no-loop) com Playwright + logs detalhados.

Por design, este script NÃO tenta "resolver" Turnstile automaticamente.
Ele abre o navegador, preenche credenciais, e espera você concluir o captcha
e finalizar o login normalmente.

Saídas:
- logs/login_7k_<timestamp>.jsonl (eventos de rede relevantes)
- screenshots/login_7k_<timestamp>_*.png
- storage_state.json (cookies + localStorage para reutilizar sessão)

Requisitos:
  pip install -r requirements.txt
  python -m playwright install chromium

Uso:
  set SEVENK_EMAIL=seu@email.com
  set SEVENK_PASSWORD=sua_senha
  python login_7k_manual_playwright.py

Opcional (proxy):
  set SEVENK_PROXY=http://user:pass@host:port
  # ou formato alternativo: user:pass:host:port
  # ou separado:
  set SEVENK_PROXY_SERVER=http://host:port
  set SEVENK_PROXY_USERNAME=user
  set SEVENK_PROXY_PASSWORD=pass
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, Optional

from playwright.sync_api import sync_playwright


DEFAULT_BASE_URL = "https://7k.bet.br"
DEFAULT_LOGIN_PATHS = ("/login", "/")


def _now_ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_trunc(s: str, limit: int = 2000) -> str:
    if s is None:
        return ""
    if len(s) <= limit:
        return s
    return s[:limit] + f"\n... [truncated, {len(s)} chars total]"


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    redacted = {}
    for k, v in headers.items():
        lk = k.lower()
        if lk in {"authorization", "cookie"}:
            redacted[k] = "<redacted>"
        else:
            redacted[k] = v
    return redacted


def _looks_like_login_field(placeholder: str) -> bool:
    p = (placeholder or "").strip().lower()
    return any(x in p for x in ("e-mail", "email", "cpf", "usuário", "usuario", "login"))


def _print(msg: str) -> None:
    # timestamps ajudam a debugar
    sys.stdout.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    sys.stdout.flush()


@dataclass
class ProxyConfig:
    server: str
    username: Optional[str] = None
    password: Optional[str] = None

    def to_playwright(self) -> dict[str, str]:
        cfg: dict[str, str] = {"server": self.server}
        if self.username:
            cfg["username"] = self.username
        if self.password:
            cfg["password"] = self.password
        return cfg


class JsonlLogger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fp = self.path.open("a", encoding="utf-8")

    def write(self, event: str, payload: dict[str, Any]) -> None:
        obj = {
            "ts": time.time(),
            "event": event,
            **payload,
        }
        self._fp.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self._fp.flush()

    def close(self) -> None:
        try:
            self._fp.close()
        except Exception:
            pass


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Login manual 7k.bet.br com Playwright + logs")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p.add_argument("--headless", action="store_true", help="Rodar headless (não recomendado para captcha)")
    p.add_argument("--storage-state", default="storage_state.json", help="Arquivo para salvar sessão")
    p.add_argument("--timeout-sec", type=int, default=180, help="Timeout para observar request de login")
    p.add_argument("--email", default=os.getenv("SEVENK_EMAIL", ""))
    p.add_argument("--password", default=os.getenv("SEVENK_PASSWORD", ""))
    # Proxy: pode ser informado como URL completa (recomendado) ou separado em server/user/pass
    p.add_argument(
        "--proxy",
        default=os.getenv("SEVENK_PROXY", ""),
        help='Proxy URL completa. Ex: "http://user:pass@host:port" ou "user:pass:host:port"',
    )
    p.add_argument("--proxy-server", default=os.getenv("SEVENK_PROXY_SERVER", ""))
    p.add_argument("--proxy-username", default=os.getenv("SEVENK_PROXY_USERNAME", ""))
    p.add_argument("--proxy-password", default=os.getenv("SEVENK_PROXY_PASSWORD", ""))
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if not args.email or not args.password:
        _print("ERRO: defina SEVENK_EMAIL e SEVENK_PASSWORD (ou passe --email/--password).")
        return 2

    ts = _now_ts()
    logs_dir = Path("logs")
    screenshots_dir = Path("screenshots")
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    log = JsonlLogger(logs_dir / f"login_7k_{ts}.jsonl")

    proxy: Optional[ProxyConfig] = None
    # Preferência: --proxy / SEVENK_PROXY (URL completa ou USER:PASS:HOST:PORT)
    if args.proxy:
        proxy_str = args.proxy.strip()
        # Detecta formato USER:PASS:HOST:PORT (sem http://)
        if "://" not in proxy_str and proxy_str.count(":") == 3:
            parts = proxy_str.split(":")
            if len(parts) == 4:
                username, password, host, port = parts
                proxy_str = f"http://{username}:{password}@{host}:{port}"
                _print(f"Convertido proxy para: http://{username}:***@{host}:{port}")
        parsed = urlparse(proxy_str)
        if not parsed.scheme or not parsed.hostname or not parsed.port:
            _print('ERRO: proxy inválido. Use formato "http://user:pass@host:port" ou "user:pass:host:port"')
            return 2
        server = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
        username = parsed.username
        password = parsed.password
        proxy = ProxyConfig(server=server, username=username, password=password)
    # Alternativa: server + username/password separados
    elif args.proxy_server:
        proxy = ProxyConfig(
            server=args.proxy_server,
            username=args.proxy_username or None,
            password=args.proxy_password or None,
        )

    _print("=== LOGIN 7k.bet.br (manual) ===")
    _print(f"Base URL: {args.base_url}")
    _print(f"Headless: {args.headless}")
    _print(f"Proxy: {proxy.server if proxy else '(sem proxy)'}")
    _print(f"Logs: {log.path}")
    _print(f"Storage state: {args.storage_state}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context_kwargs: dict[str, Any] = {
            "locale": "pt-BR",
            "viewport": {"width": 1366, "height": 768},
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        if proxy:
            context_kwargs["proxy"] = proxy.to_playwright()

        context = browser.new_context(**context_kwargs)
        page = context.new_page()

        # filtros: reduz ruído e foca no login/auth/api
        def is_interesting(url: str) -> bool:
            u = url.lower()
            return (
                "/api/" in u
                or "/auth" in u
                or "login" in u
                or "session" in u
                or "me" in u
            )

        def on_request(req) -> None:
            try:
                if not is_interesting(req.url):
                    return
                post_data = req.post_data() or ""
                log.write(
                    "request",
                    {
                        "method": req.method,
                        "url": req.url,
                        "headers": _redact_headers(dict(req.headers)),
                        "post_data": _safe_trunc(post_data, 1500),
                    },
                )
                _print(f"[REQ] {req.method} {req.url}")
            except Exception as e:
                _print(f"[WARN] falha ao logar request: {e}")

        def on_response(resp) -> None:
            try:
                if not is_interesting(resp.url):
                    return
                body = ""
                try:
                    body = resp.text()
                except Exception:
                    body = "<unavailable>"
                log.write(
                    "response",
                    {
                        "url": resp.url,
                        "status": resp.status,
                        "headers": _redact_headers(dict(resp.headers)),
                        "body": _safe_trunc(body, 2000),
                    },
                )
                _print(f"[RES] {resp.status} {resp.url}")
            except Exception as e:
                _print(f"[WARN] falha ao logar response: {e}")

        page.on("request", on_request)
        page.on("response", on_response)

        # abre uma rota de login mais provável; se falhar, cai na home
        last_err: Optional[Exception] = None
        for path in DEFAULT_LOGIN_PATHS:
            try:
                url = args.base_url.rstrip("/") + path
                _print(f"Abrindo: {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                break
            except Exception as e:
                last_err = e
        else:
            _print(f"ERRO: não consegui abrir o site. Último erro: {last_err}")
            browser.close()
            log.close()
            return 1

        page.wait_for_timeout(2000)
        page.screenshot(path=str(screenshots_dir / f"login_7k_{ts}_01_loaded.png"), full_page=True)

        # tenta achar inputs de login/senha de forma resiliente
        login_input = page.locator('input[type="email"]').first
        if login_input.count() == 0:
            login_input = page.locator('input[name*="email" i], input[id*="email" i], input[autocomplete="username"]').first
        if login_input.count() == 0:
            # fallback: primeiro input "texto" que pareça login
            candidates = page.locator("input").all()
            chosen = None
            for c in candidates:
                try:
                    ph = c.get_attribute("placeholder") or ""
                    t = (c.get_attribute("type") or "").lower()
                    if t in ("text", "tel", "email") and _looks_like_login_field(ph):
                        chosen = c
                        break
                except Exception:
                    continue
            if chosen is not None:
                login_input = chosen

        password_input = page.locator('input[type="password"]').first

        _print("Preenchendo credenciais...")
        try:
            login_input.click(timeout=10_000)
            login_input.fill(args.email, timeout=10_000)
        except Exception as e:
            _print(f"[WARN] não consegui preencher o campo de login automaticamente: {e}")
        try:
            password_input.click(timeout=10_000)
            password_input.fill(args.password, timeout=10_000)
        except Exception as e:
            _print(f"[WARN] não consegui preencher o campo de senha automaticamente: {e}")

        page.screenshot(path=str(screenshots_dir / f"login_7k_{ts}_02_filled.png"), full_page=True)

        # tenta clicar num botão típico, mas deixa o usuário finalizar se necessário
        _print("Tentando clicar no botão de login (se encontrado)...")
        clicked = False
        for text in ("Entrar", "Acessar", "Login"):
            try:
                btn = page.get_by_role("button", name=re.compile(rf"^{re.escape(text)}$", re.I)).first
                if btn.count() > 0:
                    btn.click(timeout=5_000)
                    clicked = True
                    _print(f"Cliquei em: {text}")
                    break
            except Exception:
                continue

        if not clicked:
            _print("Não achei um botão óbvio. Você pode clicar manualmente.")

        _print("Agora resolva o Turnstile (se aparecer) e conclua o login no navegador.")
        _print(f"Vou esperar até {args.timeout_sec}s por uma requisição POST em /api/auth/login ...")

        login_resp = None
        deadline = time.time() + args.timeout_sec
        while time.time() < deadline:
            try:
                login_resp = page.wait_for_response(
                    lambda r: ("/api/auth/login" in r.url) and (r.request.method == "POST"),
                    timeout=5_000,
                )
                break
            except Exception:
                # ainda não rolou o POST; segue aguardando
                pass

        page.screenshot(path=str(screenshots_dir / f"login_7k_{ts}_03_after_wait.png"), full_page=True)

        if login_resp is None:
            _print("Timeout: não observei POST /api/auth/login. Verifique se o login foi concluído na UI.")
        else:
            _print(f"Recebi resposta do login: HTTP {login_resp.status} ({login_resp.url})")
            try:
                body = login_resp.text()
                _print("Body (parcial):")
                _print(_safe_trunc(body, 1200))
            except Exception as e:
                _print(f"[WARN] não consegui ler body da resposta: {e}")

        # salva estado da sessão (cookies + storage)
        try:
            context.storage_state(path=args.storage_state)
            _print(f"Session salva em: {args.storage_state}")
        except Exception as e:
            _print(f"[WARN] não consegui salvar storage_state: {e}")

        browser.close()
        log.close()

    _print("Fim.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


