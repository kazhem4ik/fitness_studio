# 🏋️‍♀️ Fitness Studio Monorepo

Комплексная экосистема автоматизации для фитнес-студии: промо-лендинг, интеллектуальный Telegram-бот для клиентов и тренеров, а также веб-планировщик (CRM/PWA) для управления записями, финансами и расписанием.

🌐 **Production:** [fit-nch.ru](https://fit-nch.ru)  
📖 **Руководство по деплою:** [DEPLOYMENT.md](DEPLOYMENT.md)

---

## 📌 Архитектура экосистемы

```
                                  [ Клиенты в Интернет ]
                                             │
                                   HTTPS (Cloudflare / SSL)
                                             │
                                   ▼ [ Host Nginx ]
                                      Port 80/443
                                             │
                                      127.0.0.1:8080
                                             │
                    ┌────────────────────────┴────────────────────────┐
                    │          Docker Nginx Router (Port 80)          │
                    └────────────────────────┬────────────────────────┘
                                             │
              ┌──────────────────────────────┼──────────────────────────────┐
              ▼                              ▼                              ▼
    [ landing_page ]                [ bot_service ]               [ planner_service ]
    Статика: /                     FastAPI + Polling             FastAPI + PWA + VAPID
    HTML/CSS/JS                    (Port 8000)                   (Port 8001)
                                             │                              │
                                             └──────────────┬───────────────┘
                                                            ▼
                                                 [ SQLite DB: planner.db ]
```

### Основные компоненты:
1. **[Landing Page](landing_page/)**: Высокопроизводительный промо-сайт студии с презентацией направлений и прямой интеграцией с записью.
2. **[Bot Service](bot_service/)**: Telegram-бот для онлайн-записи клиентов в доступные слоты, напоминаний, дневника питания и мобильной админки для тренера.
3. **[Planner Service](planner_service/)**: Полнофункциональное PWA-приложение для тренера: интерактивный календарь, клиенты, финансовая аналитика, Web Push уведомления.
4. **[Nginx Gateway](nginx/)**: Внутренний балансировщик и прокси для изолированной маршрутизации микросервисов.
5. **[Deploy & Backups](deploy/)**: Systemd-таймеры для автоматического создания ежедневных сжатых резервных копий БД с ротацией.

---

## 📂 Структура репозитория

```text
├── bot_service/               # Сервис Telegram-бота (FastAPI + python-telegram-bot)
├── planner_service/           # CRM и PWA планировщик (FastAPI + SQLAlchemy + Push)
├── landing_page/              # Промо-лендинг студии
├── nginx/                     # Конфигурация встроенного Nginx-контейнера
├── deploy/                    # Конфиги развертывания
│   ├── nginx/fit-nch.ru.conf  # Конфигурация внешнего хостового Nginx
│   └── systemd/               # Юниты systemd для автобэкапов (service + timer)
├── database/                  # Локальное хранилище SQLite (монтируется volume)
├── scripts/                   # Сервисные скрипты (бэкапы, миграции)
├── tests/                     # Автоматизированный тестовый контур (pytest)
├── documentation/             # Проектная документация и регламенты
├── .env.example               # Шаблон всех переменных окружения
├── docker-compose.yml         # Манифест оркестрации Docker
├── DEPLOYMENT.md              # Подробный DevOps Deployment Guide
└── README.md                  # Документация проекта
```

---

## 🚀 Быстрый старт (Локально / Docker)

### 1. Клонирование и настройка окружения
```bash
git clone https://github.com/kazhem4ik/fitness_studio.git
cd fitness_studio

cp .env.example .env
# Заполните реальные токены и секреты в .env
```

### 2. Запуск через Docker Compose
```bash
docker compose up -d --build
```

### 3. Создание первого администратора
```bash
docker compose exec planner_service python -m planner_service.scripts.create_admin
```

После старта будут доступны следующие эндпоинты:
* **Лендинг:** `http://localhost:8080/`
* **CRM / Планировщик:** `http://localhost:8080/clients`
* **Публичная запись:** `http://localhost:8080/book`

---

## 🧪 Тестирование

Запуск набора unit- и интеграционных тестов:
```bash
pytest tests/
```

---

## 🔒 Безопасность

* Любые чувствительные данные (`.env`, ключи SSH `*.pem`, `*.ppk`, дампы БД) строго изолированы в [.gitignore](.gitignore) и не отслеживаются в Git.
* Публичные эндпоинты защищены встроенным Rate Limiter по IP и номерам телефонов для противодействия ботам.
* Доступ к веб-планировщику защищен JWT-токенами с алгоритмом HS256 и безопасными HttpOnly cookies.
* Подробные инструкции по безопасности и развертыванию см. в [DEPLOYMENT.md](DEPLOYMENT.md).
