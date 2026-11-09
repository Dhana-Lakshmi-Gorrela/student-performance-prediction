"""Tiny database layer: MySQL (PyMySQL) by default, SQLite for quick starts."""
import os
import re
import sqlite3
from flask import g
from config import Config

IS_SQLITE = Config.DB_TYPE == "sqlite"

if IS_SQLITE:
    IntegrityError = sqlite3.IntegrityError
else:
    import pymysql
    import pymysql.cursors
    IntegrityError = pymysql.err.IntegrityError


def connect(with_database=True):
    if IS_SQLITE:
        conn = sqlite3.connect(Config.SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    return pymysql.connect(
        host=Config.DB_HOST, user=Config.DB_USER, password=Config.DB_PASSWORD,
        database=Config.DB_NAME if with_database else None,
        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
    )


def get_db():
    if "db" not in g:
        g.db = connect()
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def _sql(sql):
    return sql.replace("%s", "?") if IS_SQLITE else sql


def query(sql, args=(), one=False):
    cur = get_db().cursor()
    cur.execute(_sql(sql), args)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql, args=()):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(_sql(sql), args)
        conn.commit()
        return cur.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def init_db():
    """Create the database and all tables from schema.sql."""
    path = os.path.join(os.path.dirname(__file__), "schema.sql")
    script = open(path, encoding="utf-8").read()
    statements = [s.strip() for s in script.split(";") if s.strip()]
    conn = connect(with_database=False) if not IS_SQLITE else connect()
    cur = conn.cursor()
    for stmt in statements:
        if IS_SQLITE:
            if stmt.upper().startswith(("CREATE DATABASE", "USE ")):
                continue
            stmt = stmt.replace("INT AUTO_INCREMENT PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
            stmt = re.sub(r"\)\s*ENGINE=InnoDB", ")", stmt)
        cur.execute(stmt)
    conn.commit()
    conn.close()
