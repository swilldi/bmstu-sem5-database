create or replace function fn_driver_season(p_driver_id int, p_year int)
returns table (track_name text, car_model text, grid_position smallint, finish_position smallint, status text, race_date date)
language sql
stable
as $$
    select t.name as track_name, c.model as car_model, re.grid_position, re.finish_position, re.status, re.race_date
    from race_entry re
    join track t using (track_id) 
    join car c using (car_id)
    where p_driver_id = driver_id and extract(year from race_date) = p_year
    order by re.race_date
$$;


select * from fn_driver_season(657, 2000);
