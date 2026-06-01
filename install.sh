#!/usr/bin/env bash
# Скачивает Xray-core в ./bin/xray (не трогает системные пакеты)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/common.sh
source "${SCRIPT_DIR}/scripts/common.sh"

XRAY_VERSION="${XRAY_VERSION:-26.4.15}"
ARCH_SUFFIX="$(detect_arch)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

mkdir -p "${BIN_DIR}"

if [[ -x "${XRAY_BIN}" ]]; then
  log "Xray уже установлен: $(${XRAY_BIN} version 2>/dev/null | head -n1 || echo 'ok')"
  exit 0
fi

ZIP_NAME="Xray-linux-${ARCH_SUFFIX}.zip"
URL="https://github.com/XTLS/Xray-core/releases/download/v${XRAY_VERSION}/${ZIP_NAME}"

log "Скачиваю Xray v${XRAY_VERSION} (${ARCH_SUFFIX})..."
if ! curl -fsSL -o "${TMP_DIR}/${ZIP_NAME}" "${URL}"; then
  die "Не удалось скачать ${URL}. Проверьте сеть или задайте XRAY_VERSION вручную."
fi

if ! command -v unzip >/dev/null 2>&1; then
  die "Нужен unzip: sudo apt install unzip  (или yum install unzip)"
fi

unzip -q "${TMP_DIR}/${ZIP_NAME}" -d "${TMP_DIR}"
install -m 755 "${TMP_DIR}/xray" "${XRAY_BIN}"

log "Установлено: $(${XRAY_BIN} version | head -n1)"
log ""
log "Дальше:"
log "  1) cp config/vless.url.example config/vless.url"
log "  2) cp config/proxy.json.example config/proxy.json"
log "  3) отредактируйте оба файла"
log "  4) sudo ./systemd/install-systemd.sh"
log "  5) sudo systemctl enable --now localproxy-vless"
