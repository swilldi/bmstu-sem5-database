-- Задание 4. Хранимая процедура transfer_driver
--
-- Переход пилота в другую команду с даты p_on. Текущий контракт пилота
-- (end_date IS NULL) закрывается датой p_on - 1, и открывается новый контракт
-- с start_date = p_on.
--
-- Проверки делаются в Python до изменений. Каждая выдаёт своё сообщение
-- через plpy.error с конкретными значениями:
-- 1. Пилот существует.
-- 2. Новая команда существует и is_active = true.
-- 3. p_on не в будущем и не раньше 1950-01-01, как в CHECK таблицы contract.
-- 4. У пилота ровно один открытый контракт: ни ноля, ни двух.
-- 5. Новая команда отличается от текущей.
-- 6. p_on - 1 >= start_date текущего контракта, иначе нарушится
--    chk_contract_end_date.
-- 7. У пилота нет заездов после p_on - 1 на машинах старой команды. Иначе эти
--    заезды окажутся вне контракта, а это то самое правило, которое охраняет
--    триггер из задания 5.
--
-- - Закрытие старого и открытие нового контракта выполняются атомарно
--   в plpy.subtransaction().
-- - В конце plpy.notice вида "driver 736: team 12 -> team 40 from 2025-03-01".
-- - Если любой аргумент NULL, процедура выдаёт ошибку, а не молча ничего
--   не делает.
--
-- Проверка (всё в begin ... rollback):
-- 1. Успешный переход. После него у пилота ровно один открытый контракт,
--    и он с новой командой.
-- 2. Минимум 4 разных ошибочных вызова из списка проверок, каждый со своим
--    сообщением.
-- 3. Ошибка на шаге «открыть новый» не оставляет закрытым старый контракт.
--    Сымитируй её, например, вставив заранее контракт с тем же
--    (driver_id, start_date).

create or replace procedure transfer_driver(p_driver_id int, p_new_team_id int, p_on date)
language plpython3u
as $$
    -- проверки проверочки

    close_contract_plan = plpy.prepare("""
        update contract
        set end_date = $1 - 1
        where driver_id = $2 and end_date is null
    """, ["date", "int"])

    plpy.execute(close_contract_plan, [p_on, p_driver_id])

    add_contract_plan = plpy.prepare("""
        insert into contract (driver_id, team_id, start_date, end_date)
        values ($1, $2, $3, null)
    """, ["int", "int", "date"])

    plpy.execute(add_contract_plan, [p_driver_id, p_new_team_id, p_on])
$$;
