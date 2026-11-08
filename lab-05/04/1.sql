select model, specs -> 'engine', specs #> '{engine, hybrid}'
from car;

select pit_stops -> 0 first_pit_stop, pit_stops -> -1 as last_pit_stop
from race_entry
where pit_stops != '[]';

select model,
    jsonb_path_query_array(specs, '$.sponsors[*] ? (@.share > 0.2).name') as sponsors
from car;

