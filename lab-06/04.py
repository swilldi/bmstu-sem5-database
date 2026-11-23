from database import connect

# Запрос к метаданным.

# Пользователь вводит имя таблицы. Выведи её столбцы (имя, тип, NULL/NOT NULL,
# значение по умолчанию)

table_name = input("Введите название таблицы: ")
with connect() as db:
    resp = db.execute(
        "select t.table_name from information_schema.tables t where t.table_schema = 'public'"
    )
    tables = list(map(lambda x: x[0], resp.fetchall()))
    if table_name in tables:
        resp = db.execute(
            """
            select 
                column_name, is_nullable, column_default
            from information_schema.columns 
            where table_name = %s
            """,
        (table_name,))
        
        for row in resp.fetchall():
            (name, nullable, default,) = row
            print(f"{name}: nullable {nullable}, default {default}")


# Список функций и процедур схемы public: имя, вид (функция или процедура),
# аргументы, возвращаемый тип.
with connect() as db:
    public_oid = db.execute("select oid from pg_namespace where nspname = 'public';").fetchone()[0]
    resp = db.execute("""
        select oid, proname, prokind
        from pg_proc
        where pronamespace = %s
    """, (public_oid,))
    for row in resp.fetchall():
        (oid, name, kind,) = row
        args = db.execute("select * from pg_get_function_arguments(%s)", (oid, )).fetchone()[0]
        result_type = db.execute("select * from pg_get_function_result(%s)", (oid, )).fetchone()[0]
        print(f"\
name: {name}\n\
kind: {kind}\n\
args: {args}\n\
result_type: {result_type}\n\
        ")

    

