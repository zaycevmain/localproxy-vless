#!/usr/bin/env bash
# Проверка: systemd, порты, внешний IP через каждый прокси

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/common.sh
source "${SCRIPT_DIR}/common.sh"

SERVICE="localproxy-vless"

echo "=== systemd: ${SERVICE} ==="
if systemctl is-active --quiet "${SERVICE}" 2>/dev/null; then
  echo "Статус: active (running)"
else
  echo "Статус: не active (см. systemctl status ${SERVICE})"
  code="$(systemctl show "${SERVICE}" -p ExecMainStatus --value 2>/dev/null || true)"
  if [[ "${code}" == "203" ]]; then
    echo ""
    echo "Подсказка: status=203/EXEC — systemd не смог запустить скрипт."
    echo "  sed -i 's/\\r$//' install.sh scripts/*.sh systemd/*.sh"
    echo "  chmod +x scripts/run-foreground.sh"
    echo "  sudo ./systemd/install-systemd.sh && sudo systemctl restart localproxy-vless"
    echo ""
  elif [[ "${code}" == "200" ]]; then
    echo ""
    echo "Подсказка: status=200/CHDIR — не удалось открыть WorkingDirectory (часто из-за ProtectHome)."
    echo "  sudo ./systemd/install-systemd.sh && sudo systemctl restart localproxy-vless"
    echo ""
  fi
fi
systemctl status "${SERVICE}" --no-pager -l 2>/dev/null | head -n 15 || true
echo ""

if [[ ! -f "${META_FILE}" ]]; then
  log "meta.json нет — сгенерируйте: python3 scripts/generate_config.py"
  exit 1
fi

print_proxies

echo "=== Проверка IP (через api.ipify.org) ==="
DIRECT_IP="$(curl -fsS --max-time 15 https://api.ipify.org 2>/dev/null || echo 'ошибка')"
echo "Прямой IP сервера:     ${DIRECT_IP}"
echo ""

python3 - <<'PY' "${META_FILE}"
import json, subprocess, sys
from pathlib import Path

meta = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

for p in meta.get("proxies", []):
    name = p["name"]
    port = p["port"]
    user = p["user"]
    password = p["password"]
    ptype = p["type"]

    if ptype == "socks5":
        cmd = [
            "curl", "-fsS", "--max-time", "20",
            "--socks5", f"socks5://{user}:{password}@127.0.0.1:{port}",
            "https://api.ipify.org",
        ]
    else:
        cmd = [
            "curl", "-fsS", "--max-time", "20",
            "-x", f"http://{user}:{password}@127.0.0.1:{port}",
            "https://api.ipify.org",
        ]

    try:
        out = subprocess.check_output(cmd, text=True).strip()
    except subprocess.CalledProcessError:
        out = "ошибка (прокси не отвечает или неверный логин)"

    print(f"[{name}] {ptype} :{port} -> IP: {out}")
PY

echo ""
echo "Логи: journalctl -u ${SERVICE} -f"
echo "      tail -f ${LOG_DIR}/error.log"
