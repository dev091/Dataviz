from fastapi import APIRouter

from app.api.routes import admin, alerts, auth, billing, connections, dashboards, nl_analytics, semantic, workspaces


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])
api_router.include_router(connections.router, prefix="/connections", tags=["connections"])
api_router.include_router(semantic.router, prefix="/semantic", tags=["semantic"])
api_router.include_router(dashboards.router, prefix="/dashboards", tags=["dashboards"])
api_router.include_router(nl_analytics.router, prefix="/nl", tags=["nl"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])
