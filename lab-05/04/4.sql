rollback;
begin;

--
update car
set specs = jsonb_set(specs, '{top_speed_kmh}', to_jsonb((specs ->> 'top_speed_kmh')::int + 5))
where season_year >= 2020 and (specs ->> 'homologated')::boolean;

--
update car
set specs = jsonb_set(specs, '{aero,drs}', 'true')
where specs @> '{"engine": {"turbo": true}, "aero": {}}';


-- слоооожна
select car_id, specs -> 'sponsors' from car where car_id in (6825, 6673);

update car
set specs = jsonb_set(specs, '{sponsors}', '[{"name": "ASD", "share": 0.2}]' || (specs -> 'sponsors'))
where car_id = 6825;
   
update car
set specs = jsonb_insert(specs, '{sponsors, -1}', '{"name": "ZXC", "share": 0.2}', true)
where car_id = 6673;

select car_id, specs -> 'sponsors' from car where car_id in (6825, 6673);
   
   
rollback;