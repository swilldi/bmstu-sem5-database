-- проверка контракта пилота с командой машины при записи заезда

create or replace function race_entry_contract_check()
returns trigger
language plpython3u
as $$
new = TD["new"]
if TD["event"] == "UPDATE":
    old = TD["old"]
    if all(old[k] == new[k] for k in ("driver_id", "car_id", "race_date")):
        return None

if "car_team" not in SD:
    SD["car_team"] = plpy.prepare("select team_id from car where car_id = $1", ["int"])
    SD["contract_teams"] = plpy.prepare("""
        select team_id from contract
        where driver_id = $1 and start_date <= $2
          and (end_date is null or end_date >= $2)
    """, ["int", "date"])

rows = plpy.execute(SD["car_team"], [new["car_id"]])
if not rows:
    return None   # машины нет — пусть ругается FOREIGN KEY
car_team = rows[0]["team_id"]

teams = [r["team_id"] for r in plpy.execute(SD["contract_teams"], [new["driver_id"], new["race_date"]])]
if car_team in teams:
    return None

who = f'driver {new["driver_id"]} on {new["race_date"]}'
car = f'car {new["car_id"]} belongs to team {car_team}'
if teams:
    plpy.error(f'{who} is contracted to team {", ".join(map(str, teams))}, but {car}')
plpy.error(f'{who} has no contract, but {car}')
$$;

create or replace trigger trg_race_entry_contract
before insert or update on race_entry
for each row execute function race_entry_contract_check();
