# ЛР 2. Docker Compose

ETL-приложение из ЛР 1, развёрнутое через Docker Compose вместе с PostgreSQL.

Раз в `ETL_INTERVAL` секунд приложение забирает заказы из базы `shop`,
считает итоги по клиентам, записывает их в базу `dwh` и сохраняет
parquet-слепок выгрузки на диск.

## Схема

```
docker compose up
  │
  ├─ postgres       стартует → healthcheck → healthy
  │
  ├─ init_service   создаёт базу dwh, таблицу orders и тестовые заказы → exit 0
  │
  └─ core_service   цикл: shop.orders → итоги → dwh.customer_totals
                                              └→ parquet в томе etl_data
```

## Файлы

| Файл | Описание |
|---|---|
| `docker-compose.yml` | Описание сервисов, сети и томов |
| `.env` | Переменные окружения для всех сервисов |
| `Dockerfile` | Образ init-сервиса |
| `init_service/` | Код init-сервиса |
| `../lr1/` | Код и Dockerfile ETL-сервиса из ЛР 1 |

## Сервисы

| Сервис | Контейнер | Образ | Назначение |
|---|---|---|---|
| `postgres` | `shop-postgres` | `postgres:17` | БД: источник `shop` и хранилище `dwh` |
| `init_service` | `init-service` | `initial-service:v0` (собирается из `Dockerfile`) | Одноразовая инициализация БД |
| `core_service` | `core-service` | `etl-service:v0` (собирается из `../lr1/Dockerfile_good`) | ETL-задача по расписанию |

### `postgres`
- **volume** `postgres_data` хранит файлы БД, данные переживают пересоздание контейнера.
- **ports** `5432:5432` — к БД можно подключиться с хоста.
- **healthcheck** — `pg_isready` проверяет, что БД принимает подключения.

### `init_service`
- **depends_on** `postgres` с условием `service_healthy`: стартует только когда БД готова.
- Создаёт базу `dwh`, таблицу `orders` в базе `shop` и наполняет её тестовыми заказами.
- Скрипт идемпотентный: при повторном `up` ничего не дублирует.
- Отрабатывает и завершается с кодом 0.

### `core_service`
- **depends_on**: `postgres` (`service_healthy`) и `init_service` (`service_completed_successfully`). ETL стартует только после успешной инициализации.
- **entrypoint** заменяет одиночный запуск из Dockerfile на бесконечный цикл:
  `python main.py ./data`, затем `sleep $ETL_INTERVAL`.
  `$$` в compose-файле нужен, чтобы переменную подставил shell в контейнере, а не compose.
- **volume** `etl_data` хранит parquet-слепки выгрузок.

### Общее
- **network**: все сервисы в одной сети `db_network` и обращаются друг к другу по имени сервиса (`postgres`).
- **env**: все переменные вынесены в `.env`, compose-файл подключает его через `env_file`.

## Запуск

```bash
docker compose up -d --build
```

Проверка:

```bash
docker compose ps -a
docker compose logs init_service core_service
docker compose exec postgres psql -U admin -d dwh -c "SELECT * FROM customer_totals;"
docker compose exec core_service ls data
```

Остановка (с `-v` удаляются и тома с данными):

```bash
docker compose down
docker compose down -v
```

## Ответы на вопросы

### Можно ли ограничивать ресурсы (память, CPU) для сервисов в docker-compose.yml?

Да. Лимиты задаются в `deploy.resources`:

```yaml
services:
  core_service:
    deploy:
      resources:
        limits:          # жёсткий потолок
          cpus: "0.5"
          memory: 512M
        reservations:    # гарантированный минимум
          memory: 128M
```

Docker Compose v2 применяет эти лимиты и при обычном `docker compose up`.

### Как запустить только определённый сервис, не запуская остальные?

```bash
docker compose up <сервис>             # сервис + всё, от чего он зависит через depends_on
docker compose up --no-deps <сервис>   # только сам сервис, без зависимостей
docker compose run --rm <сервис>       # разовый запуск, контейнер удаляется после завершения
```
