"""
FastAPI Application Entrypoint for AADS.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from aads.api.routes import router

app = FastAPI(
    title="Agentic Architecture Design & Simulation (AADS) API",
    description="AI Agent backend for backend system architecture comparison, benchmarking, and discrete-event simulation.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return {
        "service": "AADS API",
        "status": "healthy",
        "docs_url": "/docs",
        "endpoints": [
            "/api/workload/validate",
            "/api/candidates",
            "/api/registry/models",
            "/api/registry/experiments",
            "/api/registry/check-compatibility",
            "/api/benchmark/run",
            "/api/simulate",
            "/api/evaluate",
            "/api/workflow/run",
            "/api/agent/run",
        ],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("aads.api.app:app", host="0.0.0.0", port=8000, reload=True)
