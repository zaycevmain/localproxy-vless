#!/usr/bin/env bash
# Установка systemd unit с подстановкой пути и пользователя

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

SERVICE_NAME="localproxy-vless.service"
SRC_SERVICE="${ROOT_DIR}/systemd/${SERVICE_NAME}"
DST_SERVICE="/etc/systemd/system/${SERVICE_NAME}"

if [[ $EUID -ne 0 ]]; then
  echo "Запустите от root: sudo ./systemd/install-systemd.sh" >&2
  exit 1
fi

if [[ ! -f "${SRC_SERVICE}" ]]; then
  echo "Не найден unit: ${SRC_SERVICE}" >&2
  exit 1
fi

RUN_USER="${SUDO_USER:-root}"
if [[ "${RUN_USER}" == "root" ]]; then
  echo "Запускайте через sudo от обычного пользователя, например:" >&2
  echo "  sudo ./systemd/install-systemd.sh" >&2
  exit 1
fi

RUN_GROUP="$(id -gn "${RUN_USER}")"

# Убрать Windows-переводы строк и выставить +x (иначе systemd: status=203/EXEC)
while IFS= read -r -d '' script; do
  sed -i 's/\r$//' "${script}"
  chmod +x "${script}"
done < <(find "${ROOT_DIR}" -name '*.sh' -print0)

sed \
  -e "s|__USER__|${RUN_USER}|g" \
  -e "s|__GROUP__|${RUN_GROUP}|g" \
  -e "s|__ROOT__|${ROOT_DIR}|g" \
  "${SRC_SERVICE}" >"${DST_SERVICE}"

chmod 644 "${DST_SERVICE}"
systemctl daemon-reload

echo ""
echo "Установлен: ${DST_SERVICE}"
echo "  User:    ${RUN_USER}"
echo "  Group:   ${RUN_GROUP}"
echo "  Project: ${ROOT_DIR}"
echo ""
echo "Проверка конфига (от пользователя ${RUN_USER}):"
sudo -u "${RUN_USER}" python3 "${ROOT_DIR}/scripts/generate_config.py" || true
echo ""
echo "Дальше:"
echo "  sudo systemctl restart localproxy-vless"
echo "  ./scripts/check.sh"
echo ""
