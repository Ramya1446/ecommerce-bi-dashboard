"""SQLite persistence and the named SQL query library."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .generate import Dataset

ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = ROOT / "sql"
QUERY_DIR = SQL_DIR / "queries"
DEFAULT_DB = ROOT / "data" / "ecommerce.db"


def build_database(ds: Dataset, db_path: Path = DEFAULT_DB) -> Path:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    with sqlite3.connect(db_path) as con:
        con.executescript((SQL_DIR / "schema.sql").read_text())
        for name, df in ds.tables().items():
            out = df.copy()
            for col in out.columns:
                if pd.api.types.is_datetime64_any_dtype(out[col]):
                    out[col] = out[col].dt.strftime("%Y-%m-%d %H:%M:%S")
            out.to_sql(name, con, if_exists="append", index=False)
        con.execute("ANALYZE")
    return db_path


def connect(db_path: Path = DEFAULT_DB) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(
            f"{db_path} not found - run `python scripts/build_data.py` first."
        )
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, check_same_thread=False)


def read_sql(sql: str, db_path: Path = DEFAULT_DB, params: tuple | dict = ()) -> pd.DataFrame:
    with connect(db_path) as con:
        return pd.read_sql_query(sql, con, params=params)


@dataclass(frozen=True)
class NamedQuery:
    slug: str
    title: str
    question: str
    sql: str


_HEADER = re.compile(r"^--\s*(title|question):\s*(.+)$", re.MULTILINE)


def load_queries(query_dir: Path = QUERY_DIR) -> list[NamedQuery]:
    """Load every .sql file; `-- title:` and `-- question:` header comments describe it."""
    out = []
    for path in sorted(query_dir.glob("*.sql")):
        text = path.read_text()
        meta = {k: v.strip() for k, v in _HEADER.findall(text)}
        out.append(NamedQuery(
            slug=path.stem,
            title=meta.get("title", path.stem),
            question=meta.get("question", ""),
            sql=text.strip(),
        ))
    return out


_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum|reindex)\b",
    re.IGNORECASE,
)


def run_readonly(sql: str, db_path: Path = DEFAULT_DB, limit: int = 5000) -> pd.DataFrame:
    """Run a user-supplied query. The connection is opened read-only; the keyword check
    is a second guard that gives a friendly error instead of a SQLite exception."""
    stripped = re.sub(r"--[^\n]*", "", sql).strip().rstrip(";")
    if ";" in stripped:
        raise ValueError("Only a single statement is allowed.")
    if not re.match(r"^\s*(select|with)\b", stripped, re.IGNORECASE):
        raise ValueError("Only SELECT / WITH queries are allowed.")
    if _FORBIDDEN.search(stripped):
        raise ValueError("Query contains a write/DDL keyword; this editor is read-only.")
    df = read_sql(stripped, db_path)
    return df.head(limit)
