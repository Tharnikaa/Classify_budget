"""FastAPI application entrypoint for ExpenseIt."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import analytics, auth, claims, notifications, ocr, policies, workflow
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers


def create_app(settings_override: Settings | None = None) -> FastAPI:
    cfg = settings_override or get_settings()

    application = FastAPI(
        title="ExpenseIt API",
        version="1.0.0",
        description=(
            "Automated corporate expense classification & policy validation backend "
            "(INR paise precision, 4 RBAC roles x Spend Tiers, Separation of Duties)."
        ),
    )

    if settings_override is not None:
        application.dependency_overrides[get_settings] = lambda: settings_override

    origins = cfg.cors_origin_list
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=origins != ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(application)

    @application.get("/api/v1/health", tags=["System"])
    def health_check() -> dict[str, str]:
        return {
            "status": "ok",
            "app_env": cfg.APP_ENV,
            "base_currency": cfg.BASE_CURRENCY,
            "timezone": cfg.COMPANY_TIMEZONE,
        }

    application.include_router(auth.router)
    application.include_router(policies.router)
    application.include_router(ocr.router)
    application.include_router(claims.router)
    application.include_router(workflow.router)
    application.include_router(notifications.router)
    application.include_router(analytics.router)

    return application


app = create_app()

