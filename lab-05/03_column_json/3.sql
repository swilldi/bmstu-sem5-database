
alter table race_entry add column if not exists pit_stops jsonb;

update race_entry re
set pit_stops = ps.pit_stops
from jsonb_to_recordset(pg_read_file('/workspace/data/pit_stops.json')::jsonb) as ps(driver_id int, race_date date, pit_stops jsonb)
where re.driver_id = ps.driver_id and re.race_date = ps.race_date;

