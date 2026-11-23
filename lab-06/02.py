from database import connect

# Запрос с несколькими JOIN.

# Пользователь вводит часть имени пилота. Выведи все его гонки: дата, трасса,
# машина, команда, стартовое и финишное место, статус. Сортировка по дате.

# name = input("Введите части имени пилота: ")
name = "Ma"
with connect() as db:
    resp = db.execute("""
        select d.full_name, tm.name, re.race_date, tr.name, c.model, re.grid_position, re.finish_position, re.status
        from race_entry re
        join driver d using (driver_id)
        join car c using (car_id)
        join contract using (driver_id, team_id)
        join team tm using (team_id)
        join track tr using (track_id)
        where d.full_name ilike %s
        order by re.race_date desc;
    """, (f"%{name}%", ))
    res = resp.fetchall()
        
    print(res[0:10])
