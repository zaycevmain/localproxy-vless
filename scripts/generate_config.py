#!/usr/bin/env python3
"""Генерация client-конфига Xray из config/vless.url и config/proxy.json."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
VLESS_FILE = ROOT / "config" / "vless.url"
PROXY_FILE = ROOT / "config" / "proxy.json"
OUTPUT_FILE = ROOT / "var" / "config.json"

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
    values = params.get(key, [])
    return values[0] if values else default


def parse_vless(url: str) -> dict:
    url = url.strip()
    if not url.lower().startswith("vless://"):
        url = "vless://" + url.lstrip("/")

    parsed = urlparse(url)
    uuid = parsed.username
    if not uuid:
        raise ValueError("В VLESS-ссылке не найден UUID")

    host = parsed.hostname
    port = parsed.port or 443
    if not host:
        raise ValueError("В VLESS-ссылке не найден адрес сервера")

    params = parse_qs(parsed.query, keep_blank_values=True)
    remark = unquote(parsed.fragment) if parsed.fragment else "vless-upstream"

    transport = first_param(params, "type", "tcp").lower()
    network = NETWORK_MAP.get(transport, transport)
    security = first_param(params, "security", "none").lower()

    stream: dict = {"network": network}

    if security == "reality":
        reality = {
            "serverName": first_param(params, "sni"),
            "publicKey": first_param(params, "pbk"),
            "shortId": first_param(params, "sid"),
            "fingerprint": first_param(params, "fp", "chrome"),
        }
        spx = first_param(params, "spx")
        if spx:
            reality["spiderX"] = unquote(spx)
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
            "path": unquote(first_param(params, "path", "/")) or "/",
            "mode": first_param(params, "mode", "auto") or "auto",
        }
        host_header = first_param(params, "host")
        if host_header:
            xhttp["host"] = host_header

        extra: dict = {}
        extra_raw = first_param(params, "extra")
        if extra_raw:
            try:
                extra.update(json.loads(unquote(extra_raw)))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Не удалось разобрать extra в VLESS-ссылке: {exc}") from exc

        padding = first_param(params, "x_padding_bytes")
        if padding and "xPaddingBytes" not in extra:
            extra["xPaddingBytes"] = padding

        if extra:
            xhttp["extra"] = extra

        stream["xhttpSettings"] = xhttp
    elif network == "ws":
        stream["wsSettings"] = {
            "path": unquote(first_param(params, "path", "/")) or "/",
            "headers": {"Host": first_param(params, "host", host)},
        }
    elif network == "grpc":
        stream["grpcSettings"] = {
            "serviceName": first_param(params, "serviceName") or first_param(params, "service"),
            "multiMode": first_param(params, "mode") == "multi",
        }

    encryption = first_param(params, "encryption", "none") or "none"
    flow = first_param(params, "flow")

    user = {"id": uuid, "encryption": encryption}
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

    # proxy.json должен быть полноценным JSON-файлом без комментариев.
    # Читаем его целиком, а не одну строку, в отличие от vless.url.
    raw = PROXY_FILE.read_text(encoding="utf-8-sig")
    data = json.loads(raw)
    listen_host = data.get("listen_host", "0.0.0.0")
    http_active = bool(data.get("http_active", True))
    socks_active = bool(data.get("socks5_active", True))
    proxies = data.get("proxies") or data.get("proxy-list") or []

    if not isinstance(proxies, list):
        raise ValueError("proxy.json: поле proxies должно быть массивом")

    normalized = []
    for item in proxies:
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

        try:
            port = int(item["port"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Некорректный порт у прокси '{item.get('name')}': {item.get('port')}") from exc

        validate_port(port, item.get("name", "proxy"))
        normalized.append(
            {
                "name": str(item.get("name", f"{ptype}-{port}")),
                "type": ptype,
                "port": port,
                "user": str(item.get("user", "")),
                "password": str(item.get("password", "")),
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
        inbound = {
            **base,
            "protocol": "socks",
            "settings": {
                "auth": "password",
                "accounts": [{"user": proxy["user"], "pass": proxy["password"]}],
                "udp": True,
                "ip": listen_host,
            },
        }
    else:
        inbound = {
            **base,
            "protocol": "http",
            "settings": {
                "accounts": [{"user": proxy["user"], "pass": proxy["password"]}],
                "allowTransparent": False,
            },
        }

    return inbound


def build_config(vless: dict, proxy_cfg: dict) -> dict:
    inbounds = [build_inbound(p, proxy_cfg["listen_host"]) for p in proxy_cfg["proxies"]]
    inbound_tags = [i["tag"] for i in inbounds]

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
                    "inboundTag": inbound_tags,
                    "outboundTag": "proxy",
                }
            ],
        },
        "_meta": {
            "remark": vless["remark"],
            "upstream": f"{vless['address']}:{vless['port']}",
            "network": vless["streamSettings"].get("network"),
            "security": vless["streamSettings"].get("security"),
        },
    }


def main() -> int:
    try:
        vless_url = load_text(VLESS_FILE)
        vless = parse_vless(vless_url)
        proxy_cfg = load_proxy_config()
        config = build_config(vless, proxy_cfg)

        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        (ROOT / "var" / "log").mkdir(parents=True, exist_ok=True)

        with OUTPUT_FILE.open("w", encoding="utf-8") as fh:
            json.dump(config, fh, ensure_ascii=False, indent=2)

        meta_path = ROOT / "var" / "meta.json"
        meta = {
            "remark": config["_meta"]["remark"],
            "upstream": config["_meta"]["upstream"],
            "proxies": proxy_cfg["proxies"],
            "listen_host": proxy_cfg["listen_host"],
        }
        with meta_path.open("w", encoding="utf-8") as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=2)

        print(f"OK: {OUTPUT_FILE}")
        return 0
    except Exception as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
