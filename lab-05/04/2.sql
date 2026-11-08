-- select model, specs -> 'engine' -> 'layout' as layout, specs #> '{engine, turbo}' as have_turbo -- остально в падлу писать всё тоже самое
-- from car; 



select layout, avg(top_speed_kmh)::numeric(6, 2) as avg_speed_kmh, count(model) as car_count
from (
    select model, specs #>> '{engine, layout}' as layout, (specs ->> 'top_speed_kmh')::int as top_speed_kmh
    from car
)
group by layout
order by avg_speed_kmh desc;


select model, sponsors_count
from (
    select model, jsonb_array_length(specs -> 'sponsors')  as sponsors_count
    from car
)
where  sponsors_count > 3;
-- where jsonb_array_length(sponsors) > 3

