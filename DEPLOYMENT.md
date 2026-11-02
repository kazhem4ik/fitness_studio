# Руководство по развертыванию и эксплуатации (Deployment Guide)
**Проект:** Fitness Studio Monorepo  
**Домен:** [fit-nch.ru](https://fit-nch.ru)  
**Боевой сервер:** `<IP_ВАШЕГО_СЕРВЕРА>`

---

## 1. Архитектура и стек технологий

Проект представляет собой монорепозиторий автоматизации фитнес-студии:
* **`landing_page`** — Статический промо-сайт студии (HTML5/CSS3/Vanilla JS).
* **`bot_service`** — Telegram-бот для клиентов и тренеров (Python 3.11+, FastAPI, aiosqlite, Telegram Bot API).
* **`planner_service`** — CRM-система и веб-ежедневник тренера (FastAPI, SQLAlchemy, PWA, Web Push VAPID, JWT-аутентификация).
* **`nginx (container)`** — Маршрутизатор внутри Docker-сети, отдаёт статику лендинга/PWA и проксирует запросы к сервисам на `127.0.0.1:8080`.
* **`host nginx`** — Внешний веб-сервер хоста, принимающий трафик `80/443` и проксирующий его на `127.0.0.1:8080`.
* **База данных** — SQLite с WAL-режимом (`database/planner.db`), смонтированная volume в контейнеры.
* **Бэкапы** — Systemd Timer + Service с ротацией и сжатием (`scripts/backup_databases.py`).

### Системные требования:
* **ОС:** Ubuntu 22.04 LTS / Debian 12
* **Docker:** v24.0+ с плагином Docker Compose v2 (`docker compose`)
* **Nginx:** 1.18+ (на хосте)
* **Python:** 3.11+ (для локальных сервисных скриптов и бэкапов)
* **Минимальные ресурсы:** 1 vCPU, 1 GB RAM, 10 GB NVMe SSD

---

## 2. Параметры сервера и подключение

| Параметр | Значение |
| :--- | :--- |
| **IP-адрес / Хост** | `<IP_СЕРВЕРА>` (или `fit-nch.ru`) |
| **Пользователь** | `root` (сервисный пользователь: `agent`) |
| **Рабочая директория** | `/home/agent/fitness_studio` |
| **SSH-ключ (OpenSSH)** | `<путь_к_приватному_ключу_ed25519>` |
| **SSH-ключ (PuTTY/WinSCP)**| `<путь_к_приватному_ключу.ppk>` |

### Команда подключения:
```bash
ssh -i "path/to/private_key" root@<IP_СЕРВЕРА>
```

---

## 3. Настройка переменных окружения (`.env`)

Перед запуском проекта в корне `/home/agent/fitness_studio` должен быть создан файл `.env`:
```bash
cp .env.example .env
nano .env
```

### Описание ключевых параметров:

| Переменная | Назначение | Пример / Значение |
| :--- | :--- | :--- |
| `TG_BOT_TOKEN` | Токен Telegram-бота от @BotFather | `123456789:ABC...` |
| `ADMIN_CHAT_ID` | Telegram ID администратора студии для алертов | `482910482` |
| `WEBHOOK_HOST` | Базовый HTTPS URL для входящих вебхуков | `https://fit-nch.ru` |
| `DATABASE_URL` | Путь подключения SQLAlchemy к SQLite | `sqlite+aiosqlite:////database/planner.db` |
| `PLANNER_SECRET_KEY` | Секретный ключ подписи сессионных JWT | 64 hex символа (`openssl rand -hex 32`) |
| `PLANNER_ADMIN_LOGIN` | Логин стартового администратора | `admin` |
| `PLANNER_ADMIN_PASSWORD` | Пароль стартового администратора | Стойкий пароль |
| `VAPID_PUBLIC_KEY` | Публичный ключ Web Push (VAPID) | `BExamplePublic...` |
| `VAPID_PRIVATE_KEY` | Приватный ключ Web Push (VAPID) | `ExamplePrivate...` |
| `RATE_LIMIT_IP_LIMIT` | Защита от ботов: макс. попыток записи с 1 IP | `5` |
| `RATE_LIMIT_PHONE_LIMIT` | Защита от ботов: макс. попыток записи с 1 номера | `3` |

---

## 4. Пошаговое развертывание с нуля

### Шаг 4.1. Подготовка сервера и установка Docker
```bash
# Обновление пакетов
apt update && apt upgrade -y
apt install -y curl git nginx ufw

# Установка Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker agent
```

### Шаг 4.2. Клонирование репозитория
```bash
su - agent
git clone https://github.com/kazhem4ik/fitness_studio.git
cd fitness_studio
```

### Шаг 4.3. Настройка .env и каталогов данных
```bash
# Создание рабочей директории БД
mkdir -p database

# Создание конфигурации окружения
cp .env.example .env
nano .env  # Укажите реальные токены и секреты
```

### Шаг 4.4. Сборка и запуск контейнеров
```bash
docker compose up -d --build
```
Проверка статуса:
```bash
docker compose ps
```
Должны быть запущены 3 контейнера:
* `fitness_studio-planner_service-1`
* `fitness_studio-bot_service-1`
* `fitness_studio-nginx-1`

### Шаг 4.5. Создание администратора планировщика
```bash
docker compose exec planner_service python -m planner_service.scripts.create_admin
```

### Шаг 4.6. Настройка хостового Nginx
Файл конфигурации расположен в `deploy/nginx/fit-nch.ru.conf`:
```bash
# Копирование конфига на хост
cp deploy/nginx/fit-nch.ru.conf /etc/nginx/sites-available/fit-nch.ru.conf
ln -s /etc/nginx/sites-available/fit-nch.ru.conf /etc/nginx/sites-enabled/

# Проверка и перезагрузка
nginx -t
systemctl reload nginx
```

### Шаг 4.7. Настройка регулярных бэкапов БД
```bash
# Установка systemd-таймера
cp deploy/systemd/fitness-studio-backup.* /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now fitness-studio-backup.timer

# Проверка расписания
systemctl list-timers | grep fitness
```

---

## 5. Регламент обновления (CI/CD Workflow)

В проекте принят строгий регламент разработки и доставки:
1. **Любые правки делаются локально** на рабочей станции разработчика.
2. Локально проверяются изменения, формируется коммит и отправляется в GitHub:
   ```bash
   git add .
   git commit -m "feat/fix: описание изменений"
   git push origin main
   ```
3. **На сервере выполняется накат релиза**:
   ```bash
   ssh -i "path/to/key" root@<IP_СЕРВЕРА>
   su - agent -c "cd /home/agent/fitness_studio && git pull origin main"
   ```
4. **Перезапуск нужного сервиса**:
   * Если менялся только бэкенд планировщика:
     ```bash
     docker restart fitness_studio-planner_service-1
     ```
   * Если менялся бот:
     ```bash
     docker restart fitness_studio-bot_service-1
     ```
   * Если менялись `Dockerfile` или зависимости:
     ```bash
     su - agent -c "cd /home/agent/fitness_studio && docker compose up -d --build"
     ```

---

## 6. Мониторинг, логирование и отладка

### Просмотр логов:
```bash
# Все логи проекта в реальном времени
docker compose logs -f --tail 50

# Логи только планировщика (FastAPI)
docker logs -f --tail 100 fitness_studio-planner_service-1

# Логи Telegram-бота
docker logs -f --tail 100 fitness_studio-bot_service-1

# Логи Nginx контейнера
docker logs -f --tail 50 fitness_studio-nginx-1
```

### Проверка работоспособности (Healthcheck):
```bash
# Проверка ответа лендинга
curl -I http://127.0.0.1:8080/

# Проверка формы бронирования
curl -I http://127.0.0.1:8080/book

# Проверка веб-клиента планировщика
curl -I http://127.0.0.1:8080/clients
```

### Ручной запуск бэкапа:
```bash
systemctl start fitness-studio-backup.service
journalctl -u fitness-studio-backup.service -n 20 --no-pager
```
Архивы бэкапов сохраняются в каталоге: `/home/agent/backups/fitness_studio/`.
