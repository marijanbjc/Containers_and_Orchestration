"""Заглушка ETL-задачи.

Выгружает заказы из БД-источника, преобразует их, загружает результат
в целевую БД и сохраняет слепок выгрузки в parquet на диск.

Запуск: python main.py <каталог_для_данных>
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, inspect

SEED_ORDERS = [
    {"order_id": 1, "customer": "alice", "status": "completed", "quantity": 2, "price": 150.0},
    {"order_id": 2, "customer": "bob", "status": "completed", "quantity": 1, "price": 990.0},
    {"order_id": 3, "customer": "alice", "status": "cancelled", "quantity": 5, "price": 40.0},
    {"order_id": 4, "customer": "carol", "status": "completed", "quantity": 3, "price": 75.5},
    {"order_id": 5, "customer": "bob", "status": "completed", "quantity": 4, "price": 20.0},
]


def seed_source(engine):
    """Наполняет источник тестовыми заказами, если таблицы ещё нет."""
    if not inspect(engine).has_table("orders"):
        pd.DataFrame(SEED_ORDERS).to_sql("orders", engine, index=False)


def extract(engine):
    return pd.read_sql("SELECT * FROM orders", engine)


def transform(orders):
    """Оставляет завершённые заказы и считает итоги по каждому клиенту."""
    completed = orders[orders["status"] == "completed"].copy()
    completed["total"] = completed["quantity"] * completed["price"]
    return completed.groupby("customer", as_index=False).agg(
        orders_count=("order_id", "count"),
        total_amount=("total", "sum"),
    )


def load(totals, engine):
    totals.to_sql("customer_totals", engine, if_exists="replace", index=False)


def save_snapshot(orders, data_dir):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = data_dir / f"orders_{stamp}.parquet"
    orders.to_parquet(path, index=False)
    return path


def main():
    data_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "./data").resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    # Пока обе БД - это sqlite-файлы в каталоге данных.
    # Адреса настоящих БД можно будет передать через переменные окружения.
    source = create_engine(os.getenv("SOURCE_DB_URL", f"sqlite:///{data_dir / 'source.db'}"))
    target = create_engine(os.getenv("TARGET_DB_URL", f"sqlite:///{data_dir / 'target.db'}"))

    seed_source(source)

    orders = extract(source)
    print(f"Выгружено заказов: {len(orders)}")

    totals = transform(orders)
    print(f"Итоги по клиентам:\n{totals.to_string(index=False)}")

    load(totals, target)
    print("Итоги загружены в целевую БД, таблица customer_totals")

    snapshot = save_snapshot(orders, data_dir)
    print(f"Слепок выгрузки сохранён: {snapshot}")


if __name__ == "__main__":
    main()
