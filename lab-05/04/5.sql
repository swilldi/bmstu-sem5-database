select re.race_date, re.driver_id,
       ps.n               as n_stop,
       ps.stop ->> 'lap'  as lap,
       ps.stop ->> 'tyre' as tyre,
       ps.stop ->> 'duration_s' as duration
from race_entry re,
     jsonb_array_elements(re.pit_stops) with ordinality as ps(stop, n);


select race_year, round(avg(duration_s), 2)
from (
    select extract(year from race_date) as race_year, (ps ->> 'duration_s')::numeric(4, 1) as duration_s
    from race_entry re, jsonb_array_elements(re.pit_stops) as ps
)
group by race_year
order by race_year;


--

select model, s.*
from car c, jsonb_to_recordset(c.specs -> 'sponsors') as s(name text, share numeric(3, 2));

select s.name, count(model) as cnt, max(s.share)
from car c, jsonb_to_recordset(c.specs -> 'sponsors') as s(name text, share numeric(3, 2))
group by s.name
order by cnt desc, s.name
limit 10;

select tyre, count(model)
from (
    select model, tyre
    from car c, jsonb_array_elements(c.specs -> 'tyres') as tyre
)
group by tyre;

select model, kv.key, kv.value
from car c, jsonb_each(c.specs -> 'engine') as kv
where c.car_id = 304;