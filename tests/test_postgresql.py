import pytest
import os
from unittest.mock import patch, MagicMock
from db_client import convert_query, Row, get_db_config, execute_query, execute_write

def test_convert_query_sqlite():
    # SQLite should leave parameters unchanged
    sql = "SELECT * FROM users WHERE email=? AND password_hash=?"
    assert convert_query(sql, is_postgres=False) == sql

    sql_named = "INSERT INTO user_profiles (user_id, name) VALUES (:user_id, :name)"
    assert convert_query(sql_named, is_postgres=False) == sql_named


def test_convert_query_postgres():
    # Postgres should convert positional ? to %s
    sql = "SELECT * FROM users WHERE email=? AND password_hash=?"
    assert convert_query(sql, is_postgres=True) == "SELECT * FROM users WHERE email=%s AND password_hash=%s"

    # Postgres should convert named params :name to %(name)s
    sql_named = "INSERT INTO user_profiles (user_id, name) VALUES (:user_id, :name)"
    assert convert_query(sql_named, is_postgres=True) == "INSERT INTO user_profiles (user_id, name) VALUES (%(user_id)s, %(name)s)"

    # Postgres should not convert double colon (cast) like ::text
    sql_cast = "SELECT name::text FROM user_profiles WHERE id = :id"
    assert convert_query(sql_cast, is_postgres=True) == "SELECT name::text FROM user_profiles WHERE id = %(id)s"


def test_row_class_behavior():
    mapping = {"id": 1, "email": "test@test.com", "name": "Alice"}
    row = Row(mapping)

    # 1. Key-based access
    assert row["id"] == 1
    assert row["email"] == "test@test.com"

    # 2. Index-based access
    assert row[0] == 1
    assert row[1] == "test@test.com"
    assert row[2] == "Alice"

    # 3. Iteration over values (matches sqlite3.Row)
    values = list(row)
    assert values == [1, "test@test.com", "Alice"]

    # 4. Zip compatibility
    zipped = dict(zip(["col_a", "col_b", "col_c"], row))
    assert zipped == {"col_a": 1, "col_b": "test@test.com", "col_c": "Alice"}


@patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/dbname"})
def test_get_db_config_postgres():
    config = get_db_config()
    assert config["type"] == "postgres"
    assert config["url"] == "postgresql://user:pass@localhost:5432/dbname"


@patch.dict(os.environ, {"DATABASE_URL": ""})
def test_get_db_config_sqlite_default():
    config = get_db_config()
    assert config["type"] == "sqlite"
    assert config["path"] == "outputs/applications.db"


@patch.dict(os.environ, {"DATABASE_URL": "sqlite:///custom_db.sqlite"})
def test_get_db_config_sqlite_custom():
    config = get_db_config()
    assert config["type"] == "sqlite"
    assert config["path"] == "custom_db.sqlite"
