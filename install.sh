#!/usr/bin/env bash
# Скачивает Xray-core в ./bin/xray (не трогает системные пакеты)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/common.sh
source "${SCRIPT_DIR}/scripts/common.sh"

REQUESTED_VERSION="${XRAY_VERSION:-}"
RESOLVE_LATEST=0

if [[ "${REQUESTED_VERSION}" == "latest" ]]; then
  REQUESTED_VERSION=""
  RESOLVE_LATEST=1
else
  REQUESTED_VERSION="${REQUESTED_VERSION#v}"
fi

installed_version() {
  "${XRAY_BIN}" version 2>/dev/null | awk 'NR==1 {print $2}'
}

resolve_latest_version() {
  local url tag
  command -v curl >/dev/null 2>&1 || return 1

  url="$(curl -fsSIL -o /dev/null -w '%{url_effective}' \
    https://github.com/XTLS/Xray-core/releases/latest 2>/dev/null || true)"
  if [[ -z "${url}" ]]; then
    url="$(curl -fsSL -o /dev/null -w '%{url_effective}' \
      https://github.com/XTLS/Xray-core/releases/latest 2>/dev/null || true)"
  fi

  tag="${url##*/}"
  tag="${tag#v}"
  [[ "${tag}" =~ ^[0-9]+\.[0-9]+ ]] || return 1
  printf '%s\n' "${tag}"
}

if [[ -x "${XRAY_BIN}" ]]; then
  installed="$(installed_version || true)"

  if [[ -z "${installed}" && -z "${REQUESTED_VERSION}" ]]; then
    RESOLVE_LATEST=1
  fi

  if [[ "${RESOLVE_LATEST}" == "0" && -z "${REQUESTED_VERSION}" && -n "${installed}" ]]; then
    log "Xray уже установлен: ${installed}"
    log "Обновить до последней версии: XRAY_VERSION=latest ./install.sh"
    log "Закрепить версию:             XRAY_VERSION=26.5.9 ./install.sh"
    exit 0
  fi

  if [[ "${RESOLVE_LATEST}" == "1" ]]; then
    resolved="$(resolve_latest_version || true)"
    [[ -n "${resolved}" ]] || die "Не удалось определить последнюю версию Xray. Проверьте сеть или задайте XRAY_VERSION вручную."
    REQUESTED_VERSION="${resolved}"
  fi

  if [[ -n "${installed}" && "${REQUESTED_VERSION}" == "${installed}" ]]; then
    log "Xray ${installed} уже установлен"
    exit 0
  fi

  log "Замена Xray ${installed:-?} -> ${REQUESTED_VERSION}"
else
  if [[ "${RESOLVE_LATEST}" == "1" || -z "${REQUESTED_VERSION}" ]]; then
    resolved="$(resolve_latest_version || true)"
    [[ -n "${resolved}" ]] || die "Не удалось определить последнюю версию Xray. Проверьте сеть или задайте XRAY_VERSION вручную."
    REQUESTED_VERSION="${resolved}"
  fi
fi

XRAY_VERSION="${REQUESTED_VERSION}"
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
