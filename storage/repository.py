"""SQLite 数据层的直接查询与 Persona 持久化 API。"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Iterable

from .db import DEFAULT_DB_PATH, db_session, init_db


JSON_COLUMNS = {
    "metadata_json",
    "raw_json",
    "persona_json",
    "final_summary_json",
    "response_json",
}


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _row_to_dict(row: Any) -> dict[str, Any]:
    result = dict(row)
    for key in JSON_COLUMNS:
        if key in result and isinstance(result[key], str):
            try:
                result[key] = json.loads(result[key])
            except json.JSONDecodeError:
                pass
    if "merged_record_ids_json" in result:
        raw = result.pop("merged_record_ids_json")
        try:
            result["merged_record_ids"] = json.loads(raw) if raw else []
        except json.JSONDecodeError:
            result["merged_record_ids"] = []
    if "include_in_dashboard" in result and result["include_in_dashboard"] is not None:
        result["include_in_dashboard"] = bool(result["include_in_dashboard"])
    return result


class Repository:
    """保持简单的查询 API；每个方法使用独立短连接。"""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = init_db(db_path)

    def list_events(self) -> list[dict[str, Any]]:
        with db_session(self.db_path) as connection:
            rows = connection.execute(
                "SELECT * FROM events ORDER BY imported_at DESC, event_id"
            ).fetchall()
        return [_row_to_dict(row) for row in rows]

    def get_event(self, event_id: str) -> dict[str, Any] | None:
        with db_session(self.db_path) as connection:
            row = connection.execute(
                "SELECT * FROM events WHERE event_id = ?", (event_id,)
            ).fetchone()
        return _row_to_dict(row) if row else None

    def get_comments(
        self,
        event_id: str,
        platform: str | None = None,
        sentiment: str | None = None,
    ) -> list[dict[str, Any]]:
        conditions = ["event_id = ?"]
        params: list[Any] = [event_id]
        if platform is not None:
            conditions.append("platform = ?")
            params.append(platform)
        if sentiment is not None:
            conditions.append("sentiment = ?")
            params.append(sentiment)
        sql = f"SELECT * FROM comments WHERE {' AND '.join(conditions)} ORDER BY id"
        with db_session(self.db_path) as connection:
            rows = connection.execute(sql, params).fetchall()
        return [_row_to_dict(row) for row in rows]

    def get_comments_by_category(
        self, event_id: str, category_id: str
    ) -> list[dict[str, Any]]:
        with db_session(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT c.*, cc.sentiment AS category_sentiment
                FROM comments AS c
                JOIN comment_categories AS cc
                  ON cc.event_id = c.event_id AND cc.record_id = c.record_id
                WHERE cc.event_id = ? AND cc.category_id = ?
                ORDER BY c.id
                """,
                (event_id, category_id),
            ).fetchall()
        return [_row_to_dict(row) for row in rows]

    def search_comments(
        self,
        query: str,
        event_id: str | None = None,
        exclude_event_id: str | None = None,
        platform: str | None = None,
        sentiment: str | None = None,
        category_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """搜索评论文本，并按需叠加事件、平台、情绪和类别过滤。"""

        terms = [term for term in query.split() if term]
        if not terms:
            raise ValueError("search query cannot be empty")
        if not 1 <= limit <= 500:
            raise ValueError("search limit must be between 1 and 500")

        filters: list[str] = []
        filter_params: list[Any] = []
        if event_id is not None:
            filters.append("c.event_id = ?")
            filter_params.append(event_id)
        if exclude_event_id is not None:
            filters.append("c.event_id <> ?")
            filter_params.append(exclude_event_id)
        if platform is not None:
            filters.append("c.platform = ?")
            filter_params.append(platform)
        if sentiment is not None:
            filters.append("c.sentiment = ?")
            filter_params.append(sentiment)
        if category_id is not None:
            filters.append(
                """
                EXISTS (
                    SELECT 1 FROM comment_categories AS cc
                    WHERE cc.event_id = c.event_id
                      AND cc.record_id = c.record_id
                      AND cc.category_id = ?
                )
                """
            )
            filter_params.append(category_id)

        use_fts = all(len(term) >= 3 for term in terms)
        if use_fts:
            quoted_terms = [f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms]
            search_condition = "comments_fts MATCH ?"
            search_params: list[Any] = [" AND ".join(quoted_terms)]
            from_clause = """
                comments_fts
                JOIN comments AS c ON c.id = comments_fts.rowid
                JOIN events AS e ON e.event_id = c.event_id
            """
            rank_expression = "bm25(comments_fts)"
            order_by = "search_rank ASC, c.support_count DESC, c.id"
            method = "fts5_trigram"
        else:
            like_conditions: list[str] = []
            search_params = []
            for term in terms:
                escaped = (
                    term.replace("\\", "\\\\")
                    .replace("%", "\\%")
                    .replace("_", "\\_")
                )
                like_conditions.append("c.text LIKE ? ESCAPE '\\'")
                search_params.append(f"%{escaped}%")
            search_condition = " AND ".join(like_conditions)
            from_clause = "comments AS c JOIN events AS e ON e.event_id = c.event_id"
            rank_expression = "NULL"
            order_by = "c.support_count DESC, c.id"
            method = "literal_substring"

        where = " AND ".join([search_condition, *filters])
        sql = f"""
            SELECT c.*, e.title AS event_title,
                   {rank_expression} AS search_rank,
                   ? AS search_method
            FROM {from_clause}
            WHERE {where}
            ORDER BY {order_by}
            LIMIT ?
        """
        params = [method, *search_params, *filter_params, limit]
        with db_session(self.db_path) as connection:
            rows = connection.execute(sql, params).fetchall()
        return [_row_to_dict(row) for row in rows]

    def get_categories_for_comments(
        self, keys: Iterable[tuple[str, str]]
    ) -> dict[tuple[str, str], list[dict[str, Any]]]:
        """按 (event_id, record_id) 返回动态类别；不假设跨事件共享类别 ID。"""

        key_list = list(dict.fromkeys(keys))
        result: dict[tuple[str, str], list[dict[str, Any]]] = {
            key: [] for key in key_list
        }
        if not key_list:
            return result
        with db_session(self.db_path) as connection:
            for event_id, record_id in key_list:
                rows = connection.execute(
                    """
                    SELECT cc.event_id, cc.record_id, cc.category_id,
                           cc.sentiment AS category_sentiment,
                           c.category_name, c.definition, c.summary
                    FROM comment_categories AS cc
                    JOIN categories AS c
                      ON c.event_id = cc.event_id
                     AND c.category_id = cc.category_id
                    WHERE cc.event_id = ? AND cc.record_id = ?
                    ORDER BY cc.category_id
                    """,
                    (event_id, record_id),
                ).fetchall()
                result[(event_id, record_id)] = [_row_to_dict(row) for row in rows]
        return result

    def get_analyses_for_events(
        self, event_ids: Iterable[str]
    ) -> dict[str, list[dict[str, Any]]]:
        ids = list(dict.fromkeys(event_ids))
        result: dict[str, list[dict[str, Any]]] = {event_id: [] for event_id in ids}
        if not ids:
            return result
        placeholders = ",".join("?" for _ in ids)
        with db_session(self.db_path) as connection:
            rows = connection.execute(
                f"SELECT * FROM analyses WHERE event_id IN ({placeholders}) "
                "ORDER BY event_id, created_at DESC",
                ids,
            ).fetchall()
        for row in rows:
            item = _row_to_dict(row)
            result[item["event_id"]].append(item)
        return result

    def get_persona(self, persona_id: str) -> dict[str, Any] | None:
        with db_session(self.db_path) as connection:
            row = connection.execute(
                "SELECT * FROM personas WHERE persona_id = ?", (persona_id,)
            ).fetchone()
        return _row_to_dict(row) if row else None

    def get_persona_evidence(self, persona_id: str) -> list[dict[str, Any]]:
        with db_session(self.db_path) as connection:
            rows = connection.execute(
                "SELECT * FROM persona_evidence WHERE persona_id = ? ORDER BY id",
                (persona_id,),
            ).fetchall()
        return [_row_to_dict(row) for row in rows]

    def get_simulations(
        self, persona_id: str | None = None, event_id: str | None = None
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        params: list[Any] = []
        if persona_id is not None:
            conditions.append("persona_id = ?")
            params.append(persona_id)
        if event_id is not None:
            conditions.append("event_id = ?")
            params.append(event_id)
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        with db_session(self.db_path) as connection:
            rows = connection.execute(
                f"SELECT * FROM simulations{where} ORDER BY created_at, simulation_id",
                params,
            ).fetchall()
        return [_row_to_dict(row) for row in rows]

    def import_persona(
        self, persona: dict[str, Any], evidence: Iterable[dict[str, Any]] = ()
    ) -> str:
        """幂等更新 Persona，并以传入 bundle 替换该 Persona 的旧证据集。"""

        persona_id = str(persona.get("persona_id", "")).strip()
        name = str(persona.get("name", "")).strip()
        persona_type = str(persona.get("persona_type", "")).strip()
        version = str(persona.get("version", "")).strip()
        if not persona_id:
            raise ValueError("persona.persona_id is required")
        if not all((name, persona_type, version)):
            raise ValueError("persona name, persona_type and version are required")
        status = str(persona.get("status", "active")).strip() or "active"
        evidence_rows = list(evidence)

        with db_session(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO personas(
                    persona_id, name, persona_type, version, status,
                    persona_json, skill_path, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(persona_id) DO UPDATE SET
                    name = excluded.name,
                    persona_type = excluded.persona_type,
                    version = excluded.version,
                    status = excluded.status,
                    persona_json = excluded.persona_json,
                    skill_path = excluded.skill_path,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    persona_id,
                    name,
                    persona_type,
                    version,
                    status,
                    _dump(persona),
                    persona.get("skill_path"),
                ),
            )
            connection.execute(
                "DELETE FROM persona_evidence WHERE persona_id = ?", (persona_id,)
            )
            for item in evidence_rows:
                role = str(item.get("evidence_role", "")).lower()
                if role not in {"anchor", "support", "context"}:
                    raise ValueError(f"invalid evidence_role: {role!r}")
                confidence = item.get("confidence")
                if confidence is not None and not 0.0 <= float(confidence) <= 1.0:
                    raise ValueError("evidence confidence must be between 0 and 1")
                connection.execute(
                    """
                    INSERT INTO persona_evidence(
                        persona_id, event_id, record_id, evidence_role,
                        feature, confidence, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        persona_id,
                        item["event_id"],
                        item["record_id"],
                        role,
                        item.get("feature"),
                        confidence,
                        item.get("notes"),
                    ),
                )
        return persona_id

    def add_simulation(self, simulation: dict[str, Any]) -> str:
        persona_id = str(simulation.get("persona_id", "")).strip()
        scenario_text = str(simulation.get("scenario_text", "")).strip()
        if not persona_id or not scenario_text:
            raise ValueError("simulation persona_id and scenario_text are required")
        simulation_id = str(simulation.get("simulation_id") or uuid.uuid4())
        with db_session(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO simulations(
                    simulation_id, persona_id, event_id, scenario_id,
                    scenario_text, model, response_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    simulation_id,
                    persona_id,
                    simulation.get("event_id"),
                    simulation.get("scenario_id"),
                    scenario_text,
                    simulation.get("model"),
                    _dump(simulation.get("response_json", {})),
                ),
            )
        return simulation_id


def list_events(db_path: str | Path = DEFAULT_DB_PATH) -> list[dict[str, Any]]:
    return Repository(db_path).list_events()


def get_event(event_id: str, db_path: str | Path = DEFAULT_DB_PATH) -> dict[str, Any] | None:
    return Repository(db_path).get_event(event_id)


def get_comments(
    event_id: str,
    platform: str | None = None,
    sentiment: str | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> list[dict[str, Any]]:
    return Repository(db_path).get_comments(event_id, platform, sentiment)


def get_comments_by_category(
    event_id: str, category_id: str, db_path: str | Path = DEFAULT_DB_PATH
) -> list[dict[str, Any]]:
    return Repository(db_path).get_comments_by_category(event_id, category_id)


def search_comments(
    query: str,
    event_id: str | None = None,
    exclude_event_id: str | None = None,
    platform: str | None = None,
    sentiment: str | None = None,
    category_id: str | None = None,
    limit: int = 50,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> list[dict[str, Any]]:
    return Repository(db_path).search_comments(
        query=query,
        event_id=event_id,
        exclude_event_id=exclude_event_id,
        platform=platform,
        sentiment=sentiment,
        category_id=category_id,
        limit=limit,
    )


def get_persona(
    persona_id: str, db_path: str | Path = DEFAULT_DB_PATH
) -> dict[str, Any] | None:
    return Repository(db_path).get_persona(persona_id)


def get_persona_evidence(
    persona_id: str, db_path: str | Path = DEFAULT_DB_PATH
) -> list[dict[str, Any]]:
    return Repository(db_path).get_persona_evidence(persona_id)


def get_simulations(
    persona_id: str | None = None,
    event_id: str | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> list[dict[str, Any]]:
    return Repository(db_path).get_simulations(persona_id, event_id)


def import_persona(
    persona: dict[str, Any],
    evidence: Iterable[dict[str, Any]] = (),
    db_path: str | Path = DEFAULT_DB_PATH,
) -> str:
    return Repository(db_path).import_persona(persona, evidence)


def add_simulation(
    simulation: dict[str, Any], db_path: str | Path = DEFAULT_DB_PATH
) -> str:
    return Repository(db_path).add_simulation(simulation)
