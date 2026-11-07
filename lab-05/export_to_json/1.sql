\t on
\a

\o 'track_full.json'
select to_jsonb(t) from track t;

\o 'pilot_part.json'
select jsonb_build_object(
    'id', d.driver_id,
    'name', d.full_name,
    'born', d.birth_date,
    'country', d.country
)
from driver d;

\o 'track_arrray_part.json'
select jsonb_build_array(
    name, country, length_km
)
from track;

\o
