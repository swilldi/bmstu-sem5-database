-- -- select d1.driver_id, d1.full_name, d2.driver_id, d2.full_name
-- -- from driver d1
-- -- join driver d2 using (full_name)
-- -- where d1.driver_id != d2.driver_id;


-- -- select full_name
-- -- from race_entry re
-- -- join driver d using (driver_id)
-- -- where re.finish_position = 1
-- -- group by d.driver_id, d.full_name
-- -- order by count(*) desc
-- -- limit 1;


-- -- # Пользователь вводит часть имени пилота. Выведи все его гонки: дата, трасса,
-- -- # машина, команда, стартовое и финишное место, статус. Сортировка по дате.
-- -- select re.race_date, tr.name, c.model, re.grid_position, re.finish_position, re.status
-- -- from race_entry re
-- -- join driver d using (driver_id)
-- -- join car c using (car_id)
-- -- join contract using (driver_id, team_id)
-- -- join team tm using (team_id)
-- -- join track tr using (track_id)
-- -- order by re.race_date desc;


-- -- # Пользователь вводит год. Выведи личный зачёт сезона: очки за места 1–10
-- -- # по схеме 25-18-15-12-10-8-6-4-2-1. Для каждого пилота покажи место (rank()),
-- -- # очки и отставание от лидера.

-- drop function if exists points_for_place;
-- create or replace function points_for_place(place integer)
-- returns integer
-- language sql
-- as $$ 
--     select case place
--         WHEN 1 THEN 25
--         WHEN 2 THEN 18
--         WHEN 3 THEN 15
--         WHEN 4 THEN 12
--         WHEN 5 THEN 10
--         WHEN 6 THEN 8
--         WHEN 7 THEN 6
--         WHEN 8 THEN 4
--         WHEN 9 THEN 2
--         WHEN 10 THEN 1
--         ELSE 0
--     end;
-- $$;

-- with season_points as (
--     select driver_id, sum(points_for_place(finish_position)) as points
--     from race_entry
--     where extract(year from race_date) = 2026 and finish_position is not null
--     group by driver_id
-- ),
-- stat as (
--     select 
--         driver_id,
--         points,
--         rank() over (order by points desc) as rank,
--         max(points) over () - points as gap
--     from season_points
-- )
-- select
--     d.full_name,
--     s.rank,
--     s.points,
--     s.gap
-- from stat s
-- join driver d using (driver_id)
-- order by s.rank, d.full_name; 


-- SELECT oid
-- FROM pg_namespace
-- where nspname = 'public';

-- # Создай таблицу penalty (штрафы в гонке): составной внешний ключ на
-- # race_entry (driver_id, race_date), штраф в секундах с CHECK на диапазон,
-- # причина из фиксированного списка. Используй IF NOT EXISTS, чтобы повторный
-- # запуск не падал.

create table if not exists penalty (
    penalty_id integer generated always as identity primary key,
    driver_id integer not null,
    race_date date not null,
    penalty_seconds integer not null
        check (penalty_seconds between 1 and 300),
    kind text not null
        check (kind in (
            'speeding',
            'track_limits',
            'collision',
            'false_start',
            'unsafe_release'
        )),
    constraint fk_penalty_race_entry
        foreign key (driver_id, race_date)
        references race_entry (driver_id, race_date)
);