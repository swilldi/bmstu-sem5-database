-- Задание 3. Табличная функция team_seasons
--
-- История команды по сезонам. Сезон — это год race_date, а заезды команды —
-- заезды на её машинах (car.team_id).
--
-- - races — число заездов, wins — побед, podiums — подиумов.
-- - dnf_rate — доля dnf + dsq от стартовавших (dns не считаются),
--   с округлением до 3 знаков. Если стартов не было, NULL.
-- - top_driver — пилот команды с максимумом подиумов в этом сезоне,
--   при равенстве берётся меньший driver_id. Если подиумов не было, NULL.
-- - Если команды нет, ошибка "team <id> not found". Если p_team_id IS NULL,
--   пустой результат.
-- - Строки возвращаются через yield, отсортированные по season.
--
-- Проверка:
-- 1. Сумма races по всем сезонам равна count(*) заездов на машинах команды.
-- 2. Ошибка на несуществующем team_id.
-- 3. p_team_id IS NULL даёт пустой результат.

create or replace function team_seasons(p_team_id int)
returns table(season int, races int, wins int, podiums int, dnf_rate numeric, top_driver text)
language plpython3u
as $$
    from decimal import Decimal, ROUND_HALF_UP

    if p_team_id is None:
        return

    if "team_seasons" not in SD:
        SD["team_seasons"] = {
            "team_exists": plpy.prepare("""
                select 1 from team where team_id = $1
            """, ["int"]),

            "seasons": plpy.prepare("""
                select distinct extract(year from race_date)::int as season
                from race_entry r
                join car c using (car_id)
                where team_id = $1
                order by season
            """, ["int"]),

            "season_data": plpy.prepare("""
                select
                    count(*) as races,
                    count(*) filter (where finish_position = 1) as wins,
                    count(*) filter (where finish_position <= 3) as podiums,
                    count(*) filter (where status = any (array['dnf', 'dsq'])) as dnf_dsq,
                    count(*) filter (where status <> 'dns') as started
                from race_entry r
                join car c using (car_id)
                where extract(year from race_date) = $1 and team_id = $2
            """, ["int", "int"]),

            "top_driver": plpy.prepare("""
                select d.full_name, count(*) as podiums
                from race_entry r
                join driver d using (driver_id)
                join car c using (car_id)
                where extract(year from race_date) = $1 and team_id = $2 and finish_position <= 3
                group by d.driver_id, d.full_name
                order by podiums desc, d.driver_id
                limit 1
            """, ["int", "int"]),
        }
    plans = SD["team_seasons"]

    if not plpy.execute(plans["team_exists"], [p_team_id]):
        plpy.error(f"team {p_team_id} not found")

    for s in plpy.execute(plans["seasons"], [p_team_id]):
        season = s["season"]
        sd = plpy.execute(plans["season_data"], [season, p_team_id])[0]
        top = plpy.execute(plans["top_driver"], [season, p_team_id])

        # round() в Python округляет половинки к чётному (0.3125 -> 0.312),
        # а round() в PostgreSQL — от нуля (0.313), поэтому Decimal с ROUND_HALF_UP
        dnf_rate = None
        if sd["started"] > 0:
            dnf_rate = (Decimal(sd["dnf_dsq"]) / Decimal(sd["started"])).quantize(
                Decimal("0.001"), rounding=ROUND_HALF_UP)

        yield {
            "season": season,
            "races": sd["races"],
            "wins": sd["wins"],
            "podiums": sd["podiums"],
            "dnf_rate": dnf_rate,
            "top_driver": top[0]["full_name"] if top else None,
        }
$$;
