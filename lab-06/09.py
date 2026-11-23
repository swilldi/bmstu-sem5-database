from database import connect

# Создание таблицы по тематике БД.

# Создай таблицу penalty (штрафы в гонке): составной внешний ключ на
# race_entry (driver_id, race_date), штраф в секундах с CHECK на диапазон,
# причина из фиксированного списка. Используй IF NOT EXISTS, чтобы повторный
# запуск не падал.

with connect() as db:
    db.execute("""
        create table if not exists penalty (
            penalty_id integer generated always as identity primary key,
            driver_id integer not null,
            race_date date not null,
            penalty_seconds integer not null
                check (penalty_seconds between 1 and 300),
            kind text not null
                check (kind in (
                    'speeding',
                    'track_limits',
                    'collision',
                    'false_start',
                    'unsafe_release'
                )),
            constraint fk_penalty_race_entry
                foreign key (driver_id, race_date)
                references race_entry (driver_id, race_date)
        );
    """)
    


