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
    echo "  chmod +x scripts/run-foreground.sh"
    echo "  sudo ./systemd/install-systemd.sh && sudo systemctl restart localproxy-vless"
    echo ""
  elif [[ "${code}" == "200" ]]; then
    echo ""
    echo "Подсказка: status=200/CHDIR — не удалось открыть WorkingDirectory."
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
run_config check

echo ""
echo "Логи: journalctl -u ${SERVICE} -f"
echo "      tail -f ${LOG_DIR}/error.log"
