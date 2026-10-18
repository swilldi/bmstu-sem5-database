-- очки за гонку
create or replace function race_points(status text, finish_position int, best_lap interval, race_best_lap interval)
returns int
language plpython3u
as $$
if status not in ("finished", "dnf", "dns", "dsq"):
    plpy.error("Неизвестный статус")

if status != "finished":
    return 0

if finish_position is None or not (1 <= finish_position <= 70):
    plpy.error("Некоректное значение позици финиша")

points_per_position = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1, 0]
fp = finish_position - 1
return points_per_position[min(fp, 10)] + (fp < 10 and best_lap == race_best_lap)
$$;
