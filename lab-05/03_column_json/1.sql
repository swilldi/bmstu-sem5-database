\set value '{"b": 1, "a": 2, "b": 3}'
select :'value'::json as json, :'value'::jsonb;