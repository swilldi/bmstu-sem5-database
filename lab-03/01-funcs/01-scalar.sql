create or replace function fn_avg_speed(p_driver_id int, p_race_date date) 
returns numeric
language sql
stable
as $$
    select round(t.length_km / extract(epoch from re.best_lap) * 3600, 2)
    from race_entry re 
    join track t using (track_id)
    where re.race_date = p_race_date and re.driver_id = p_driver_id
$$;

begin;
select fn_avg_speed(20, '1950-05-13');
rollback;
