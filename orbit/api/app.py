"""
FastAPI Application Entrypoint for ORBIT.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from orbit.api.routes import router

app = FastAPI(
    title="ORBIT — Orchestrated Reasoning and Benchmarking for Infrastructure Testing API",
    description="AI Agent platform for architecture reasoning, empirical benchmarking, and discrete-event simulation.",
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


@app.get("/api/health")
def api_health():
    return {"status": "ok", "service": "ORBIT API"}


@app.get("/")
def root():
    return {
        "service": "ORBIT API",
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
            "/api/demo/run",
        ],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("orbit.api.app:app", host="0.0.0.0", port=8000, reload=True)
