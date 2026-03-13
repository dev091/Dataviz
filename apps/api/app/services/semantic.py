import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import AIActionHistory, AIQuerySession, AuditLog, CalculatedField, Dataset, DatasetField, MetricLineage, SemanticDimension, SemanticMetric, SemanticModel


ALLOWED_AGG = {"sum", "avg", "count", "min", "max"}
ALLOWED_JOIN_TYPES = {"left", "inner", "right", "full"}
ALLOWED_CERTIFICATION = {"draft", "review", "certified", "deprecated"}
SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
AGG_EXPR_RE = re.compile(r"^(SUM|AVG|COUNT|MIN|MAX)\(\s*([A-Za-z_][A-Za-z0-9_]*|\*)\s*\)$", re.IGNORECASE)
CURRENCY_FIELD_HINTS = {"revenue", "amount", "sales", "cost", "price", "arr", "mrr", "gmv", "income", "expense", "profit", "spend"}
PERCENT_FIELD_HINTS = {"rate", "ratio", "pct", "percent", "margin", "share"}
IDENTIFIER_FIELD_HINTS = {"id", "key", "code", "number", "num"}


def _safe_identifier(value: str) -> bool:
    return bool(SAFE_IDENTIFIER_RE.fullmatch(value))


def _normalize_alias(value: str) -> str:
    alias = re.sub(r"[^A-Za-z0-9_]", "_", value.lower().strip())
    alias = re.sub(r"_+", "_", alias).strip("_")
    if not alias:
        alias = "dataset"
    if alias[0].isdigit():
        alias = f"d_{alias}"
    return alias


def _slugify(value: str) -> str:
    return _normalize_alias(value)


def _labelize(value: str) -> str:
    cleaned = re.sub(r"[_\-.]+", " ", value).strip()
    return re.sub(r"\s+", " ", cleaned).title() or "Field"


