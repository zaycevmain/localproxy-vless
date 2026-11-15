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

Например, клонируйте репозиторий:

```bash
git clone https://github.com/zaycevmain/localproxy-vless.git /home/zaycevadmin/localproxy-vless
cd /home/zaycevadmin/localproxy-vless
```

Можно также скопировать папку вручную (например, через `scp`). Дальше все
команды выполняются из папки проекта.

### 2. Права на скрипты

```bash
cd /home/zaycevadmin/localproxy-vless
chmod +x install.sh scripts/*.sh systemd/*.sh
```

Переводы строк Git приводит к LF автоматически (`.gitattributes`), а
`install-systemd.sh` дополнительно исправляет CRLF перед установкой.

### 3. Установите Xray

```bash
./install.sh
```

По умолчанию скрипт сам определяет последний релиз Xray на GitHub и
скачивает его. Xray не берётся из репозиториев дистрибутива, поэтому
«старая версия в apt/yum» на установку не влияет.

Если Xray уже установлен, повторный запуск ничего не меняет. Обновить до
последнего релиза или закрепить конкретную версию:

```bash
XRAY_VERSION=latest ./install.sh
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

`user` и `password` обязательны для каждого прокси, порты не должны повторяться.

Проверка генерации конфига без запуска:

```bash
python3 scripts/generate_config.py
```

Диагностика (без запуска сервиса):

```bash
python3 scripts/generate_config.py show    # список активных прокси
python3 scripts/generate_config.py ports   # свободны ли порты
python3 scripts/generate_config.py check   # внешний IP через каждый прокси
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

## Обновление проекта

```bash
cd /home/zaycevadmin/localproxy-vless
git pull
./install.sh                         # поставит Xray, если его ещё нет
XRAY_VERSION=latest ./install.sh     # при необходимости обновить Xray
sudo ./systemd/install-systemd.sh    # обновит unit, права и CRLF
sudo systemctl restart localproxy-vless
./scripts/check.sh
```

После обновления конфиг Xray пересобирается автоматически при рестарте.

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
curl -s --socks5-hostname "socks5://USER:PASS@127.0.0.1:1080" https://api.ipify.org ; echo

# HTTP
curl -s -x "http://USER:PASS@127.0.0.1:3128" https://api.ipify.org ; echo

# Без прокси (для сравнения)
curl -s https://api.ipify.org ; echo
```

Если IP через прокси отличается от прямого — трафик идёт через зарубежный VLESS.

Порты слушают:

```bash
sudo ss -tulpen | grep -i xray
```

---

## Устранение проблем

| Симптом | Решение |
|---------|---------|
| `bash\r: No such file or directory` | `sed -i 's/\r$//' install.sh scripts/*.sh systemd/*.sh` |
| `status=203/EXEC` в systemd | `sudo ./systemd/install-systemd.sh`, затем `sudo systemctl restart localproxy-vless` |
| `status=200/CHDIR` | Переустановите unit: `sudo ./systemd/install-systemd.sh` |
| `meta.json нет` | `python3 scripts/generate_config.py` (сначала исправьте ошибку из вывода) |
| `Не удалось определить последнюю версию Xray` | Проверьте доступ к GitHub или задайте версию: `XRAY_VERSION=26.5.9 ./install.sh` |
| `Expecting property name enclosed in double quotes` | `proxy.json` должен быть валидным JSON (без комментариев) |
| Сервис `failed` | `journalctl -u localproxy-vless -n 100` и `var/log/error.log` |
| «Занятые порты» | Смените `port` в `proxy.json` или остановите конфликтующий сервис |
| Прокси есть, интернета нет | Проверьте VLESS-ссылку и доступность зарубежного сервера с хоста |
| `должны быть заполнены user и password` | У каждого прокси в `proxy.json` не должно быть пустых логина/пароля |

---

## Структура проекта

```
localproxy-vless/
  install.sh                 # скачать Xray в bin/
  scripts/
    common.sh                # общие пути и функции
    generate_config.py       # generate / ports / show / check
    run-foreground.sh        # старт для systemd
    check.sh                 # статус + проверка IP
  systemd/
    localproxy-vless.service # шаблон unit
    install-systemd.sh       # установка в /etc/systemd/system/
  config/
    vless.url                # ваша VLESS-ссылка (не в git)
    proxy.json               # локальные прокси (не в git)
  var/                       # config.json, meta.json и логи
  bin/xray                   # бинарник (не в git)
```

## Безопасность

- Сложные пароли на каждом прокси; пустые `user`/`password` не принимаются
- По возможности ограничьте доступ firewall по IP
- Не публикуйте `config/vless.url` и `config/proxy.json`
