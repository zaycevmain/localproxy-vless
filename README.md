# localproxy-vless

Локальные **HTTP** и **SOCKS5** прокси на вашем Linux-сервере. Весь трафик клиентов уходит через **VLESS** (xHTTP + Reality) на зарубежный сервер.

![Screenshot](https://github.com/zaycevmain/localproxy-vless/blob/main/pic.png)
```
[Телефон/ПК] ── HTTP/SOCKS5 ──► [Linux у вас] ── VLESS ──► [VPS за рубежом]
```

Управление — через **systemd**: автозапуск после перезагрузки, перезапуск при сбое.

---

## Что не трогается на хосте

- Нет глобального VPN/TUN, iptables, маршрутизации, DNS
- Слушаются только порты из `config/proxy.json`
- Xray лежит в `./bin/`, логи в `./var/log/`
- Сервис запускается от вашего пользователя (не root), если порты > 1024

---

## Требования

- Linux x86_64 или arm64
- `curl`, `unzip`, `python3`, `systemd`
- Свободные порты из `proxy.json` (не заняты другими сервисами)

---

## Установка с нуля

### 1. Скопируйте проект на сервер

Например:

```bash
/home/zaycevadmin/localproxy-vless
```

Дальше все команды — из этой папки.

### 2. Права и переводы строк (если копировали с Windows)

```bash
cd /home/zaycevadmin/localproxy-vless

sed -i 's/\r$//' install.sh scripts/*.sh systemd/*.sh
chmod +x install.sh scripts/run-foreground.sh scripts/check.sh systemd/install-systemd.sh
```

### 3. Установите Xray

```bash
./install.sh
```

Другая версия Xray:

```bash
XRAY_VERSION=26.5.9 ./install.sh
```

### 4. Настройте конфиги

```bash
cp config/vless.url.example config/vless.url
cp config/proxy.json.example config/proxy.json

nano config/vless.url    # одна строка vless://...
nano config/proxy.json   # порты, логины, пароли
```

**`config/vless.url`** — одна строка со ссылкой `vless://...` (строки с `#` в начале игнорируются).

**`config/proxy.json`** — JSON, пример:

```json
{
  "http_active": true,
  "socks5_active": true,
  "listen_host": "0.0.0.0",
  "proxies": [
    {
      "name": "MySocks5",
      "type": "socks5",
      "port": 1080,
      "user": "zaycevsocks5",
      "password": "секрет"
    },
    {
      "name": "MyHttp",
      "type": "http",
      "port": 3128,
      "user": "zaycevhttp",
      "password": "секрет"
    }
  ]
}
```

| Поле | Значение |
|------|----------|
| `listen_host` | `0.0.0.0` — доступ снаружи (через проброс на роутере); `127.0.0.1` — только с самого сервера |
| `http_active` / `socks5_active` | Включить соответствующие типы из списка `proxies` |

Проверка генерации конфига без запуска:

```bash
python3 scripts/generate_config.py
```

### 5. Установите systemd-сервис

Скрипт подставит путь к проекту и пользователя (того, кто вызвал `sudo`):

```bash
sudo ./systemd/install-systemd.sh
```

### 6. Включите автозапуск и запустите

```bash
sudo systemctl enable --now localproxy-vless
```

### 7. Проверьте, что всё работает

```bash
./scripts/check.sh
```

Или вручную:

```bash
systemctl status localproxy-vless --no-pager
journalctl -u localproxy-vless -n 50 --no-pager
```

---

## Проброс портов на роутере

Пробросьте **внешний порт → тот же порт на IP Linux-хоста**.

Подключение с устройства:

- SOCKS5: `socks5://USER:PASS@ВАШ_ВНЕШНИЙ_IP:ПОРТ`
- HTTP: `http://USER:PASS@ВАШ_ВНЕШНИЙ_IP:ПОРТ`

---

## Управление сервисом

| Действие | Команда |
|----------|---------|
| Статус | `systemctl status localproxy-vless` |
| Остановить | `sudo systemctl stop localproxy-vless` |
| Запустить | `sudo systemctl start localproxy-vless` |
| Перезапустить (после смены конфигов) | `sudo systemctl restart localproxy-vless` |
| Отключить автозапуск | `sudo systemctl disable localproxy-vless` |
| Логи systemd | `journalctl -u localproxy-vless -f` |

После изменения `config/vless.url` или `config/proxy.json` достаточно **перезапуска** — конфиг Xray пересобирается при каждом старте.

---

## Логи Xray

```bash
tail -f var/log/error.log
tail -f var/log/access.log
```

---

## Проверка «внешнего IP» через прокси

На сервере (подставьте свои логин/пароль/порт):

```bash
# SOCKS5
curl -s --socks5 "socks5://USER:PASS@127.0.0.1:1080" https://api.ipify.org ; echo

# HTTP
curl -s -x "http://USER:PASS@127.0.0.1:3128" https://api.ipify.org ; echo

# Без прокси (для сравнения)
curl -s https://api.ipify.org ; echo
```

Если IP через прокси отличается от прямого — трафик идёт через зарубежный VLESS.

Порты слушают:

```bash
ss -tulpen | grep -E '(:1080|:3128)\b'
```

---

## Устранение проблем

| Симптом | Решение |
|---------|---------|
| `bash\r: No such file or directory` | `sed -i 's/\r$//' install.sh scripts/*.sh systemd/*.sh` |
| `status=203/EXEC` в systemd | `sed -i 's/\r$//' scripts/*.sh && chmod +x scripts/run-foreground.sh`, затем `sudo ./systemd/install-systemd.sh` и `sudo systemctl restart localproxy-vless` |
| `status=200/CHDIR` | Проект в `/home/...` — переустановите unit: `sudo ./systemd/install-systemd.sh` (убраны `ProtectHome`/`ProtectSystem`) |
| `meta.json нет` | Сервис не стартовал. Сначала исправьте 203/EXEC, затем `python3 scripts/generate_config.py` |
| `Expecting property name enclosed in double quotes` | `proxy.json` должен быть валидным JSON (без комментариев). Обновите `scripts/generate_config.py` |
| Сервис `failed` | `journalctl -u localproxy-vless -n 100` и `var/log/error.log` |
| «Занятые порты» | Смените `port` в `proxy.json` или остановите конфликтующий сервис |
| Прокси есть, интернета нет | Проверьте VLESS-ссылку и доступность зарубежного сервера с хоста |

---

## Структура проекта

```
localproxy-vless/
  install.sh                 # скачать Xray в bin/
  scripts/
    generate_config.py       # vless.url + proxy.json → var/config.json
    run-foreground.sh        # старт для systemd
    check.sh                 # статус + проверка IP
  systemd/
    localproxy-vless.service # шаблон unit
    install-systemd.sh       # установка в /etc/systemd/system/
  config/
    vless.url                # ваша VLESS-ссылка (не в git)
    proxy.json               # локальные прокси (не в git)
  var/                       # сгенерированный конфиг и логи
  bin/xray                   # бинарник (не в git)
```

## Безопасность

- Сложные пароли на каждом прокси
- По возможности ограничьте доступ firewall по IP
- Не публикуйте `config/vless.url` и `config/proxy.json`
