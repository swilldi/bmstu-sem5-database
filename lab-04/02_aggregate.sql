-- самая длинная серия подиумов пилота подряд
drop type if exists podium_streak cascade;
create type podium_streak as (
    len int,
    max_len int
);

create or replace function best_podium_streak_state(state podium_streak, finish_position int)
returns podium_streak
language plpython3u
as $$
    if finish_position is not None and finish_position <= 3:
        state["len"] += 1
    else:
        state["max_len"] = max(state["max_len"], state["len"])
        state["len"] = 0

    return state
$$;

create or replace function best_podium_streak_finish_state(state podium_streak)
returns int
language plpython3u
as $$
    return max(state["max_len"], state["len"])
$$;

create or replace aggregate best_podium_streak(int) (
    sfunc     = best_podium_streak_state,
    stype     = podium_streak,
    finalfunc = best_podium_streak_finish_state,
    initcond = '(0, 0)'
);
