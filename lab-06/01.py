from database import connect
import datetime

# Имя пилота с наибольшим числом побед.
with connect() as db:
    resp = db.execute("""
                      select full_name
                      from race_entry re
                               join driver d using (driver_id)
                      where re.finish_position = 1
                      group by d.driver_id, d.full_name
                      order by count(*) desc
                      limit 1;
                      """)
    (driver,) = resp.fetchone()
    print(driver)

# Cамый быстрый круг в истории базы в виде `м:сс.ммм` и трассу, где он поставлен.
with connect() as db:
    resp = db.execute("""
                      select t.name, t.country, re.best_lap
                      from race_entry re
                               join track t using (track_id)
                      order by best_lap
                      limit 1
                      """)
    (track_name, track_country, best_lap_time,) = resp.fetchone()
    print(track_name, track_country, best_lap_time.total_seconds())
