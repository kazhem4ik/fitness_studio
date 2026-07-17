# Настройка Cloudflare Tunnel для домашнего сервера

## Шаг 1: Перенести DNS на Cloudflare

1. Зайди на [dash.cloudflare.com](https://dash.cloudflare.com)
2. Нажми **"Add a site"** → введи `fit-nch.ru`
3. Выбери **Free plan**
4. Cloudflare покажет 2 nameserver'а, например:
   - `ada.ns.cloudflare.com`
   - `rick.ns.cloudflare.com`
5. Зайди в [reg.ru](https://www.reg.ru/user/account) → Домены → `fit-nch.ru` → DNS-серверы
6. Замени NS-записи на те, что дал Cloudflare
7. Подожди 10 мин — 24 часа (обычно ~30 мин)
8. В Cloudflare статус домена станет **"Active"** ✅

## Шаг 2: Установить Docker на Ubuntu

```bash
# Обновляем систему
sudo apt update && sudo apt upgrade -y

# Устанавливаем Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Добавляем пользователя в группу docker
sudo usermod -aG docker $USER

# Устанавливаем Docker Compose
sudo apt install docker-compose-plugin -y

# Проверяем
docker --version
docker compose version

# Перелогинься для применения группы
exit
```

## Шаг 3: Установить cloudflared на Ubuntu

```bash
# Скачиваем и устанавливаем
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb

# Проверяем
cloudflared --version
```

## Шаг 4: Авторизация cloudflared

```bash
cloudflared tunnel login
```

Откроется ссылка в браузере — выбери домен `fit-nch.ru` и авторизуй.

## Шаг 5: Создать туннель

```bash
# Создаём туннель
cloudflared tunnel create fitness-studio

# Запомни ID туннеля (выведется в консоли), например: a1b2c3d4-...
```

## Шаг 6: Конфигурация туннеля

Создай файл конфигурации:

```bash
nano ~/.cloudflared/config.yml
```

Содержимое:

```yaml
tunnel: <ID_ТУННЕЛЯ>
credentials-file: /home/<USER>/.cloudflared/<ID_ТУННЕЛЯ>.json

ingress:
  - hostname: fit-nch.ru
    service: http://localhost:80
  - hostname: www.fit-nch.ru
    service: http://localhost:80
  - service: http_status:404
```

Замени `<ID_ТУННЕЛЯ>` и `<USER>` на свои значения.

## Шаг 7: Добавить DNS-запись

```bash
cloudflared tunnel route dns fitness-studio fit-nch.ru
cloudflared tunnel route dns fitness-studio www.fit-nch.ru
```

## Шаг 8: Запустить туннель

```bash
# Тестовый запуск
cloudflared tunnel run fitness-studio

# Если всё ок — установить как системный сервис
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared

# Проверка
sudo systemctl status cloudflared
```

## Шаг 9: Запустить проект

```bash
# Клонируй репозиторий на сервер
git clone <URL_РЕПОЗИТОРИЯ> ~/fitness-studio
cd ~/fitness-studio/fitness_studio_mono

# Скопируй .env файл
cp .env.example .env
nano .env  # Заполни переменные

# Создай админа для планнера
docker compose run --rm planner_service python -m planner_service.scripts.create_admin

# Запусти всё
docker compose up -d

# Проверь логи
docker compose logs -f
```

## Шаг 10: Проверка

1. Открой `https://fit-nch.ru` — должен открыться лендинг
2. Открой `https://fit-nch.ru/clients` — должен открыться планнер
3. На iPhone: Safari → `fit-nch.ru/clients` → Поделиться → "На экран Домой"
4. Войди по логину/паролю → Safari предложит сохранить в Keychain
5. В следующий раз при входе iPhone предложит FaceID для автозаполнения

## Полезные команды

```bash
# Перезапуск
docker compose restart

# Обновление (после git pull)
docker compose build && docker compose up -d

# Логи конкретного сервиса
docker compose logs -f planner_service

# Статус туннеля
sudo systemctl status cloudflared
```
