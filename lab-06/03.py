from database import connect

# Запрос с CTE и оконными функциями.

# Пользователь вводит год. Выведи личный зачёт сезона: очки за места 1–10
# по схеме 25-18-15-12-10-8-6-4-2-1. Для каждого пилота покажи место (rank()),
# очки и отставание от лидера.
year = int(input("Введите сезон(год): "))
with connect() as db:
    resp = db.execute("""
        with season_points as (
        select driver_id, sum(points_for_place(finish_position)) as points
        from race_entry
        where extract(year from race_date) = %s and finish_position is not null
        group by driver_id
        ),
        stat as (
            select 
                driver_id,
                points,
                rank() over (order by points desc) as rank,
                max(points) over () - points as gap
            from season_points
        )
        select
            d.full_name,
            s.rank,
            s.points,
            s.gap
        from stat s
        join driver d using (driver_id)
        order by s.rank, d.full_name; 
    """, (year, ))
    print(resp.fetchall())