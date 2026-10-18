-- на вход драйвер на выход список треков на 
-- которых он участовал, отсортировать по занимаемым местам

create or replace function fn_driver_tracks(p_driver_id int)
returns table (finish_position smallint, track_id int)
language sql
stable
as $$
    
    select re.finish_position, re.track_id
    from race_entry re
    where driver_id = p_driver_id
    order by finish_position, track_id

    -- select t.name as track_name, c.model as car_model, re.grid_position, re.finish_position, re.status, re.race_date
    -- from race_entry re
    -- join track t using (track_id) 
    -- join car c using (car_id)
    -- where p_driver_id = driver_id and extract(year from race_date) = p_year
    -- order by re.race_date
$$;

select * from fn_driver_tracks(209);
