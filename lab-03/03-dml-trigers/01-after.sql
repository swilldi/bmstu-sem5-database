-- Журнал изменений race_entry
drop trigger if exists tr_race_entry_audit on race_entry;
drop function if exists fn_race_entry_audit();
drop table if exists race_entry_audit;

create table race_entry_audit (
    id serial primary key,
    op text not null,
    changed_at timestamp not null default now(),
    changed_by text not null default current_user,
    old_row jsonb,
    new_row jsonb
);

create or replace function fn_race_entry_audit()
returns trigger
language plpgsql
as $$
begin
    insert into race_entry_audit(op, old_row, new_row)
    values (tg_op, to_jsonb(old), to_jsonb(new));

    return null;
end;
$$;

create trigger tr_race_entry_audit
after insert or update or delete on race_entry
for each row
execute function fn_race_entry_audit();


begin;
insert into race_entry(driver_id, car_id, track_id, status, grid_position, laps_completed, race_date)
values (626, 4333, 27, 'dns', 23, 0, '2000-03-12');
select * from race_entry_audit;
rollback;

begin;
update race_entry set laps_completed = 60 where driver_id = 52 and race_date = '1950-05-13';
select * from race_entry_audit;
rollback;

begin;
delete from race_entry where driver_id = 52 and race_date = '1950-05-13';
select * from race_entry_audit;
rollback;

begin;
call pr_disqualify(677, '2000-03-12');
select op, count(*) from race_entry_audit group by op;
rollback;

begin;
update race_entry set grid_position = 100 where driver_id = 52 and race_date = '1950-05-13';
rollback;
select count(*) from race_entry_audit;
