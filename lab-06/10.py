from datetime import date
from pathlib import Path

import psycopg

from database import connect

# Вставка одной строки в penalty через INSERT.
driver_id = int(input("ID пилота: "))
race_date = date.fromisoformat(input("Дата гонки (ГГГГ-ММ-ДД): "))
penalty_seconds = int(input("Штраф в секундах (1–300): "))
kind = input(
    "Причина (speeding, track_limits, collision, false_start, unsafe_release): "
).strip()

try:
    with connect() as db:
        db.execute(
            "INSERT INTO penalty (driver_id, race_date, penalty_seconds, kind) "
            "VALUES (%s, %s, %s, %s)",
            (driver_id, race_date, penalty_seconds, kind)
        )
    print("Штраф добавлен.")
except psycopg.IntegrityError as error:
    print(f"Не удалось добавить штраф: {error.diag.message_primary}")

# Загрузка penalty из CSV через COPY.
csv_path = Path(input("Путь к CSV-файлу: ").strip()).expanduser()
try:
    with csv_path.open(encoding="utf-8", newline="") as csv_file:
        with connect() as db:
            with db.cursor().copy(
                """
                COPY penalty
                    (driver_id, race_date, penalty_seconds, kind)
                FROM STDIN WITH (FORMAT CSV, HEADER TRUE)
                """
            ) as copy:
                copy.write(csv_file.read())
    print("CSV загружен.")
except OSError as error:
    print(f"Не удалось прочитать CSV-файл: {error}")
except psycopg.IntegrityError as error:
    print(f"Ошибка в CSV, вся загрузка отменена: {error}")