def _normalize_list(values: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        item = str(value).strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(item)
    return normalized


def _sanitize_lineage(lineage: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(lineage, dict) or not lineage:
        return None

    sanitized: dict[str, Any] = {}
    for key, value in lineage.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            sanitized[str(key)] = value
            continue
        if isinstance(value, list):
            sanitized[str(key)] = [item for item in value if isinstance(item, (str, int, float, bool))]
            continue
        if isinstance(value, dict):
            sanitized[str(key)] = {str(child_key): child_value for child_key, child_value in value.items() if isinstance(child_value, (str, int, float, bool))}
    return sanitized or None


def _qualified_dimension_expression(field_ref: str, base_alias: str) -> str:
    if "." in field_ref:
        return field_ref
    if _safe_identifier(field_ref):
        return f"{base_alias}.{field_ref}"
    return field_ref


def _qualified_metric_expression(formula: str, base_alias: str) -> str:
    if "." in formula:
        return formula

    if _safe_identifier(formula):
        return f"{base_alias}.{formula}"

    match = AGG_EXPR_RE.fullmatch(formula.strip())
    if not match:
        return formula

    agg, field = match.groups()
    if field == "*":
        return f"{agg.upper()}(*)"
    return f"{agg.upper()}({base_alias}.{field})"


def _extract_metric_source_fields(formula: str) -> list[str]:
    """Parse a metric formula to extract referenced field names for lineage."""
    match = AGG_EXPR_RE.fullmatch(formula.strip())
    if match:
        field = match.group(2)
        if field == "*":
            return []
        # Strip alias prefix if present
        if "." in field:
            field = field.split(".")[-1]
        return [field]
    simple_match = SAFE_IDENTIFIER_RE.fullmatch(formula.strip())
    if simple_match:
        return [formula.strip().split(".")[-1]] if "." in formula else [formula.strip()]
    # Complex expression: extract all identifier tokens
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", formula)
    keywords = {"SUM", "AVG", "COUNT", "MIN", "MAX", "sum", "avg", "count", "min", "max"}
    return [tok for tok in tokens if tok not in keywords]


def _build_alias_map(base_dataset: Dataset, datasets: list[Dataset]) -> dict[str, str]:
    alias_by_dataset: dict[str, str] = {}
    used: set[str] = set()

    def assign(dataset: Dataset) -> str:
        base_alias = _normalize_alias(dataset.name)
        alias = base_alias
        i = 2
        while alias in used:
            alias = f"{base_alias}_{i}"
            i += 1
        used.add(alias)
        alias_by_dataset[dataset.id] = alias
        return alias

    assign(base_dataset)
    for dataset in datasets:
        if dataset.id not in alias_by_dataset:
            assign(dataset)

    return alias_by_dataset


def _normalized_data_type(raw_data_type: str) -> str:
    value = raw_data_type.lower()
    if "datetime" in value or "timestamp" in value:
        return "datetime"
    if "date" in value or value.startswith("time"):
        return "date"
    if "bool" in value:
        return "boolean"
    if any(token in value for token in ["int", "bigint", "smallint"]):
        return "integer"
    if any(token in value for token in ["float", "double", "decimal", "numeric", "real"]):
        return "number"
    return "string"


def _is_time_field(field: DatasetField) -> bool:
    return _normalized_data_type(field.data_type) in {"date", "datetime"}


def _is_identifier_field(field_name: str) -> bool:
    normalized = field_name.lower().strip()
    if normalized in IDENTIFIER_FIELD_HINTS:
        return True
    return normalized.endswith("_id") or normalized.endswith("id") and normalized != "paid"


def _value_format_for_metric(field_name: str, field: DatasetField) -> str:
    normalized = field_name.lower()
    if any(hint in normalized for hint in CURRENCY_FIELD_HINTS):
        return "currency"
    if any(hint in normalized for hint in PERCENT_FIELD_HINTS):
        return "percent"
    return "integer" if _normalized_data_type(field.data_type) == "integer" else "number"


def _default_governance() -> dict[str, Any]:
    return {
        "owner_name": None,
        "owner_email": None,
        "certification_status": "draft",
        "certification_note": None,
        "trusted_for_nl": True,
    }


def _sanitize_governance(governance: dict[str, Any] | None) -> dict[str, Any]:
    payload = {**_default_governance(), **(governance or {})}
    status = str(payload.get("certification_status", "draft")).lower()
    payload["certification_status"] = status if status in ALLOWED_CERTIFICATION else "draft"
    payload["owner_name"] = str(payload.get("owner_name") or "").strip() or None
    payload["owner_email"] = str(payload.get("owner_email") or "").strip() or None
    payload["certification_note"] = str(payload.get("certification_note") or "").strip() or None
    payload["trusted_for_nl"] = bool(payload.get("trusted_for_nl", True))
    return payload


def _metric_metadata(metric: dict[str, Any]) -> dict[str, Any]:
    status = str(metric.get("certification_status", "draft")).lower()
    return {
        "description": str(metric.get("description") or "").strip() or None,
        "synonyms": _normalize_list(metric.get("synonyms")),
        "owner_name": str(metric.get("owner_name") or "").strip() or None,
        "certification_status": status if status in ALLOWED_CERTIFICATION else "draft",
        "certification_note": str(metric.get("certification_note") or "").strip() or None,
        "lineage": _sanitize_lineage(metric.get("lineage")),
    }


def _dimension_metadata(dimension: dict[str, Any]) -> dict[str, Any]:
    status = str(dimension.get("certification_status", "draft")).lower()
    return {
        "description": str(dimension.get("description") or "").strip() or None,
        "synonyms": _normalize_list(dimension.get("synonyms")),
        "hierarchy": _normalize_list(dimension.get("hierarchy")),
        "owner_name": str(dimension.get("owner_name") or "").strip() or None,
        "certification_status": status if status in ALLOWED_CERTIFICATION else "draft",
    }


def _definition_section(model: SemanticModel, key: str) -> dict[str, Any]:
    definition = model.definition or {}
    value = definition.get(key, {})
    return value if isinstance(value, dict) else {}


def infer_semantic_model_draft(
    *,
    dataset: Dataset,
    fields: list[DatasetField],
    name: str | None = None,
    model_key: str | None = None,
    description: str | None = None,
) -> dict:
    safe_fields = [field for field in fields if _safe_identifier(field.name)]
    notes: list[str] = []
    metrics: list[dict[str, Any]] = []
    dimensions: list[dict[str, Any]] = []
    calculated_fields: list[dict[str, Any]] = []

    if len(safe_fields) != len(fields):
        notes.append("Skipped fields with unsafe names during semantic draft generation.")

    numeric_metric_candidates = [field for field in safe_fields if field.is_metric and not _is_identifier_field(field.name)]
    dimension_candidates = [field for field in safe_fields if field.is_dimension or _is_identifier_field(field.name) or _is_time_field(field)]

    for field in numeric_metric_candidates[:8]:
        metrics.append(
            {
                "name": _slugify(field.name),
                "label": _labelize(field.name),
                "formula": f"SUM({field.name})",
                "aggregation": "sum",
                "value_format": _value_format_for_metric(field.name, field),
                "visibility": "public",
                "description": f"Governed metric derived from {field.name}.",
                "synonyms": [_labelize(field.name)],
                "owner_name": None,
                "certification_status": "draft",
            }
        )

    if len(numeric_metric_candidates) > 8:
        notes.append("Trimmed auto-generated metrics to the first 8 numeric candidates for a focused MVP draft.")

    for field in dimension_candidates[:12]:
        normalized_data_type = _normalized_data_type(field.data_type)
        hierarchy = ["year", "quarter", "month"] if normalized_data_type in {"date", "datetime"} else []
        dimensions.append(
            {
                "name": _slugify(field.name),
                "label": _labelize(field.name),
                "field_ref": field.name,
                "data_type": normalized_data_type,
                "time_grain": "month" if normalized_data_type in {"date", "datetime"} else None,
                "visibility": "public",
                "description": f"Governed dimension mapped from {field.name}.",
                "synonyms": [_labelize(field.name)],
                "hierarchy": hierarchy,
                "owner_name": None,
                "certification_status": "draft",
            }
        )

    if len(dimension_candidates) > 12:
        notes.append("Trimmed auto-generated dimensions to the first 12 candidates to keep the draft reviewable.")

    if not metrics:
        metrics.append(
            {
                "name": "row_count",
                "label": "Row Count",
                "formula": "COUNT(*)",
                "aggregation": "count",
                "value_format": "integer",
                "visibility": "public",
                "description": "Fallback governed KPI when no additive metric is detected.",
                "synonyms": ["Rows", "Records"],
                "owner_name": None,
                "certification_status": "draft",
            }
        )
        notes.append("No additive numeric measure was found, so the draft uses row count as the default KPI.")

    field_names = {field.name.lower(): field.name for field in safe_fields}
    revenue_field = next((field_names[key] for key in field_names if key in {"revenue", "sales", "amount", "arr", "mrr"}), None)
    cost_field = next((field_names[key] for key in field_names if key in {"cost", "cogs", "expense", "spend"}), None)
    if revenue_field and cost_field:
        calculated_fields.append(
            {
                "name": "gross_margin",
                "expression": f"{revenue_field} - {cost_field}",
                "data_type": "number",
            }
        )
        notes.append("Generated a `gross_margin` calculated field from detected revenue and cost columns.")

    if not dimensions and safe_fields:
        field = safe_fields[0]
        dimensions.append(
            {
                "name": _slugify(field.name),
                "label": _labelize(field.name),
                "field_ref": field.name,
                "data_type": _normalized_data_type(field.data_type),
                "time_grain": None,
                "visibility": "public",
                "description": f"Fallback governed dimension mapped from {field.name}.",
                "synonyms": [_labelize(field.name)],
                "hierarchy": [],
                "owner_name": None,
                "certification_status": "draft",
            }
        )
        notes.append("Added the first safe field as a fallback dimension because no categorical or time field was detected.")

    notes.append(f"Generated {len(metrics)} metrics, {len(dimensions)} dimensions, and {len(calculated_fields)} calculated fields from dataset `{dataset.name}`.")

    return {
        "name": name or f"{_labelize(dataset.name)} Model",
        "model_key": model_key or f"{_slugify(dataset.name)}_model",
        "description": description or f"Auto-generated governed model draft from dataset {dataset.name}.",
        "base_dataset_id": dataset.id,
        "joins": [],
        "metrics": metrics,
        "dimensions": dimensions,
        "calculated_fields": calculated_fields,
        "governance": _default_governance(),
        "inference_notes": notes,
    }


def validate_semantic_payload(
    *,
    base_dataset: Dataset | None,
    joins: list[dict],
    metrics: list[dict],
    dimensions: list[dict],
    calculated_fields: list[dict],
) -> list[str]:
    errors: list[str] = []
    if not base_dataset:
        errors.append("Base dataset not found")

    for join in joins:
        left_dataset_id = join.get("left_dataset_id")
        right_dataset_id = join.get("right_dataset_id")
        left_field = join.get("left_field")
        right_field = join.get("right_field")
        join_type = str(join.get("join_type", "left")).lower()

        if not left_dataset_id or not right_dataset_id:
            errors.append("Join must include left_dataset_id and right_dataset_id")
        if not left_field or not right_field:
            errors.append("Join must include left_field and right_field")
        if join_type not in ALLOWED_JOIN_TYPES:
            errors.append(f"Unsupported join_type '{join_type}'")

        for field_name, value in [("left_field", left_field), ("right_field", right_field)]:
            if value and not _safe_identifier(str(value)):
                errors.append(f"Unsafe join identifier '{field_name}'")

    metric_names = set()
    for metric in metrics:
        if metric["name"] in metric_names:
            errors.append(f"Duplicate metric name '{metric['name']}'")
        metric_names.add(metric["name"])

        agg = metric.get("aggregation", "sum").lower()
        if agg not in ALLOWED_AGG:
            errors.append(f"Unsupported aggregation '{agg}' for metric '{metric['name']}'")

        formula = metric.get("formula", "")
        if ";" in formula or "--" in formula:
            errors.append(f"Unsafe formula detected for metric '{metric['name']}'")

        certification_status = str(metric.get("certification_status", "draft")).lower()
        if certification_status not in ALLOWED_CERTIFICATION:
            errors.append(f"Unsupported certification_status '{certification_status}' for metric '{metric['name']}'")

    dim_names = set()
    for dim in dimensions:
        if dim["name"] in dim_names:
            errors.append(f"Duplicate dimension name '{dim['name']}'")
        dim_names.add(dim["name"])

        field_ref = dim.get("field_ref", "")
        if ";" in field_ref or "--" in field_ref:
            errors.append(f"Unsafe field reference in dimension '{dim['name']}'")

        certification_status = str(dim.get("certification_status", "draft")).lower()
        if certification_status not in ALLOWED_CERTIFICATION:
            errors.append(f"Unsupported certification_status '{certification_status}' for dimension '{dim['name']}'")

    for calc in calculated_fields:
        expr = calc.get("expression", "")
        if ";" in expr or "--" in expr:
            errors.append(f"Unsafe expression in calculated field '{calc['name']}'")

    return errors


def create_semantic_model(
    db: Session,
    *,
    workspace_id: str,
    created_by: str,
    name: str,
    model_key: str,
    description: str | None,
    base_dataset_id: str,
    joins: list[dict],
    metrics: list[dict],
    dimensions: list[dict],
    calculated_fields: list[dict],
    governance: dict[str, Any] | None = None,
) -> SemanticModel:
    latest_version = (
        db.scalar(
            select(func.max(SemanticModel.version)).where(
                SemanticModel.workspace_id == workspace_id,
                SemanticModel.model_key == model_key,
            )
        )
        or 0
    )

    model = SemanticModel(
        workspace_id=workspace_id,
        created_by=created_by,
        name=name,
        model_key=model_key,
        description=description,
        version=latest_version + 1,
        is_active=True,
        base_dataset_id=base_dataset_id,
        joins=joins,
        definition={
            "status": "published",
            "governance": _sanitize_governance(governance),
            "metric_metadata": {metric["name"]: _metric_metadata(metric) for metric in metrics},
            "dimension_metadata": {dimension["name"]: _dimension_metadata(dimension) for dimension in dimensions},
        },
    )
    db.add(model)
    db.flush()

    for metric in metrics:
        db.add(
            SemanticMetric(
                semantic_model_id=model.id,
                name=metric["name"],
                label=metric["label"],
                formula=metric["formula"],
                aggregation=metric.get("aggregation", "sum"),
                value_format=metric.get("value_format"),
                visibility=metric.get("visibility", "public"),
            )
        )

    for dimension in dimensions:
        db.add(
            SemanticDimension(
                semantic_model_id=model.id,
                name=dimension["name"],
                label=dimension["label"],
                field_ref=dimension["field_ref"],
                data_type=dimension["data_type"],
                time_grain=dimension.get("time_grain"),
                visibility=dimension.get("visibility", "public"),
            )
        )

    for calc in calculated_fields:
        db.add(
            CalculatedField(
                semantic_model_id=model.id,
                name=calc["name"],
                expression=calc["expression"],
                data_type=calc["data_type"],
            )
        )

    db.flush()

    # Auto-record metric lineage
    persisted_metrics = db.scalars(
        select(SemanticMetric).where(SemanticMetric.semantic_model_id == model.id)
    ).all()
    persisted_calcs = db.scalars(
        select(CalculatedField).where(CalculatedField.semantic_model_id == model.id)
    ).all()
    calc_names = {cf.name.lower() for cf in persisted_calcs}
    for metric_obj in persisted_metrics:
        source_fields = _extract_metric_source_fields(metric_obj.formula)
        for field_name in source_fields:
            db.add(MetricLineage(
                workspace_id=workspace_id,
                semantic_model_id=model.id,
                semantic_metric_id=metric_obj.id,
                source_dataset_id=base_dataset_id,
                source_field=field_name,
                source_type="calculated_field" if field_name.lower() in calc_names else "raw_field",
                transformation_summary=f"{metric_obj.aggregation.upper()}({field_name}) → {metric_obj.name}",
                confidence=1.0,
            ))
        if not source_fields:
            db.add(MetricLineage(
                workspace_id=workspace_id,
                semantic_model_id=model.id,
                semantic_metric_id=metric_obj.id,
                source_dataset_id=base_dataset_id,
                source_field="*",
                source_type="aggregation",
                transformation_summary=f"{metric_obj.formula} → {metric_obj.name}",
                confidence=0.8,
            ))

    # Record AI action history for semantic model creation
    db.add(AIActionHistory(
        workspace_id=workspace_id,
        actor_id=created_by,
        action_type="semantic_model_create",
        input_summary=f"Created semantic model '{name}' from dataset {base_dataset_id}",
        output_summary=f"Model with {len(metrics)} metrics, {len(dimensions)} dimensions, {len(calculated_fields)} calculated fields",
        artifact_ref=model.id,
        artifact_type="semantic_model",
        status="completed",
    ))

    db.flush()
    return model


def semantic_context(db: Session, semantic_model_id: str) -> dict[str, Any]:
    model = db.get(SemanticModel, semantic_model_id)
    if not model:
        raise ValueError("Semantic model not found")

    base_dataset = db.get(Dataset, model.base_dataset_id)
    if not base_dataset:
        raise ValueError("Base dataset not found")

    datasets = db.scalars(select(Dataset).where(Dataset.workspace_id == model.workspace_id)).all()
    dataset_by_id = {dataset.id: dataset for dataset in datasets}

    alias_by_dataset_id = _build_alias_map(base_dataset, datasets)
    base_alias = alias_by_dataset_id[base_dataset.id]

    joins: list[dict[str, str]] = []
    for join in model.joins:
        left_dataset_id = join.get("left_dataset_id")
        right_dataset_id = join.get("right_dataset_id")
        left_field = join.get("left_field")
        right_field = join.get("right_field")
        join_type = str(join.get("join_type", "left")).lower()

        if not left_dataset_id or not right_dataset_id or not left_field or not right_field:
            continue

        left_dataset = dataset_by_id.get(left_dataset_id)
        right_dataset = dataset_by_id.get(right_dataset_id)
        if not left_dataset or not right_dataset:
            continue

        left_alias = str(join.get("left_alias") or alias_by_dataset_id[left_dataset_id])
        right_alias = str(join.get("right_alias") or alias_by_dataset_id[right_dataset_id])

        joins.append(
            {
                "left_table": left_dataset.physical_table,
                "right_table": right_dataset.physical_table,
                "left_alias": left_alias,
                "right_alias": right_alias,
                "left_field": str(left_field),
                "right_field": str(right_field),
                "join_type": join_type,
            }
        )

    metrics = db.scalars(select(SemanticMetric).where(SemanticMetric.semantic_model_id == model.id)).all()
    dimensions = db.scalars(select(SemanticDimension).where(SemanticDimension.semantic_model_id == model.id)).all()

    metric_sql = {metric.name: _qualified_metric_expression(metric.formula, base_alias) for metric in metrics}
    dimension_sql = {dimension.name: _qualified_dimension_expression(dimension.field_ref, base_alias) for dimension in dimensions}

    return {
        "model": model,
        "dataset": base_dataset,
        "base_table": base_dataset.physical_table,
        "base_alias": base_alias,
        "joins": joins,
        "metrics": metrics,
        "dimensions": dimensions,
        "metric_sql": metric_sql,
        "dimension_sql": dimension_sql,
    }


def semantic_detail_payload(db: Session, model: SemanticModel) -> dict[str, Any]:
    metrics = db.scalars(select(SemanticMetric).where(SemanticMetric.semantic_model_id == model.id).order_by(SemanticMetric.name.asc())).all()
    dimensions = db.scalars(select(SemanticDimension).where(SemanticDimension.semantic_model_id == model.id).order_by(SemanticDimension.name.asc())).all()
    calculated_fields = db.scalars(
        select(CalculatedField).where(CalculatedField.semantic_model_id == model.id).order_by(CalculatedField.name.asc())
    ).all()

    metric_metadata = _definition_section(model, "metric_metadata")
    dimension_metadata = _definition_section(model, "dimension_metadata")
    governance = _sanitize_governance(_definition_section(model, "governance"))

    return {
        "id": model.id,
        "workspace_id": model.workspace_id,
        "name": model.name,
        "model_key": model.model_key,
        "version": model.version,
        "is_active": model.is_active,
        "base_dataset_id": model.base_dataset_id,
        "description": model.description,
        "created_at": model.created_at,
        "joins": model.joins,
        "governance": governance,
        "metrics": [
            {
                "name": metric.name,
                "label": metric.label,
                "formula": metric.formula,
                "aggregation": metric.aggregation,
                "value_format": metric.value_format,
                "visibility": metric.visibility,
                **(_metric_metadata(metric_metadata.get(metric.name, {}))),
            }
            for metric in metrics
        ],
        "dimensions": [
            {
                "name": dimension.name,
                "label": dimension.label,
                "field_ref": dimension.field_ref,
                "data_type": dimension.data_type,
                "time_grain": dimension.time_grain,
                "visibility": dimension.visibility,
                **(_dimension_metadata(dimension_metadata.get(dimension.name, {}))),
            }
            for dimension in dimensions
        ],
        "calculated_fields": [
            {
                "name": field.name,
                "expression": field.expression,
                "data_type": field.data_type,
            }
            for field in calculated_fields
        ],
    }


def semantic_trust_panel(db: Session, model: SemanticModel) -> dict[str, Any]:
    detail = semantic_detail_payload(db, model)
    base_dataset = db.get(Dataset, model.base_dataset_id)
    joins = detail["joins"]
    metrics = detail["metrics"]
    dimensions = detail["dimensions"]

    datasets_in_scope = {base_dataset.name if base_dataset else model.base_dataset_id}
    for join in joins:
        right_dataset = db.get(Dataset, join.get("right_dataset_id")) if join.get("right_dataset_id") else None
        if right_dataset:
            datasets_in_scope.add(right_dataset.name)

    recent_activity: list[dict[str, Any]] = []
    audit_rows = db.scalars(
        select(AuditLog)
        .where(AuditLog.workspace_id == model.workspace_id, AuditLog.entity_type == "semantic_model", AuditLog.entity_id == model.id)
        .order_by(AuditLog.created_at.desc())
        .limit(4)
    ).all()
    for row in audit_rows:
        recent_activity.append(
            {
                "activity_type": "audit",
                "title": row.action,
                "detail": None,
                "created_at": row.created_at,
            }
        )

    recent_queries = db.scalars(
        select(AIQuerySession)
        .where(AIQuerySession.semantic_model_id == model.id)
        .order_by(AIQuerySession.created_at.desc())
        .limit(4)
    ).all()
    for query in recent_queries:
        recent_activity.append(
            {
                "activity_type": "nl_query",
                "title": query.question,
                "detail": query.summary,
                "created_at": query.created_at,
            }
        )

    recent_activity.sort(key=lambda item: item["created_at"], reverse=True)
    governance = detail["governance"]

    open_gaps: list[str] = []
    if not governance.get("owner_name"):
        open_gaps.append("Assign a semantic owner before broad rollout.")
    if governance.get("certification_status") != "certified":
        open_gaps.append("Certification is still incomplete for this semantic model.")
    if not governance.get("trusted_for_nl", True):
        open_gaps.append("Model is not yet marked as trusted for natural-language analytics.")
    if any(metric.get("visibility") == "public" and not metric.get("synonyms") for metric in metrics):
        open_gaps.append("Some public metrics do not yet have synonym coverage for business phrasing.")
    if any(dimension.get("visibility") == "public" and not dimension.get("hierarchy") and dimension.get("data_type") == "string" for dimension in dimensions):
        open_gaps.append("Some public dimensions do not yet declare a reusable hierarchy.")
    if any(metric.get("visibility") == "public" and not metric.get("lineage") for metric in metrics):
        open_gaps.append("Some public metrics do not yet preserve migration or semantic lineage.")

    return {
        "model_id": model.id,
        "model_name": model.name,
        "model_key": model.model_key,
        "version": model.version,
        "governance": governance,
        "lineage_summary": {
            "base_dataset_name": base_dataset.name if base_dataset else model.base_dataset_id,
            "base_quality_status": base_dataset.quality_status if base_dataset else "unknown",
            "joins_configured": len(joins),
            "datasets_in_scope": sorted(datasets_in_scope),
            "metrics_governed": len(metrics),
            "dimensions_governed": len(dimensions),
            "metrics_with_lineage": sum(1 for metric in metrics if metric.get("lineage")), 
        },
        "recent_activity": recent_activity[:6],
        "open_gaps": open_gaps,
    }

