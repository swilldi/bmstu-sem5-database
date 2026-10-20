-- очки за гонку
create or replace function race_points(status text, finish_position int, best_lap interval, race_best_lap interval)
returns int
language plpython3u
as $$
if status not in ("finished", "dnf", "dns", "dsq"):
    plpy.error("Неизвестный статус")

if status != "finished":
    return 0

if finish_position is None or not (1 <= finish_position <= 70):
    plpy.error("Некоректное значение позици финиша")

points_per_position = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1, 0]
fp = finish_position - 1
return points_per_position[min(fp, 10)] + (fp < 10 and best_lap == race_best_lap)
$$;

-- Тесты

-- 1. Очки на отдельных значениях
select race_points('finished', 1,  '1:20', '1:20') as p1_fl,    -- 26
       race_points('finished', 1,  '1:21', '1:20') as p1,       -- 25
       race_points('finished', 10, '1:20', '1:20') as p10_fl,   -- 2
       race_points('finished', 11, '1:20', '1:20') as p11_fl,   -- 0, очко за круг только в топ-10
       race_points('finished', 40, '1:25', '1:20') as p40,      -- 0
       race_points('dnf', null, '1:20', '1:20')    as dnf,      -- 0
       race_points('dns', null, null, '1:20')      as dns;      -- 0

-- 2. Лучший круг гонки считается по участникам гонки: топ-10 пилотов по очкам
with e as (
    select driver_id,
           race_points(status, finish_position, best_lap,
                       min(best_lap) over (partition by track_id, race_date)) as points
    from race_entry
)
select driver_id, sum(points) as points
from e
group by driver_id
order by points desc
limit 10;

-- 3. Ошибки
select race_points('crashed', 1, null, null);        -- неизвестный статус
select race_points('finished', null, null, null);    -- finished без позиции
select race_points('finished', 71, null, null);      -- позиция вне 1..70
