from pathlib import Path

from sqlalchemy import select

from app.db.base import SessionLocal
from app.db.init_db import init_db
from app.models.entities import Dashboard, DataConnection, Dataset, ReportSchedule, SemanticModel, User
from app.services.auth import create_user_with_org
from app.services.semantic import create_semantic_model
from app.services.sync import run_sync


def ensure_demo_csv(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "date,region,product,revenue,cost,memberships\n"
        "2025-01-01,North,Alpha,12000,6000,140\n"
        "2025-01-01,South,Alpha,9000,4700,120\n"
        "2025-02-01,North,Beta,14500,7100,165\n"
        "2025-02-01,South,Beta,9800,4900,128\n"
        "2025-03-01,North,Alpha,16200,7600,178\n"
        "2025-03-01,West,Gamma,11000,5600,133\n"
        "2025-04-01,North,Beta,17100,8200,185\n"
        "2025-04-01,West,Gamma,12800,6200,142\n"
        "2025-05-01,South,Alpha,11800,5900,136\n"
        "2025-05-01,West,Beta,13300,6500,148\n",
        encoding="utf-8",
    )


def seed() -> None:
    init_db()

    root = Path(__file__).resolve().parents[2]
    csv_path = root / "local_storage" / "seed" / "demo_sales.csv"
    ensure_demo_csv(csv_path)

    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == "owner@dataviz.com"))
        if existing:
            print("Seed already exists")
            return

        user, org, workspace = create_user_with_org(
            db,
            email="owner@dataviz.com",
            full_name="Demo Owner",
            password="Password123!",
            organization_name="Acme Analytics",
            workspace_name="Executive Workspace",
        )

        connection = DataConnection(
            organization_id=org.id,
            workspace_id=workspace.id,
            created_by=user.id,
            name="Demo Revenue CSV",
            connector_type="csv",
            config={"file_path": str(csv_path)},
            status="ready",
            sync_frequency="manual",
        )
        db.add(connection)
        db.flush()

        run_sync(db, connection)

        dataset = db.scalar(
            select(Dataset).where(Dataset.workspace_id == workspace.id, Dataset.connection_id == connection.id)
        )
        if not dataset:
            raise RuntimeError("Dataset sync failed in seed")

        model = create_semantic_model(
            db,
            workspace_id=workspace.id,
            created_by=user.id,
            name="Revenue Model",
            model_key="revenue_model",
            description="Core revenue and membership metrics",
            base_dataset_id=dataset.id,
            joins=[],
            metrics=[
                {"name": "revenue", "label": "Revenue", "formula": "SUM(revenue)", "aggregation": "sum"},
                {"name": "memberships", "label": "Memberships", "formula": "SUM(memberships)", "aggregation": "sum"},
                {"name": "gross_margin", "label": "Gross Margin", "formula": "SUM(revenue - cost)", "aggregation": "sum"},
            ],
            dimensions=[
                {"name": "date", "label": "Date", "field_ref": "date", "data_type": "date", "time_grain": "month"},
                {"name": "region", "label": "Region", "field_ref": "region", "data_type": "string"},
                {"name": "product", "label": "Product", "field_ref": "product", "data_type": "string"},
            ],
            calculated_fields=[
                {"name": "margin_ratio", "expression": "(revenue - cost) / NULLIF(revenue, 0)", "data_type": "float"}
            ],
        )

        dashboard = Dashboard(
            workspace_id=workspace.id,
            created_by=user.id,
            name="Executive Overview",
            description="Core weekly executive dashboard",
            layout={"cols": 12, "rowHeight": 30},
        )
        db.add(dashboard)
        db.flush()

        db.add(
            ReportSchedule(
                workspace_id=workspace.id,
                dashboard_id=dashboard.id,
                created_by=user.id,
                name="Weekly Exec Digest",
                email_to=["exec-team@dataviz.com"],
                schedule_type="weekly",
                daily_time="09:00",
                weekday=1,
                enabled=True,
            )
        )

        db.commit()

        print("Seed complete")
        print(f"Workspace ID: {workspace.id}")
        print(f"Semantic Model ID: {model.id}")


if __name__ == "__main__":
    seed()


