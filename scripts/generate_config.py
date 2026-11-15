#!/usr/bin/env python3
"""Генерация и диагностика конфигурации Xray.

Команды:
  generate (по умолчанию)  config/vless.url + config/proxy.json -> var/config.json
  ports                    проверить, свободны ли порты из meta.json
  show                     показать активные прокси
  check                    проверить внешний IP через каждый прокси
"""

from __future__ import annotations

import json
import re
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
VLESS_FILE = ROOT / "config" / "vless.url"
PROXY_FILE = ROOT / "config" / "proxy.json"
OUTPUT_FILE = ROOT / "var" / "config.json"
META_FILE = ROOT / "var" / "meta.json"

NETWORK_MAP = {
    "xhttp": "xhttp",
    "splithttp": "xhttp",
    "tcp": "tcp",
    "ws": "ws",
    "grpc": "grpc",
    "httpupgrade": "httpupgrade",
    "h2": "h2",
}


def load_text(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Файл не найден: {path}")
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    raise ValueError(f"Заполните {path} (сейчас пусто или только комментарии)")


def first_param(params: dict, key: str, default: str = "") -> str:
    values = params.get(key) or []
    return (values[0] if values else "") or default


def parse_vless(url: str) -> dict:
    url = url.strip()
    if not url.lower().startswith("vless://"):
        url = "vless://" + url.lstrip("/")

    parsed = urlparse(url)
    uuid = parsed.username
    if not uuid:
        raise ValueError("В VLESS-ссылке не найден UUID")

    host = parsed.hostname
    if not host:
        raise ValueError("В VLESS-ссылке не найден адрес сервера")
    try:
        port = parsed.port or 443
    except ValueError as exc:
        raise ValueError(f"Некорректный порт в VLESS-ссылке: {exc}") from exc

    params = parse_qs(parsed.query, keep_blank_values=True)
    remark = unquote(parsed.fragment) if parsed.fragment else "vless-upstream"

    transport = first_param(params, "type", "tcp").lower()
    network = NETWORK_MAP.get(transport, transport)
    security = first_param(params, "security", "none").lower()

    stream: dict = {"network": network}

    if security == "reality":
        sni = first_param(params, "sni", host)
        public_key = first_param(params, "pbk")
        if not public_key:
            raise ValueError("В VLESS-ссылке security=reality требует параметр pbk")

        reality = {
            "serverName": sni,
            "publicKey": public_key,
            "shortId": first_param(params, "sid"),
            "fingerprint": first_param(params, "fp", "chrome"),
        }
        spider_x = first_param(params, "spx")
        if spider_x:
            reality["spiderX"] = spider_x
        stream["security"] = "reality"
        stream["realitySettings"] = reality
    elif security == "tls":
        stream["security"] = "tls"
        stream["tlsSettings"] = {
            "serverName": first_param(params, "sni", host),
            "fingerprint": first_param(params, "fp", "chrome"),
            "allowInsecure": first_param(params, "allowinsecure", "0") == "1",
        }

    if network == "xhttp":
        xhttp: dict = {
            "path": first_param(params, "path", "/"),
            "mode": first_param(params, "mode", "auto"),
        }
        host_header = first_param(params, "host")
        if host_header:
            xhttp["host"] = host_header

        extra: dict = {}
        extra_raw = first_param(params, "extra")
        if extra_raw:
            try:
                extra = json.loads(extra_raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Не удалось разобрать extra в VLESS-ссылке: {exc}") from exc
            if not isinstance(extra, dict):
                raise ValueError("Параметр extra в VLESS-ссылке должен быть JSON-объектом")

        padding = first_param(params, "x_padding_bytes")
        if padding and "xPaddingBytes" not in extra:
            extra["xPaddingBytes"] = padding

        if extra:
            xhttp["extra"] = extra

        stream["xhttpSettings"] = xhttp
    elif network == "ws":
        stream["wsSettings"] = {
            "path": first_param(params, "path", "/"),
            "headers": {"Host": first_param(params, "host", host)},
        }
    elif network == "grpc":
        stream["grpcSettings"] = {
            "serviceName": first_param(params, "serviceName") or first_param(params, "service"),
            "multiMode": first_param(params, "mode") == "multi",
        }

    user = {
        "id": uuid,
        "encryption": first_param(params, "encryption", "none"),
    }
    flow = first_param(params, "flow")
    if flow:
        user["flow"] = flow

    return {
        "remark": remark,
        "address": host,
        "port": port,
        "user": user,
        "streamSettings": stream,
    }


def validate_port(port: int, name: str) -> None:
    if port < 1 or port > 65535:
        raise ValueError(f"{name}: порт {port} вне диапазона 1-65535")


def load_proxy_config() -> dict:
    if not PROXY_FILE.is_file():
        raise FileNotFoundError(f"Файл не найден: {PROXY_FILE}")

    data = json.loads(PROXY_FILE.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("proxy.json: корневой элемент должен быть объектом")

    listen_host = str(data.get("listen_host", "0.0.0.0")).strip() or "0.0.0.0"
    http_active = bool(data.get("http_active", True))
    socks_active = bool(data.get("socks5_active", True))
    proxies = data.get("proxies") or data.get("proxy-list") or []

    if not isinstance(proxies, list):
        raise ValueError("proxy.json: поле proxies должно быть массивом")

    normalized = []
    ports: set[int] = set()

    for item in proxies:
        if not isinstance(item, dict):
            raise ValueError("proxy.json: каждый элемент proxies должен быть объектом")

        ptype = str(item.get("type", "")).lower()
        if ptype in ("socks", "socks5"):
            ptype = "socks5"
        elif ptype in ("http", "https"):
            ptype = "http"
        else:
            raise ValueError(f"Неизвестный тип прокси '{item.get('type')}' у {item.get('name')}")

        if ptype == "http" and not http_active:
            continue
        if ptype == "socks5" and not socks_active:
            continue

        name = str(item.get("name") or f"{ptype}-{item.get('port')}")
        try:
            port = int(item["port"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Некорректный порт у прокси '{name}': {item.get('port')}") from exc

        validate_port(port, name)
        if port in ports:
            raise ValueError(f"Порт {port} указан у нескольких прокси")
        ports.add(port)

        user = str(item.get("user", ""))
        password = str(item.get("password", ""))
        if not user or not password:
            raise ValueError(f"У прокси '{name}' должны быть заполнены user и password")

        normalized.append(
            {
                "name": name,
                "type": ptype,
                "port": port,
                "user": user,
                "password": password,
            }
        )

    if not normalized:
        raise ValueError("Нет активных прокси. Проверьте proxies и флаги http_active/socks5_active")

    return {
        "listen_host": listen_host,
        "proxies": normalized,
    }


def build_inbound(proxy: dict, listen_host: str) -> dict:
    tag = re.sub(r"[^a-zA-Z0-9_-]", "-", proxy["name"]).strip("-") or "proxy"
    tag = f"{proxy['type']}-{tag}-{proxy['port']}"

    base = {
        "listen": listen_host,
        "port": proxy["port"],
        "tag": tag,
        "sniffing": {
            "enabled": True,
            "destOverride": ["http", "tls", "quic"],
        },
    }

    if proxy["type"] == "socks5":
        return {
            **base,
            "protocol": "socks",
            "settings": {
                "auth": "password",
                "accounts": [{"user": proxy["user"], "pass": proxy["password"]}],
                "udp": True,
                "ip": listen_host,
            },
        }

    return {
        **base,
        "protocol": "http",
        "settings": {
            "accounts": [{"user": proxy["user"], "pass": proxy["password"]}],
            "allowTransparent": False,
        },
    }


def build_config(vless: dict, proxy_cfg: dict) -> dict:
    inbounds = [build_inbound(p, proxy_cfg["listen_host"]) for p in proxy_cfg["proxies"]]

    outbound = {
        "tag": "proxy",
        "protocol": "vless",
        "settings": {
            "vnext": [
                {
                    "address": vless["address"],
                    "port": vless["port"],
                    "users": [vless["user"]],
                }
            ]
        },
        "streamSettings": vless["streamSettings"],
    }

    return {
        "log": {
            "loglevel": "warning",
            "access": str(ROOT / "var" / "log" / "access.log"),
            "error": str(ROOT / "var" / "log" / "error.log"),
        },
        "inbounds": inbounds,
        "outbounds": [
            outbound,
            {"tag": "direct", "protocol": "freedom"},
            {"tag": "block", "protocol": "blackhole"},
        ],
        "routing": {
            "domainStrategy": "AsIs",
            "rules": [
                {
                    "type": "field",
                    "inboundTag": [i["tag"] for i in inbounds],
                    "outboundTag": "proxy",
                }
            ],
        },
    }


def load_meta() -> dict:
    if not META_FILE.is_file():
        raise FileNotFoundError(
            "meta.json не найден. Сначала сгенерируйте конфиг: "
            "python3 scripts/generate_config.py"
        )
    return json.loads(META_FILE.read_text(encoding="utf-8"))


def check_ports_free(meta: dict) -> int:
    listen_host = str(meta.get("listen_host") or "0.0.0.0")
    family = socket.AF_INET6 if ":" in listen_host else socket.AF_INET
    busy = []

    for proxy in meta.get("proxies", []):
        port = int(proxy["port"])
        sock = socket.socket(family, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((listen_host, port))
        except OSError:
            busy.append(port)
        finally:
            sock.close()

    if busy:
        print("Занятые порты: " + ", ".join(map(str, busy)), file=sys.stderr)
        return 1
    return 0


def show(meta: dict) -> None:
    print("=== Активные прокси ===")
    print(f"Upstream (VLESS): {meta.get('remark')} -> {meta.get('upstream')}")
    print(f"Слушаем на:       {meta.get('listen_host')}")
    print("")

    host = str(meta.get("listen_host") or "0.0.0.0")
    for proxy in meta.get("proxies", []):
        scheme = "socks5" if proxy["type"] == "socks5" else "http"
        print(f"  [{proxy['name']}] {scheme.upper()}  {host}:{proxy['port']}")
        print(f"    user: {proxy['user']}")
        print(f"    pass: {proxy['password']}")
        print(f"    url:  {scheme}://{proxy['user']}:***@ВАШ_IP:{proxy['port']}")
        print("")

    print(f"Конфиг Xray: {OUTPUT_FILE}")
    print(f"Логи:        {OUTPUT_FILE.parent / 'log'}")
    print("")


def run_curl(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["curl", "-fsS", "--max-time", "20", *args],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def check(meta: dict) -> None:
    direct = run_curl(["--noproxy", "*", "https://api.ipify.org"]) or "ошибка"
    print("=== Проверка IP (через api.ipify.org) ===")
    print(f"Прямой IP сервера:     {direct}")
    print("")

    for proxy in meta.get("proxies", []):
        user = quote(str(proxy["user"]), safe="")
        password = quote(str(proxy["password"]), safe="")
        port = proxy["port"]

        if proxy["type"] == "socks5":
            target = f"socks5://{user}:{password}@127.0.0.1:{port}"
            args = ["--socks5-hostname", target]
        else:
            target = f"http://{user}:{password}@127.0.0.1:{port}"
            args = ["-x", target]

        ip = run_curl([*args, "https://api.ipify.org"])
        ip = ip or "ошибка (прокси не отвечает или неверный логин)"
        print(f"[{proxy['name']}] {proxy['type']} :{port} -> IP: {ip}")


def generate() -> None:
    vless = parse_vless(load_text(VLESS_FILE))
    proxy_cfg = load_proxy_config()
    config = build_config(vless, proxy_cfg)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    (ROOT / "var" / "log").mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as fh:
        json.dump(config, fh, ensure_ascii=False, indent=2)

    meta = {
        "remark": vless["remark"],
        "upstream": f"{vless['address']}:{vless['port']}",
        "proxies": proxy_cfg["proxies"],
        "listen_host": proxy_cfg["listen_host"],
    }
    with META_FILE.open("w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)

    print(f"OK: {OUTPUT_FILE}")


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "generate"
    try:
        if command == "generate":
            generate()
        elif command == "ports":
            return check_ports_free(load_meta())
        elif command == "show":
            show(load_meta())
        elif command == "check":
            check(load_meta())
        else:
            print(f"Неизвестная команда: {command}", file=sys.stderr)
            print("Использование: generate_config.py [generate|ports|show|check]", file=sys.stderr)
            return 2
        return 0
    except Exception as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
