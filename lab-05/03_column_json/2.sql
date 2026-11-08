alter table car add column if not exists specs jsonb;
update car c
set specs = (
    select specs 
    from jsonb_to_recordset(pg_read_file('/workspace/data/car_specs.json')::jsonb) as d(car_id int, specs jsonb)
    where c.car_id = d.car_id
);

begin;
select car_id from car where specs is null;
insert into car (model, season_year, car_class, horsepower, weight_kg, team_id, specs) values (
    'asd',
    2000,
    'gt',
    100,
    500,
    10,
    '{
        "engine": {
            "layout": "V6",
            "cylinders": 6,
            "displacement_l": 2.4,
            "turbo": true,
            "hybrid": { "ers_kw": 60 }
        },
        "aero": {
            "downforce": "low",
            "drs": true
        },
        "tyres": ["soft"],
        "sponsors": [
            {"name": "A", "share": 0.1}, 
            {"name": "B", "share": 0.2}
        ],
        "top_speed_kmh": 327,
        "homologated": true
    }'::jsonb
);
rollback;