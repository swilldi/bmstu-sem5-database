from database import connect

# Вызов скалярной функции из ЛР3.
# (Перед запуском загрузи функции из ../lab-03, сейчас их в базе нет.)

# Вызови fn_avg_speed(p_driver_id, p_race_date) для пилота и даты, которые ввёл
# пользователь, и выведи среднюю скорость в км/ч. Обработай случай, когда такого заезда нет.

import datetime
# driver_id = int(input("Введите id пилота: "))
# race_date = datetime.date.fromisoformat(
#     input("Введите дату в формате (ГГГГ-ММ-ДД): ").strip()
# )
driver_id = 4682
race_date = race_date = datetime.date.fromisoformat("2026-10-11")
with connect() as db:
    speed = db.execute("""
        select fn_avg_speed(%s, %s);
    """, (driver_id, race_date, )).fetchone()[0]

    if speed is None:
        print("У указанного пилота в этот день не было гонки")
    else:
        print(f"Средняя скорость в гонке: {speed}")
