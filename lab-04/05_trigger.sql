-- Задание 5. Триггер trg_race_entry_contract
--
-- BEFORE INSERT OR UPDATE на race_entry, FOR EACH ROW.
--
-- Правило: на дату race_date у пилота должен быть действующий контракт
-- с командой, которой принадлежит машина car_id. Действующий означает
-- start_date <= race_date и при этом end_date IS NULL OR end_date >= race_date.
--
-- Это правило нельзя выразить через CHECK, потому что оно затрагивает три
-- таблицы, а через FOREIGN KEY — потому что сравнивает диапазоны дат.
-- В текущих данных оно уже выполняется для всех 54 560 строк, так что триггер
-- ничего не сломает.
--
-- - Сообщение об ошибке называет пилота, машину, команду машины и дату.
--   Если у пилота на эту дату контракт с другой командой, назови и её:
--   "driver 736 on 2024-05-12 is contracted to team 40, but car 1234 belongs to team 12".
-- - При UPDATE проверка нужна, только если изменились driver_id, car_id или
--   race_date. Обновление status или времени не должно делать лишних запросов.
-- - Функция триггера возвращает None (строка без изменений) или "SKIP".
--   Подумай и напиши в отчёте, почему здесь не "MODIFY".
--
-- Проверка:
-- 1. Корректная вставка проходит. Подбери пилота, машину и дату по данным.
-- 2. Вставка с машиной чужой команды падает с понятным сообщением.
-- 3. update race_entry set status = status по одной строке проходит.
-- 4. UPDATE, меняющий car_id на машину чужой команды, падает.
-- 5. (*) Второй триггер на contract (BEFORE UPDATE OR DELETE) запрещает
--    укорачивать или удалять контракт, если от этого заезды пилота окажутся
--    вне контракта.

create or replace function race_entry_contract_check()
returns trigger
language plpython3u
as $$
    pass
$$;

create or replace trigger trg_race_entry_contract
before insert or update on race_entry
for each row execute function race_entry_contract_check();

-- (*) Триггер на contract

create or replace function contract_keep_entries_check()
returns trigger
language plpython3u
as $$
    pass
$$;

create or replace trigger trg_contract_keep_entries
before update or delete on contract
for each row execute function contract_keep_entries_check();
