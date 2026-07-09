import os
import re
import sqlite3
from urllib.parse import urlparse

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

# Default SQLite database path
DEFAULT_SQLITE_PATH = "outputs/applications.db"

class Row(dict):
    """
    Custom Row class mapping database results to behave like sqlite3.Row,
    supporting both key-based lookup (e.g. row['id']) and index-based lookup (e.g. row[0]).
    """
    def __init__(self, mapping, seq=None):
        if seq is not None:
            self.seq = list(seq)
        else:
            self.seq = list(mapping.values())
        super().__init__(mapping)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.seq[key]
        return super().__getitem__(key)

    def __iter__(self):
        return iter(self.seq)



def get_db_config() -> dict:
    """
    Reads DATABASE_URL and determines if PostgreSQL should be used.
    Returns config dictionary.
    """
    url_str = os.environ.get("DATABASE_URL", "").strip()
    if url_str.startswith("postgres://") or url_str.startswith("postgresql://"):
        return {"type": "postgres", "url": url_str}
    
    # Check if a custom sqlite URL is supplied
    if url_str.startswith("sqlite://"):
        parsed = urlparse(url_str)
        path = parsed.path
        # Handle sqlite:///relative/path or sqlite:////absolute/path
        if path.startswith("/"):
            path = path[1:]
        return {"type": "sqlite", "path": path or DEFAULT_SQLITE_PATH}
        
    return {"type": "sqlite", "path": DEFAULT_SQLITE_PATH}


def convert_query(sql: str, is_postgres: bool) -> str:
    """
    Translates placeholders in SQL queries between SQLite and PostgreSQL parameter styles.
    Positional: '?' -> '%s'
    Named: ':name' -> '%(name)s'
    """
    if not is_postgres:
        return sql
    # Replace positional ? with %s
    sql = sql.replace('?', '%s')
    # Replace named params :name with %(name)s, avoiding double-colon :: casts
    sql = re.sub(r'(?<!:):([a-zA-Z_][a-zA-Z0-9_]*)', r'%(\1)s', sql)
    return sql


def _get_postgres_connection(url: str):
    if not psycopg2:
        raise ImportError("psycopg2 is not installed but a postgres DATABASE_URL was supplied.")
    return psycopg2.connect(url)


