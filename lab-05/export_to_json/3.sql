\t on
\a

drop function if exists race_result;
create or replace function race_result(p_track_id int, p_date date)
returns jsonb
language sql
as $$
    select jsonb_agg(
        jsonb_build_object(
            'position', finish_position,
            'driver_id', driver_id,
            'status', status,
            'best_lap_s', extract(epoch from best_lap)
        ) order by finish_position nulls last, driver_id
    )
    from race_entry 
    where track_id = p_track_id and race_date = p_date
$$;

select jsonb_pretty(race_result(17, '1950-05-13'));

select jsonb_pretty(jsonb_agg(
    jsonb_build_object(
        'track', jsonb_build_object(
            'name', t.name,
            'country', t.country
        ),
        'date', re.race_date,
        'results', race_result(re.track_id, re.race_date)
    )
))
from race_entry re
join track t using (track_id)
