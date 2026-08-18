# Резервное копирование баз данных

Скрипт `scripts/backup_databases.py` создаёт согласованные снимки `planner.db` и
`studio.db` через SQLite Backup API, проверяет `PRAGMA integrity_check`, упаковывает
обе базы и манифест с SHA-256 в один ZIP и загружает его на Яндекс Диск через
`rclone`.

Политика хранения:

- Яндекс Диск: `Fitness Studio/Backups/YYYY/MM/`, без автоматического удаления;
- VPS: последние 7 архивов;
- расписание: ежедневно в 03:00 по часовому поясу `Europe/Moscow`.

Локальная проверка без загрузки:

```bash
python3 scripts/backup_databases.py --skip-upload
```

Настройки окружения:

```text
FITNESS_BACKUP_DATABASE_DIR=/home/agent/fitness_studio/database
FITNESS_BACKUP_LOCAL_DIR=/home/agent/backups/fitness_studio
FITNESS_BACKUP_RCLONE_REMOTE=yandex:Fitness Studio/Backups
FITNESS_BACKUP_KEEP_LOCAL=7
```

Конфигурация `rclone` и установка systemd-таймера выполняются на VPS только после
публикации кода через GitHub. Файл rclone с токеном должен оставаться вне
репозитория: `/home/agent/.config/rclone/rclone.conf`.

Восстановление выполняется сначала в отдельную временную папку. Перед заменой
рабочих файлов необходимо остановить сервисы, проверить обе восстановленные базы
командой `PRAGMA integrity_check`, и только затем заменить базы и запустить
контейнеры снова.
