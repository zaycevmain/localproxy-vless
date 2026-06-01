#!/usr/bin/env bash
# Общие функции

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

BIN_DIR="${ROOT_DIR}/bin"
VAR_DIR="${ROOT_DIR}/var"
LOG_DIR="${VAR_DIR}/log"
CONFIG_FILE="${VAR_DIR}/config.json"
META_FILE="${VAR_DIR}/meta.json"
XRAY_BIN="${BIN_DIR}/xray"

mkdir -p "${LOG_DIR}" "${ROOT_DIR}/config"

log() {
  printf '[localproxy] %s\n' "$*"
}

die() {
  log "ОШИБКА: $*"
  exit 1
}

detect_arch() {
  local arch
  arch="$(uname -m)"
  case "${arch}" in
    x86_64|amd64) echo "64" ;;
    aarch64|arm64) echo "arm64-v8a" ;;
    armv7l) echo "arm32-v7a" ;;
    *) die "Неподдерживаемая архитектура: ${arch}" ;;
  esac
}

check_ports_free() {
  python3 - <<'PY' "${META_FILE}"
import json, socket, sys
from pathlib import Path

meta_path = Path(sys.argv[1])
if not meta_path.is_file():
    print("meta.json не найден", file=sys.stderr)
    sys.exit(1)

meta = json.loads(meta_path.read_text(encoding="utf-8"))
busy = []
for proxy in meta.get("proxies", []):
    port = int(proxy["port"])
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("0.0.0.0", port))
    except OSError:
        busy.append(port)
    finally:
        sock.close()

if busy:
    print("Занятые порты: " + ", ".join(map(str, busy)), file=sys.stderr)
    sys.exit(1)
PY
}

print_proxies() {
  if [[ ! -f "${META_FILE}" ]]; then
    log "meta.json не найден"
    return
  fi

  python3 - <<'PY' "${META_FILE}" "${CONFIG_FILE}"
import json, sys
from pathlib import Path

meta = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
cfg_path = Path(sys.argv[2])

print("=== Активные прокси ===")
print(f"Upstream (VLESS): {meta.get('remark')} -> {meta.get('upstream')}")
print(f"Слушаем на:       {meta.get('listen_host')}")
print("")

for p in meta.get("proxies", []):
    host = meta.get("listen_host", "0.0.0.0")
    scheme = "socks5" if p["type"] == "socks5" else "http"
    print(f"  [{p['name']}] {scheme.upper()}  {host}:{p['port']}")
    print(f"    user: {p['user']}")
    print(f"    pass: {p['password']}")
    if scheme == "socks5":
        print(f"    url:  socks5://{p['user']}:***@ВАШ_IP:{p['port']}")
    else:
        print(f"    url:  http://{p['user']}:***@ВАШ_IP:{p['port']}")
    print("")

print(f"Конфиг Xray: {cfg_path}")
print(f"Логи:        {cfg_path.parent / 'log'}")
print("")
PY
}
