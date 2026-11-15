#!/usr/bin/env bash
# Скачивает Xray-core в ./bin/xray (не трогает системные пакеты)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/common.sh
source "${SCRIPT_DIR}/scripts/common.sh"

DEFAULT_XRAY_VERSION="26.4.15"
REQUESTED_VERSION="${XRAY_VERSION:-}"

installed_version() {
  "${XRAY_BIN}" version 2>/dev/null | awk 'NR==1 {print $2}'
}

if [[ -x "${XRAY_BIN}" ]]; then
  installed="$(installed_version || true)"
  if [[ -z "${REQUESTED_VERSION}" && -n "${installed}" ]]; then
    log "Xray уже установлен: ${installed} (задайте XRAY_VERSION, чтобы заменить)"
    exit 0
  fi
  if [[ "${REQUESTED_VERSION}" == "${installed}" ]]; then
    log "Xray ${installed} уже установлен"
    exit 0
  fi
  if [[ -n "${REQUESTED_VERSION}" ]]; then
    log "Замена Xray ${installed:-?} -> ${REQUESTED_VERSION}"
  fi
fi

XRAY_VERSION="${REQUESTED_VERSION:-${DEFAULT_XRAY_VERSION}}"
ARCH_SUFFIX="$(detect_arch)"

for tool in curl unzip; do
  command -v "${tool}" >/dev/null 2>&1 || die "Нужен ${tool}: sudo apt install ${tool}"
done

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT
mkdir -p "${BIN_DIR}"

ZIP_NAME="Xray-linux-${ARCH_SUFFIX}.zip"
URL="https://github.com/XTLS/Xray-core/releases/download/v${XRAY_VERSION}/${ZIP_NAME}"

log "Скачиваю Xray v${XRAY_VERSION} (${ARCH_SUFFIX})..."
if ! curl -fsSL -o "${TMP_DIR}/${ZIP_NAME}" "${URL}"; then
  die "Не удалось скачать ${URL}. Проверьте сеть или задайте XRAY_VERSION вручную."
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
