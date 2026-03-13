from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.entities import AIQuerySession


EMBEDDING_DIMENSIONS = 16
SEARCH_WINDOW = 50
TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")


def embed_text(value: str) -> list[float]:
    tokens = TOKEN_PATTERN.findall(value.lower())
    vector = [0.0] * EMBEDDING_DIMENSIONS

    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for index in range(EMBEDDING_DIMENSIONS):
            direction = 1.0 if digest[index + EMBEDDING_DIMENSIONS] % 2 == 0 else -1.0
            vector[index] += direction * (digest[index] / 255.0)

    norm = math.sqrt(sum(component * component for component in vector))
    if norm == 0:
        return vector
    return [round(component / norm, 6) for component in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(component * component for component in left))
    right_norm = math.sqrt(sum(component * component for component in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(f"{value:.6f}" for value in embedding) + "]"


def retrieve_related_queries(
    db: Session,
    *,
    workspace_id: str,
    semantic_model_id: str,
    question: str,
    question_embedding: list[float],
    limit: int = 3,
) -> list[dict[str, Any]]:
    dialect = db.bind.dialect.name if db.bind is not None else ""
    normalized_question = question.strip().lower()

    if dialect == "postgresql":
        rows = db.execute(
            text(
                """
                SELECT
                    id,
                    question,
                    summary,
                    created_at,
                    1 - (question_embedding <=> CAST(:embedding AS vector)) AS similarity
                FROM ai_query_sessions
                WHERE workspace_id = :workspace_id
                  AND semantic_model_id = :semantic_model_id
                  AND question_embedding IS NOT NULL
                  AND LOWER(TRIM(question)) != :normalized_question
                ORDER BY question_embedding <=> CAST(:embedding AS vector)
                LIMIT :limit
                """
            ),
            {
                "workspace_id": workspace_id,
                "semantic_model_id": semantic_model_id,
                "normalized_question": normalized_question,
                "embedding": _vector_literal(question_embedding),
                "limit": limit,
            },
        ).mappings().all()

        return [
            {
                "id": row["id"],
                "question": row["question"],
                "summary": row["summary"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "similarity": round(float(row.get("similarity") or 0.0), 4),
            }
            for row in rows
        ]

    candidates = db.scalars(
        select(AIQuerySession)
        .where(
            AIQuerySession.workspace_id == workspace_id,
            AIQuerySession.semantic_model_id == semantic_model_id,
            AIQuerySession.question_embedding.is_not(None),
        )
        .order_by(AIQuerySession.created_at.desc())
        .limit(SEARCH_WINDOW)
    ).all()

    scored: list[dict[str, Any]] = []
    for session in candidates:
        if session.question.strip().lower() == normalized_question:
            continue
        session_embedding = session.question_embedding or []
        similarity = cosine_similarity(question_embedding, [float(value) for value in session_embedding])
        scored.append(
            {
                "id": session.id,
                "question": session.question,
                "summary": session.summary,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "similarity": round(similarity, 4),
            }
        )

    scored.sort(key=lambda item: item["similarity"], reverse=True)
    return scored[:limit]

