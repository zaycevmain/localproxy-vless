#!/usr/bin/env bash
# Запуск под systemd (foreground, без nohup и PID-файла)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/common.sh
source "${SCRIPT_DIR}/common.sh"

[[ -x "${XRAY_BIN}" ]] || die "Не найден ${XRAY_BIN}. Сначала выполните: ./install.sh"
[[ -f "${ROOT_DIR}/config/vless.url" ]] || die "Создайте config/vless.url (см. config/vless.url.example)"
[[ -f "${ROOT_DIR}/config/proxy.json" ]] || die "Создайте config/proxy.json (см. config/proxy.json.example)"

if ! command -v python3 >/dev/null 2>&1; then
  die "Нужен python3"
fi

log "Генерация конфига..."
python3 "${ROOT_DIR}/scripts/generate_config.py" || die "Ошибка генерации конфига"

if ! check_ports_free; then
  die "Один или несколько портов уже заняты на этом хосте. Проверьте proxy.json или остановите конфликтующий сервис."
fi

log "Старт Xray в foreground (systemd будет управлять процессом)"
exec "${XRAY_BIN}" run -config "${CONFIG_FILE}"

