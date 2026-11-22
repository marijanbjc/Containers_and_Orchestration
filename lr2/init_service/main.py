"""Одноразовая инициализация БД для ETL.

1. Создаёт целевую базу (TARGET_DB), если её ещё нет.
2. В базе-источнике (POSTGRES_DB) создаёт таблицу orders
   и наполняет её тестовыми заказами.

Скрипт идемпотентный: повторный запуск ничего не ломает и не дублирует данные.
"""

import os
import sys
import time

import psycopg
from psycopg import sql

SEED_ORDERS = [
    (1, "alice", "completed", 2, 150.0),
    (2, "bob", "completed", 1, 990.0),
    (3, "alice", "cancelled", 5, 40.0),
    (4, "carol", "completed", 3, 75.5),
    (5, "bob", "completed", 4, 20.0),
    (6, "dave", "pending", 1, 310.0),
    (7, "carol", "completed", 2, 12.0),
]

CREATE_ORDERS = """
    CREATE TABLE IF NOT EXISTS orders (
        order_id  INTEGER PRIMARY KEY,
        customer  TEXT             NOT NULL,
        status    TEXT             NOT NULL,
        quantity  INTEGER          NOT NULL,
        price     DOUBLE PRECISION NOT NULL
    )
"""

INSERT_ORDER = """
    INSERT INTO orders (order_id, customer, status, quantity, price)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (order_id) DO NOTHING
"""


def env(name):
    value = os.getenv(name)
    if not value:
        sys.exit(f"Не задана переменная окружения {name}")
    return value


def connect(dbname, retries=10, delay=2):
    """Подключается к БД, при неудаче повторяет попытки."""
    for attempt in range(1, retries + 1):
        try:
            return psycopg.connect(
                host=env("POSTGRES_HOST"),
                port=os.getenv("POSTGRES_PORT", "5432"),
                user=env("POSTGRES_USER"),
                password=env("POSTGRES_PASSWORD"),
                dbname=dbname,
                autocommit=True,
            )
        except psycopg.OperationalError as error:
            print(f"Попытка {attempt}/{retries}: БД недоступна ({error})")
            time.sleep(delay)
    sys.exit("Не удалось подключиться к БД")


def create_target_db(source_db, target_db):
    with connect(source_db) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (target_db,)
        ).fetchone()
        if exists:
            print(f"База {target_db} уже существует")
        else:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target_db)))
            print(f"База {target_db} создана")


def seed_orders(source_db):
    with connect(source_db) as conn:
        conn.execute(CREATE_ORDERS)
        with conn.cursor() as cur:
            cur.executemany(INSERT_ORDER, SEED_ORDERS)
        total = conn.execute("SELECT count(*) FROM orders").fetchone()[0]
        print(f"Таблица orders в базе {source_db} готова, заказов: {total}")


def main():
    source_db = env("POSTGRES_DB")
    target_db = env("TARGET_DB")

    create_target_db(source_db, target_db)
    seed_orders(source_db)
    print("Инициализация завершена")


if __name__ == "__main__":
    main()