def _get_sqlite_connection(path: str):
    db_dir = os.path.dirname(path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def execute_query(sql: str, params=None, db_path: str = None) -> list[Row]:
    """
    Executes a SELECT query and returns list of Row objects.
    """
    config = get_db_config()
    is_postgres = (config["type"] == "postgres")
    
    # Translate target DB path for SQLite if overridden in parameters
    sqlite_path = db_path if (db_path and not is_postgres) else config.get("path")
    
    translated_sql = convert_query(sql, is_postgres)
    
    if is_postgres:
        with _get_postgres_connection(config["url"]) as conn:
            with conn.cursor() as cur:
                cur.execute(translated_sql, params)
                colnames = [desc[0] for desc in cur.description] if cur.description else []
                rows = cur.fetchall()
                return [Row(dict(zip(colnames, row)), row) for row in rows]
    else:
        with _get_sqlite_connection(sqlite_path) as conn:
            cursor = conn.execute(translated_sql, params or ())
            rows = cursor.fetchall()
            return [Row(dict(row), row) for row in rows]


def execute_write(sql: str, params=None, db_path: str = None) -> int:
    """
    Executes an INSERT, UPDATE, or DELETE query.
    Returns last inserted ID for INSERT, or number of affected rows for other writes.
    """
    config = get_db_config()
    is_postgres = (config["type"] == "postgres")
    
    sqlite_path = db_path if (db_path and not is_postgres) else config.get("path")
    
    # If postgres insert, automatically append RETURNING id to fetch insert ID
    is_insert = sql.strip().upper().startswith("INSERT INTO")
    has_returning = "RETURNING" in sql.upper()
    
    translated_sql = convert_query(sql, is_postgres)
    
    if is_postgres:
        if is_insert and not has_returning:
            # Strip trailing semicolon and whitespace, append RETURNING id
            translated_sql = translated_sql.rstrip('; \t\n') + " RETURNING id"
            
        with _get_postgres_connection(config["url"]) as conn:
            with conn.cursor() as cur:
                cur.execute(translated_sql, params)
                if is_insert:
                    if not has_returning:
                        val = cur.fetchone()[0]
                        conn.commit()
                        return val
                    else:
                        # If query already had RETURNING, try to fetch it
                        try:
                            val = cur.fetchone()[0]
                            conn.commit()
                            return val
                        except Exception:
                            pass
                conn.commit()
                return cur.rowcount
    else:
        with _get_sqlite_connection(sqlite_path) as conn:
            cursor = conn.execute(translated_sql, params or ())
            conn.commit()
            if is_insert:
                return cursor.lastrowid
            return cursor.rowcount


def init_db_schema(db_path: str = None):
    """
    Creates and ensures all tables and indexes exist.
    Supports both SQLite and PostgreSQL.
    """
    config = get_db_config()
    is_postgres = (config["type"] == "postgres")
    
    if is_postgres:
        with _get_postgres_connection(config["url"]) as conn:
            with conn.cursor() as cur:
                # 1. Users table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id                  SERIAL PRIMARY KEY,
                        email               VARCHAR(255) UNIQUE NOT NULL,
                        password_hash       VARCHAR(255) NOT NULL,
                        created_at          VARCHAR(50) NOT NULL
                    )
                """)
                
                # 2. User Profiles table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_profiles (
                        user_id             INTEGER,
                        profile_name        VARCHAR(100) NOT NULL DEFAULT 'Default',
                        name                VARCHAR(255) NOT NULL,
                        email               VARCHAR(255) NOT NULL,
                        phone               VARCHAR(50),
                        linkedin            VARCHAR(255),
                        github              VARCHAR(255),
                        portfolio           VARCHAR(255),
                        location            VARCHAR(255),
                        raw_profile_json    TEXT NOT NULL DEFAULT '{}',
                        updated_at          VARCHAR(50) NOT NULL,
                        PRIMARY KEY(user_id, profile_name),
                        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)
                
                # 3. Applications table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS applications (
                        id                  SERIAL PRIMARY KEY,
                        company_name        VARCHAR(255) NOT NULL,
                        job_title           VARCHAR(255) NOT NULL,
                        source_url          TEXT,
                        status              VARCHAR(50) NOT NULL DEFAULT 'DRAFT_GENERATED',
                        match_score         INTEGER NOT NULL DEFAULT 0,
                        ats_score           INTEGER NOT NULL DEFAULT 0,
                        resume_path         VARCHAR(500),
                        cover_letter_path   VARCHAR(500),
                        notes               TEXT,
                        job_analysis_json   TEXT NOT NULL DEFAULT '{}',
                        match_json          TEXT NOT NULL DEFAULT '{}',
                        ats_report_json     TEXT NOT NULL DEFAULT '{}',
                        created_at          VARCHAR(50) NOT NULL,
                        updated_at          VARCHAR(50) NOT NULL,
                        user_id             INTEGER NOT NULL DEFAULT 1
                    )
                """)
                
                # 4. Job Search Runs table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS job_search_runs (
                        id                  SERIAL PRIMARY KEY,
                        total_urls          INTEGER NOT NULL DEFAULT 0,
                        successful_jobs     INTEGER NOT NULL DEFAULT 0,
                        failed_jobs         INTEGER NOT NULL DEFAULT 0,
                        report_path         VARCHAR(500),
                        failures_json       TEXT NOT NULL DEFAULT '[]',
                        created_at          VARCHAR(50) NOT NULL,
                        user_id             INTEGER NOT NULL DEFAULT 1
                    )
                """)
                
                # 5. Ranked Jobs table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS ranked_jobs (
                        id                  SERIAL PRIMARY KEY,
                        search_run_id       INTEGER NOT NULL,
                        rank                INTEGER NOT NULL,
                        company_name        VARCHAR(255) NOT NULL,
                        job_title           VARCHAR(255) NOT NULL,
                        source_url          TEXT NOT NULL,
                        fit_score           INTEGER NOT NULL DEFAULT 0,
                        fit_verdict         VARCHAR(100),
                        extraction_quality  VARCHAR(100),
                        missing_skills_json TEXT NOT NULL DEFAULT '[]',
                        job_analysis_json   TEXT NOT NULL DEFAULT '{}',
                        match_json          TEXT NOT NULL DEFAULT '{}',
                        created_at          VARCHAR(50) NOT NULL,
                        FOREIGN KEY(search_run_id) REFERENCES job_search_runs(id) ON DELETE CASCADE
                    )
                """)
                
                # 6. Discovered Jobs table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS discovered_jobs (
                        id SERIAL PRIMARY KEY,
                        provider_job_id TEXT NOT NULL,
                        source TEXT NOT NULL,
                        company_name TEXT NOT NULL,
                        job_title TEXT NOT NULL,
                        location TEXT,
                        work_mode TEXT,
                        job_type TEXT,
                        experience_level TEXT,
                        posted_date TEXT NOT NULL,
                        job_description TEXT NOT NULL,
                        date_label TEXT NOT NULL DEFAULT 'Posted',
                        freshness_verified INTEGER NOT NULL DEFAULT 1,
                        source_url TEXT,
                        apply_url TEXT,
                        raw_json TEXT NOT NULL DEFAULT '{}',
                        first_seen_at TEXT NOT NULL,
                        last_seen_at TEXT NOT NULL,
                        user_id INTEGER NOT NULL DEFAULT 1
                    )
                """)
                
                cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_discovered_jobs_identity ON discovered_jobs (user_id, source, provider_job_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_discovered_jobs_seen ON discovered_jobs (last_seen_at)")
                
                conn.commit()
    else:
        # SQLite implementation: delegates to local paths
        sqlite_path = db_path or config.get("path")
        db_dir = os.path.dirname(sqlite_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
            
        with _get_sqlite_connection(sqlite_path) as conn:
            # Users
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    email               TEXT UNIQUE NOT NULL,
                    password_hash       TEXT NOT NULL,
                    created_at          TEXT NOT NULL
                )
            """)
            
            # User Profiles
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id             INTEGER,
                    profile_name        TEXT NOT NULL DEFAULT 'Default',
                    name                TEXT NOT NULL,
                    email               TEXT NOT NULL,
                    phone               TEXT,
                    linkedin            TEXT,
                    github              TEXT,
                    portfolio           TEXT,
                    location            TEXT,
                    raw_profile_json    TEXT NOT NULL DEFAULT '{}',
                    updated_at          TEXT NOT NULL,
                    PRIMARY KEY(user_id, profile_name),
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            
            # Legacy migration check for SQLite composite PK
            profiles_cols = {row[1] for row in conn.execute("PRAGMA table_info(user_profiles)").fetchall()}
            if "profile_name" not in profiles_cols and len(profiles_cols) > 0:
                conn.execute("ALTER TABLE user_profiles RENAME TO old_user_profiles")
                conn.execute("""
                    CREATE TABLE user_profiles (
                        user_id             INTEGER,
                        profile_name        TEXT NOT NULL DEFAULT 'Default',
                        name                TEXT NOT NULL,
                        email               TEXT NOT NULL,
                        phone               TEXT,
                        linkedin            TEXT,
                        github              TEXT,
                        portfolio           TEXT,
                        location            TEXT,
                        raw_profile_json    TEXT NOT NULL DEFAULT '{}',
                        updated_at          TEXT NOT NULL,
                        PRIMARY KEY(user_id, profile_name),
                        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)
                conn.execute("""
                    INSERT OR IGNORE INTO user_profiles (
                        user_id, profile_name, name, email, phone,
                        linkedin, github, portfolio, location,
                        raw_profile_json, updated_at
                    )
                    SELECT 
                        user_id, 'Default', name, email, phone,
                        linkedin, github, portfolio, location,
                        raw_profile_json, updated_at
                    FROM old_user_profiles
                """)
                conn.execute("DROP TABLE old_user_profiles")
                
            # Applications
            conn.execute("""
                CREATE TABLE IF NOT EXISTS applications (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_name        TEXT NOT NULL,
                    job_title           TEXT NOT NULL,
                    source_url          TEXT,
                    status              TEXT NOT NULL DEFAULT 'DRAFT_GENERATED',
                    match_score         INTEGER NOT NULL DEFAULT 0,
                    ats_score           INTEGER NOT NULL DEFAULT 0,
                    resume_path         TEXT,
                    cover_letter_path   TEXT,
                    notes               TEXT,
                    job_analysis_json   TEXT NOT NULL DEFAULT '{}',
                    match_json          TEXT NOT NULL DEFAULT '{}',
                    ats_report_json     TEXT NOT NULL DEFAULT '{}',
                    created_at          TEXT NOT NULL,
                    updated_at          TEXT NOT NULL,
                    user_id             INTEGER NOT NULL DEFAULT 1
                )
            """)
            
            # Safe migration — add columns if missing
            existing = {row[1] for row in conn.execute("PRAGMA table_info(applications)").fetchall()}
            migrations = {
                "source_url": "ALTER TABLE applications ADD COLUMN source_url TEXT",
                "notes":      "ALTER TABLE applications ADD COLUMN notes TEXT",
                "user_id":    "ALTER TABLE applications ADD COLUMN user_id INTEGER DEFAULT 1",
            }
            for col, sql in migrations.items():
                if col not in existing:
                    conn.execute(sql)
                    
            # Job Search Runs
            conn.execute("""
                CREATE TABLE IF NOT EXISTS job_search_runs (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    total_urls          INTEGER NOT NULL DEFAULT 0,
                    successful_jobs     INTEGER NOT NULL DEFAULT 0,
                    failed_jobs         INTEGER NOT NULL DEFAULT 0,
                    report_path         TEXT,
                    failures_json       TEXT NOT NULL DEFAULT '[]',
                    created_at          TEXT NOT NULL,
                    user_id             INTEGER NOT NULL DEFAULT 1
                )
            """)
            
            existing_runs = {row[1] for row in conn.execute("PRAGMA table_info(job_search_runs)").fetchall()}
            if "user_id" not in existing_runs:
                conn.execute("ALTER TABLE job_search_runs ADD COLUMN user_id INTEGER DEFAULT 1")
                
            # Ranked Jobs
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ranked_jobs (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    search_run_id       INTEGER NOT NULL,
                    rank                INTEGER NOT NULL,
                    company_name        TEXT NOT NULL,
                    job_title           TEXT NOT NULL,
                    source_url          TEXT NOT NULL,
                    fit_score           INTEGER NOT NULL DEFAULT 0,
                    fit_verdict         TEXT,
                    extraction_quality  TEXT,
                    missing_skills_json TEXT NOT NULL DEFAULT '[]',
                    job_analysis_json   TEXT NOT NULL DEFAULT '{}',
                    match_json          TEXT NOT NULL DEFAULT '{}',
                    created_at          TEXT NOT NULL,
                    FOREIGN KEY(search_run_id) REFERENCES job_search_runs(id) ON DELETE CASCADE
                )
            """)
            
            # Discovered Jobs (Normalized job store)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS discovered_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider_job_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    company_name TEXT NOT NULL,
                    job_title TEXT NOT NULL,
                    location TEXT,
                    work_mode TEXT,
                    job_type TEXT,
                    experience_level TEXT,
                    posted_date TEXT NOT NULL,
                    job_description TEXT NOT NULL,
                    date_label TEXT NOT NULL DEFAULT 'Posted',
                    freshness_verified INTEGER NOT NULL DEFAULT 1,
                    source_url TEXT,
                    apply_url TEXT,
                    raw_json TEXT NOT NULL DEFAULT '{}',
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    user_id INTEGER NOT NULL DEFAULT 1
                )
            """)
            
            existing_jobs = {row[1] for row in conn.execute("PRAGMA table_info(discovered_jobs)").fetchall()}
            if "user_id" not in existing_jobs:
                conn.execute("ALTER TABLE discovered_jobs ADD COLUMN user_id INTEGER DEFAULT 1")
                
            conn.execute("DROP INDEX IF EXISTS idx_discovered_jobs_identity")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_discovered_jobs_identity ON discovered_jobs (user_id, source, provider_job_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_discovered_jobs_seen ON discovered_jobs (last_seen_at)")
            
            conn.commit()
