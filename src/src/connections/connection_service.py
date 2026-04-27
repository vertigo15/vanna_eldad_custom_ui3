"""Lookup of available data-source connections, sourced from `public.settings_services`.

Schema-modeler is responsible for CRUD on `settings_services`; Jeen Insights is a
read-only consumer. Each row carries the connection details inside a
`connection_config` JSONB column. We treat the row's `name` as the
`source_key` — the same value that appears in
`metadata_tables.source` / `metadata_columns.source` / `knowledge_pairs.source` /
`metadata_business_terms.source` / `metadata_relationships.source`.

This module also caches one `PostgresSqlRunner` per `source_key` so we don't
reopen pools per request.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import asyncpg

from src.tools.sql_tool import PostgresSqlRunner

logger = logging.getLogger(__name__)


class ConnectionNotFound(Exception):
    """Raised when a requested `source_key` is missing or inactive."""


class UnsupportedConnectionType(Exception):
    """Raised when `service_type` is not yet supported by Jeen Insights."""


@dataclass
class Connection:
    """A row from `public.settings_services` (without secrets)."""

    id: int
    source_key: str  # = settings_services.name; matches metadata_*.source
    display_name: str
    description: Optional[str]
    service_type: str  # e.g. 'Postgres', 'Mysql', 'Snowflake'
    database_type: str  # normalized lower-case alias of service_type for the prompt
    connection_host: Optional[str]
    connection_port: Optional[int]
    connection_database: Optional[str]
    db_schema: Optional[str]
    enable_ssl: bool
    is_active: bool

    def to_public_dict(self) -> dict:
        """Return a dict safe to send to the UI (no secrets)."""
        return {
            "id": self.id,
            "source_key": self.source_key,
            "display_name": self.display_name,
            "description": self.description,
            "service_type": self.service_type,
            "database_type": self.database_type,
            "connection_host": self.connection_host,
            "connection_port": self.connection_port,
            "connection_database": self.connection_database,
            "db_schema": self.db_schema,
            "enable_ssl": self.enable_ssl,
            "is_active": self.is_active,
        }


# ----------------------------------------------------------------------
# Service
# ----------------------------------------------------------------------
class ConnectionService:
    """Reads `settings_services` and lazily builds per-connection SQL runners."""

    def __init__(self, metadata_pool: asyncpg.Pool):
        self.pool = metadata_pool
        self._runners: Dict[str, PostgresSqlRunner] = {}
        self._runner_locks: Dict[str, asyncio.Lock] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def list_connections(self) -> List[Connection]:
        """List active database connections from `settings_services`."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, name, description, service_type, connection_config, is_active
                FROM public.settings_services
                WHERE category = 'database' AND is_active = TRUE
                ORDER BY name
                """
            )
        return [self._row_to_connection(r) for r in rows]

    async def get_connection(self, source_key: str) -> Connection:
        """Fetch one active connection by `name`. Raises `ConnectionNotFound`."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, name, description, service_type, connection_config, is_active
                FROM public.settings_services
                WHERE category = 'database' AND name = $1
                """,
                source_key,
            )
        if row is None:
            raise ConnectionNotFound(
                f"No connection found for source_key={source_key!r} (category=database)"
            )
        return self._row_to_connection(row)

    async def get_runner(self, source_key: str) -> PostgresSqlRunner:
        """Return a lazily-initialized `PostgresSqlRunner` for `source_key`."""
        if source_key in self._runners:
            return self._runners[source_key]

        # Per-source lock so concurrent first-touches don't double-build the runner.
        lock = self._runner_locks.setdefault(source_key, asyncio.Lock())
        async with lock:
            if source_key in self._runners:
                return self._runners[source_key]
            row = await self._fetch_full_row(source_key)
            runner = await self._build_runner(row)
            self._runners[source_key] = runner
            return runner

    async def close(self) -> None:
        """Close all cached runners."""
        for runner in self._runners.values():
            try:
                await runner.close()
            except Exception:  # noqa: BLE001
                logger.exception("Error closing data-source runner")
        self._runners.clear()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    async def _fetch_full_row(self, source_key: str) -> dict:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, name, description, service_type, connection_config, is_active
                FROM public.settings_services
                WHERE category = 'database' AND name = $1
                """,
                source_key,
            )
        if row is None:
            raise ConnectionNotFound(
                f"No connection found for source_key={source_key!r} (category=database)"
            )
        return dict(row)

    def _row_to_connection(self, row) -> Connection:
        cfg = _decode_config(row["connection_config"])
        host = _coerce_str(cfg.get("host"))
        port = _coerce_int(cfg.get("port"))
        # Some service types use a combined "hostPort" string.
        if (host is None or port is None) and cfg.get("hostPort"):
            host_port_str = str(cfg["hostPort"])
            if ":" in host_port_str:
                h, p = host_port_str.rsplit(":", 1)
                host = host or h
                try:
                    port = port or int(p)
                except ValueError:
                    pass
            else:
                host = host or host_port_str
        database = _coerce_str(cfg.get("database"))
        db_schema = _coerce_str(cfg.get("databaseSchema") or cfg.get("schema"))
        enable_ssl = _coerce_bool(cfg.get("ssl"), default=True)
        service_type = row["service_type"] or ""
        return Connection(
            id=row["id"],
            source_key=row["name"],
            display_name=row["name"],
            description=row["description"],
            service_type=service_type,
            database_type=service_type.lower(),
            connection_host=host,
            connection_port=port,
            connection_database=database,
            db_schema=db_schema,
            enable_ssl=enable_ssl,
            is_active=row["is_active"],
        )

    async def _build_runner(self, row: dict) -> PostgresSqlRunner:
        """Build a `PostgresSqlRunner` from a `settings_services` row."""
        cfg = _decode_config(row["connection_config"])
        service_type = (row.get("service_type") or "").strip().lower()
        if service_type not in ("postgres", "postgresql"):
            raise UnsupportedConnectionType(
                f"service_type={row.get('service_type')!r} not supported yet "
                "(Jeen Insights initial release supports PostgreSQL only)."
            )

        host = _coerce_str(cfg.get("host"))
        port = _coerce_int(cfg.get("port")) or 5432
        if (host is None) and cfg.get("hostPort"):
            host_port_str = str(cfg["hostPort"])
            if ":" in host_port_str:
                h, p = host_port_str.rsplit(":", 1)
                host = h
                try:
                    port = int(p)
                except ValueError:
                    pass
            else:
                host = host_port_str
        username = _coerce_str(cfg.get("username")) or ""
        password = _coerce_str(cfg.get("password")) or ""
        database = _coerce_str(cfg.get("database")) or ""
        enable_ssl = _coerce_bool(cfg.get("ssl"), default=True)

        if not host:
            raise UnsupportedConnectionType(
                "connection_config is missing 'host' (or 'hostPort')."
            )
        if not database:
            raise UnsupportedConnectionType(
                "connection_config is missing 'database'."
            )

        ssl_suffix = "?sslmode=require" if enable_ssl else ""
        connection_string = (
            f"postgresql://{username}:{password}@{host}:{port}/{database}{ssl_suffix}"
        )
        runner = PostgresSqlRunner(connection_string=connection_string)
        await runner.initialize()
        logger.info(
            "🔌 Built data-source runner for %s (%s@%s:%s/%s, ssl=%s)",
            row["name"],
            username,
            host,
            port,
            database,
            enable_ssl,
        )
        return runner


# ----------------------------------------------------------------------
# Module-level helpers
# ----------------------------------------------------------------------
def _decode_config(value: Any) -> Dict[str, Any]:
    """Convert the JSONB connection_config payload to a Python dict."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        try:
            value = bytes(value).decode("utf-8")
        except Exception:  # noqa: BLE001
            return {}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
    return {}


def _coerce_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    return str(value)


def _coerce_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "1", "yes", "on", "t"):
            return True
        if v in ("false", "0", "no", "off", "f", ""):
            return False
    return default
