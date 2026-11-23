from database import connect

# Вызов системной функции.

# Выведи «паспорт» базы: version(), current_database(), current_user,
# pg_size_pretty(pg_database_size(current_database())), а также размер каждой
# таблицы через pg_total_relation_size.

with connect() as db:
    resp = db.execute("select version(), current_database(), current_user, pg_size_pretty(pg_database_size(current_database()))")
    res = zip(["version", "db", "user", "size"], *resp)
    for k, v in res:
        print(k, v)
    
    tables = db.execute("""
    SELECT
        c.relname,
        pg_size_pretty(pg_total_relation_size(c.oid::regclass))
    FROM pg_class AS c
    JOIN pg_namespace AS n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relkind IN ('r', 'p')
    ORDER BY c.relname
""").fetchall()

for table_name, size in tables:
    print(f"{table_name}: {size}")
