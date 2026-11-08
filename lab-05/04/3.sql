select 
    count(*) filter (where not specs ? 'aero') as not_aero,
    count(*) filter (where not specs -> 'aero' ? 'drs') as aero_not_drs,
    count(*) filter (where specs -> 'aero' ? 'drs') as aero_drs
from (
    select car_id, specs
    from car
);

select
    count(*) filter (where specs ?| array['aero', 'sponsors']) as aero_or_sponsors,
    count(*) filter (where specs ?& array['aero', 'sponsors']) as aero_and_sponsors
from (
    select car_id, specs
    from car
);


select car_id
from car
where specs @> '{"engine": {"layout": "V6", "turbo": true}}' and specs @? '$.sponsors[*] ? (@.name == "Pirelli")';

select car_id
from car
where specs @> '{"engine": {"hybrid": {}}}';
-- where specs @? '$.engine.hybrid';

select car_id
from car
where specs @? '$.sponsors[*].name ? (@ like_regex "^P")' and (specs ->> 'top_speed_kmh')::int > 300;

select car_id
from car
where specs @? '$.aero.drs';
