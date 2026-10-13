-- Результаты гонок с названиями вместо id, вставка и удаление через instead of
drop view if exists v_race_result;
drop function if exists fn_v_race_result();

create view v_race_result as
select re.driver_id, d.full_name as driver_name, re.race_date,
       t.name as track_name, t.country as track_country, c.model as car_model, tm.name as team_name,
       re.grid_position, re.finish_position, re.status, re.laps_completed, re.best_lap, re.total_time
from race_entry re
join driver d using (driver_id)
join track t using (track_id)
join car c using (car_id)
join team tm using (team_id);

create or replace function fn_v_race_result()
returns trigger
language plpgsql
as $$
declare
    v_track_id int;
    v_car_id int;
begin
    if tg_op = 'INSERT' then
        select t.track_id into v_track_id
        from track t
        where t.name = new.track_name and t.country = new.track_country;

        if v_track_id is null then
            raise exception 'Трасса не найдена';
        end if;

        select c.car_id into v_car_id
        from car c
        where c.model = new.car_model and c.season_year = extract(year from new.race_date);

        if v_car_id is null then
            raise exception 'Машина не найдена';
        end if;

        insert into race_entry(driver_id, car_id, track_id, status, grid_position, finish_position, best_lap, total_time, race_date, laps_completed)
        values (new.driver_id, v_car_id, v_track_id, new.status, new.grid_position, new.finish_position, new.best_lap, new.total_time, new.race_date, coalesce(new.laps_completed, 0));

        return new;
    end if;

    delete from race_entry re
    where re.driver_id = old.driver_id and re.race_date = old.race_date;

    return old;
end;
$$;

create trigger tr_v_race_result
instead of insert or delete on v_race_result
for each row
execute function fn_v_race_result();


begin;
insert into v_race_result(driver_id, race_date, track_name, track_country, car_model, grid_position, status)
values (626, '2000-03-12', 'Albert Park Grand Prix Circuit', 'Australia', 'Dallara F300 #33', 23, 'dns');
select * from v_race_result where driver_id = 626 and race_date = '2000-03-12';
rollback;

begin;
delete from v_race_result where driver_id = 52 and race_date = '1950-05-13';
select * from race_entry where driver_id = 52 and race_date = '1950-05-13';
rollback;

begin;
insert into v_race_result(driver_id, race_date, track_name, track_country, car_model, grid_position, status)
values (626, '2000-03-12', 'abc', 'Australia', 'Dallara F300 #33', 23, 'dns');
rollback;

begin;
drop trigger tr_v_race_result on v_race_result;
insert into v_race_result(driver_id, race_date, track_name, track_country, car_model, grid_position, status)
values (626, '2000-03-12', 'Albert Park Grand Prix Circuit', 'Australia', 'Dallara F300 #33', 23, 'dns');
rollback;
