"""連接 Access 資料庫，以及讀取 /sql 資料夾裡的查詢檔。

查詢檔的參數寫成 [@參數名稱]，例如 [@event_id]：
- 貼進 Access 的 SQL 檢視執行時，Access 會跳出輸入框讓你填值，可以直接測試；
- 後端讀檔時會把 [@event_id] 換成 ODBC 的 ?，再依名稱把值帶進去。
"""
import os
import pathlib
import re
from contextlib import contextmanager

import pyodbc

ROOT = pathlib.Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "sql"
DB_PATH = pathlib.Path(os.environ.get("EVENT_DB_PATH", ROOT / "db" / "test_events.accdb"))

_PARAM = re.compile(r"\[@(\w+)\]")


class DatabaseNotFound(RuntimeError):
    pass


@contextmanager
def connect():
    """每個請求開一條新連線，用完就關。Access 檔在 Access 裡開著時也能連（共用模式）。"""
    if not DB_PATH.exists():
        raise DatabaseNotFound(f"找不到資料庫檔案：{DB_PATH}")
    conn = pyodbc.connect(
        "DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + str(DB_PATH),
        autocommit=False,
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def load_sql(name: str) -> tuple[str, list[str]]:
    """讀 sql/<name>.sql，回傳（換成 ? 的 SQL, 參數名稱順序）。每次重讀，改了 .sql 不用重開後端。"""
    text = (SQL_DIR / f"{name}.sql").read_text(encoding="utf-8")
    # 去掉 -- 開頭的註解行與結尾分號（Access 的 SQL 檢視會自動加分號，ODBC 不需要）
    lines = [line for line in text.splitlines() if not line.strip().startswith("--")]
    sql = "\n".join(lines).strip().rstrip(";")
    names = _PARAM.findall(sql)
    return _PARAM.sub("?", sql), names


def _rows_to_dicts(cursor) -> list[dict]:
    columns = [c[0] for c in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def query(conn, sql: str, params=()) -> list[dict]:
    cursor = conn.cursor()
    cursor.execute(sql, params)
    return _rows_to_dicts(cursor)


def run(conn, sql_name: str, /, **params) -> list[dict]:
    """執行 sql/<sql_name>.sql；SELECT 回傳 dict 清單，其他指令回傳空清單。"""
    sql, names = load_sql(sql_name)
    cursor = conn.cursor()
    cursor.execute(sql, [params[n] for n in names])
    return _rows_to_dicts(cursor) if cursor.description else []


def execute(conn, sql_name: str, /, **params) -> int:
    """執行 sql/<sql_name>.sql 的 INSERT／UPDATE／DELETE，回傳影響的筆數。"""
    sql, names = load_sql(sql_name)
    cursor = conn.cursor()
    cursor.execute(sql, [params[n] for n in names])
    return cursor.rowcount


def last_id(conn) -> int:
    """剛剛 INSERT 的自動編號（Access 用 @@IDENTITY，同一條連線內有效）。"""
    return query(conn, "SELECT @@IDENTITY AS NewID")[0]["NewID"]
