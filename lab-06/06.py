from database import connect

# Вызов многооператорной или табличной функции из ЛР3.

# Вызови fn_driver_career(p_driver_id) и выведи результат таблицей.
with connect() as db:
    data = dict()
    for row in  db.execute("select driver_id, fn_driver_career(driver_id) from driver").fetchall():
        data.setdefault(row[0], {})[row[1][0]] = row[1][1]

    for driver_id, metrics in data.items():
        print(f"Пилот {driver_id}:")
        for metric, value in metrics.items():
            print(f"\t{metric}: {value}")
        print()

# Вызови fn_driver_season(p_driver_id, p_year) сразу с
# WHERE status = 'finished' ORDER BY finish_position.

with connect() as db:
    result = db.execute(
        """
        SELECT *
        FROM fn_driver_season(4702, 2026)
        WHERE status = 'finished'
        ORDER BY finish_position
        """
    ).fetchall()

    for track_name, car_model, grid_position, finish_position, status, race_date in result:
        print(f"Гонка {race_date}:")
        print(f"\tТрасса: {track_name}")
        print(f"\tМашина: {car_model}")
        print(f"\tСтартовая позиция: {grid_position}")
        print(f"\tФинишная позиция: {finish_position}")
        print(f"\tСтатус: {status}")
        print()