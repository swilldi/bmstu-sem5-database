from database import connect
import psycopg

# Вызов хранимой процедуры из ЛР3.

# Вызови pr_disqualify(p_driver_id, p_race_date). Покажи NOTICE, затем спроси
# «зафиксировать? y/n» и в зависимости от ответа сделай commit или rollback.
# Если процедура выбросила исключение, меню должно продолжить работу.

def on_notice(diag):
    print(f"[{diag.severity}] {diag.message_primary}")

from datetime import date
driver_id = int(input("Введите id пилота"))
race_date = date.fromisoformat(input("Введите дату (ГГГГ-ММ-ДД): "))
with connect() as db:
    db.add_notice_handler(on_notice)

    try:
        db.execute("call pr_disqualify(%s, %s)", (driver_id, race_date,))
    except psycopg.Error as e:
        db.rollback()
        print("Ошибка: ", e.diag.message_primary)   
    else:
        if input("Зафиксировать? (y/n): ").strip().lower() == "y":
            db.commit()
        else:
            db.rollback()


