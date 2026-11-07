create table if not exists json_import (
    id serial primary key,
    file_name text unique,
    data jsonb
);

insert into json_import(file_name, data) values (
    'teams_array.json',
    pg_read_file('/workspace/lab-05/teams_array.json')::jsonb
) on conflict (file_name) do nothing;


create table if not exists team_copy (like team including all);
insert into team_copy 
select * from jsonb_populate_recordset(null::team, (select data from json_import where file_name = 'teams_array.json'));

(select * from team except select * from team_copy)
union all
(select * from team_copy except select * from team);

drop table team_copy;

