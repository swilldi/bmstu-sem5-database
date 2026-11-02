-- -- Извлечение фрагмента
-- select car_id, specs -> 'engine' as engine, specs -> 'sponsors' as sponsors
-- from car
-- order by car_id;

-- --
-- select car_id, specs #>> '{engine, hybrid, ers_kw}' as ers_kw
-- from car
-- where specs -> 'engine' ? 'hybrid';

-- --
-- select car_id
-- from car
-- where (specs #>> '{aero, drs}')::boolean and specs -> 'sponsors' = '[]';


-- -- 
-- -- {"car_id": 6215, "specs": {"engine": {"layout": "V8", "cylinders": 8, "displacement_l": 4.0, "turbo": true}, "tyres": ["dry", "wet"], "sponsors": [], "top_speed_kmh": 242, "homologated": true}},
-- update car 
-- set specs = jsonb_set(specs, '{engine,turbo}', 'false')
-- where car_id = 6215;
-- update car 
-- set specs = specs - 'homologated'
-- where car_id = 6215;
-- update car 
-- set specs = jsonb_set(specs, coalesce(specs -> 'sponsors', '[]') || '[{"name": "asd", "share": 0.4}]')
-- where car_id = 6215;

-- select c.car_id, sp ->> 'name' as sponsor, (sp ->> 'share')::numeric as share
-- from car c
-- cross join lateral jsonb_array_elements(c.specs -> 'sponsors') as sp;

select c.car_id, e.key
from car c, jsonb_each(c.specs -> 'engine') as e;
