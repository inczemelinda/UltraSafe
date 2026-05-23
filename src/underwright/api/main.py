"""
Underwright FastAPI application entry point.

Builds the FastAPI app and registers all route modules.
Run with: uvicorn underwright.api.main:app --reload
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from underwright.api.routes.auth import router as auth_router
from underwright.api.routes.auth_users import router as auth_users_router
from underwright.api.routes.claim_review_views import router as claim_review_views_router
from underwright.api.routes.claims import router as claims_router
from underwright.api.routes.claims import (
    internal_router as internal_claims_router,
    me_router as client_claims_router,
    underwriter_router as underwriter_claims_router,
)
from underwright.api.routes.contracts import quote_contract_router
from underwright.api.routes.contracts import generated_documents_router
from underwright.api.routes.contracts import me_router as client_contracts_router
from underwright.api.routes.contracts import router as contracts_router
from underwright.api.routes.customer_profile import router as customer_profile_router
from underwright.api.routes.customers import router as customers_router
from underwright.api.routes.intelligence import router as intelligence_router
from underwright.api.routes.quotes import router as quotes_router
from underwright.api.routes.quotes import (
    me_router as client_quotes_router,
    underwriter_router as underwriter_quotes_router,
)
from underwright.api.routes.emails import router as emails_router
from underwright.api.routes.postmark_webhooks import router as postmark_webhooks_router
from underwright.api.routes.review_views import router as review_views_router
from underwright.api.routes.raw_ingestion import router as raw_ingestion_router
from underwright.api.routes.underwriting_rules import (
    router as underwriting_rules_router,
)
from underwright.api.routes.wording_documents import router as wording_documents_router

# run in terminal with: uvicorn underwright.api.main:app --reload
# da click ori pe link din terminal ori http://127.0.0.1:8000/ dupa run


def create_app() -> FastAPI:
    app = FastAPI(
        title="Underwright API",
        version="0.1.0",
        description="Underwright MVP FastAPI routes.",
    )
    allowed_origins = [
        origin.strip()
        for origin in os.environ.get(
            "UNDERWRIGHT_CORS_ORIGINS",
            ",".join(
                [
                    "http://127.0.0.1:5173",
                    "http://localhost:5173",
                    "http://127.0.0.1:5174",
                    "http://localhost:5174",
                    "http://127.0.0.1:5175",
                    "http://localhost:5175",
                ]
            ),
        ).split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router)
    app.include_router(auth_users_router)
    app.include_router(claims_router)
    app.include_router(client_claims_router)
    app.include_router(underwriter_claims_router)
    app.include_router(internal_claims_router)
    app.include_router(claim_review_views_router)
    app.include_router(contracts_router)
    app.include_router(client_contracts_router)
    app.include_router(customer_profile_router)
    app.include_router(customers_router)
    app.include_router(generated_documents_router)
    app.include_router(intelligence_router)
    app.include_router(quotes_router)
    app.include_router(client_quotes_router)
    app.include_router(quote_contract_router)
    app.include_router(underwriter_quotes_router)
    app.include_router(review_views_router)
    app.include_router(raw_ingestion_router)
    app.include_router(emails_router)
    app.include_router(postmark_webhooks_router)
    app.include_router(underwriting_rules_router)
    app.include_router(wording_documents_router)

    @app.get("/")
    def read_root():
        return {
            "Hello": "World"
        }  # for now, cand avem frontend o sa folosim cu cors_origin

    return app


app = create_app()
