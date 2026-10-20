-- тип «результат заезда» с оператором сравнения >>

drop type if exists race_result cascade;

create type race_result as (
    status          text,
    finish_position int,
    laps            int,
    total_s         float8
);

-- Конструктор
-- Не STRICT: у нефинишировавших finish_position и total_time равны NULL.

create or replace function make_race_result(status text, finish_position int, laps int, total_time interval)
returns race_result
language plpython3u
immutable
as $$
if status not in ("finished", "dnf", "dsq", "dns"):
    plpy.error(f"неизвестный статус: {status}")
if laps is None or laps < 0:
    plpy.error(f"число кругов должно быть >= 0: {laps}")

finished = status == "finished"
if finished != (finish_position is not None):
    plpy.error("позиция финиша есть тогда и только тогда, когда статус finished")
if finished != (total_time is not None):
    plpy.error("время заезда есть тогда и только тогда, когда статус finished")
if status == "dns" and laps != 0:
    plpy.error(f"dns не может проехать круги: {laps}")

total_s = None
if total_time is not None:
    if "epoch" not in SD:
        SD["epoch"] = plpy.prepare("select extract(epoch from $1)::float8 as s", ["interval"])
    total_s = plpy.execute(SD["epoch"], [total_time])[0]["s"]
    if not 60 <= total_s <= 30 * 3600:
        plpy.error(f"время заезда вне диапазона 1 мин ... 30 ч: {total_time}")

return {"status": status, "finish_position": finish_position, "laps": laps, "total_s": total_s}
$$;

-- Методы

create or replace function rr_is_classified(r race_result)
returns boolean
language plpython3u
immutable strict
as $$
return r["status"] == "finished"
$$;

create or replace function rr_format(r race_result)
returns text
language plpython3u
immutable strict
as $$
s = r["status"]
if s == "finished":
    ms = round(r["total_s"] * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    sec, ms = divmod(ms, 1000)
    return f"P{r['finish_position']} · {r['laps']} laps · {h}:{m:02}:{sec:02}.{ms:03}"
if s == "dnf":
    return f"DNF (lap {r['laps']})"
return s.upper()
$$;

-- Насколько a позади b. Минус — a впереди.
create or replace function rr_gap(a race_result, b race_result)
returns text
language plpython3u
immutable strict
as $$
a_fin = a["status"] == "finished"
b_fin = b["status"] == "finished"
if not a_fin and not b_fin:
    return None

if a_fin and b_fin and a["laps"] == b["laps"]:
    return f"{a['total_s'] - b['total_s']:+.3f} s"

laps = b["laps"] - a["laps"]
return f"{laps:+} lap{'' if abs(laps) == 1 else 's'}"
$$;

-- Оператор

create or replace function rr_better(a race_result, b race_result)
returns boolean
language plpython3u
immutable strict
as $$
sa, sb = a["status"], b["status"]

# 1. finished лучше любого нефинишировавшего
if (sa == "finished") != (sb == "finished"):
    return sa == "finished"

# 2. оба finished — лучше меньшая позиция
if sa == "finished":
    return a["finish_position"] < b["finish_position"]

# 4. dns хуже всех
if (sa == "dns") != (sb == "dns"):
    return sb == "dns"

# 3. оба не финишировали — лучше больше кругов
if a["laps"] != b["laps"]:
    return a["laps"] > b["laps"]

# 4. при равных кругах dnf лучше dsq
return sa == "dnf" and sb == "dsq"
$$;

create or replace function rr_worse(a race_result, b race_result)
returns boolean
language sql
immutable strict
as $$
    select rr_better(b, a)
$$;

-- COMMUTATOR: a >> b равносильно b << a, поэтому планировщик может
-- переставлять аргументы.
create operator >> (
    leftarg    = race_result,
    rightarg   = race_result,
    function   = rr_better,
    commutator = <<
);

create operator << (
    leftarg    = race_result,
    rightarg   = race_result,
    function   = rr_worse,
    commutator = >>
);
