#!/usr/bin/env bash
# Общие пути и функции проекта.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

BIN_DIR="${ROOT_DIR}/bin"
VAR_DIR="${ROOT_DIR}/var"
LOG_DIR="${VAR_DIR}/log"
CONFIG_FILE="${VAR_DIR}/config.json"
META_FILE="${VAR_DIR}/meta.json"
XRAY_BIN="${BIN_DIR}/xray"

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

run_config() {
  python3 "${SCRIPT_DIR}/generate_config.py" "$@"
}

check_ports_free() {
  run_config ports
}

print_proxies() {
  run_config show
}
