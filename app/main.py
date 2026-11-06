import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn

from core.config import SystemConfig, TradingMode
from core.orchestrator import MasterOrchestrator
from adapters.paper import PaperAdapter

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("App")

# Global orchestrator instance
orchestrator: MasterOrchestrator | None = None
background_task = None

templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "dashboard" / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator, background_task

    config = SystemConfig(
        mode=TradingMode.DEMO,
        starting_equity=1000.0,
        check_interval_seconds=60
    )

    # Start with paper adapter only.
    # Later you add real adapters here.
    adapters = {
        "paper": PaperAdapter(starting_equity=config.starting_equity)
    }

    orchestrator = MasterOrchestrator(config, adapters)
    background_task = asyncio.create_task(orchestrator.start())
    log.info("Application started in DEMO mode")

    yield

    if orchestrator:
        orchestrator.stop()
    if background_task:
        background_task.cancel()
        try:
            await background_task
        except asyncio.CancelledError:
            pass
    log.info("Application shutdown complete")


app = FastAPI(
    title="Grok Capital Growth Trading Brain",
    description="Autonomous multi-asset trading core with web dashboard",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    status = orchestrator.get_status() if orchestrator else {}
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "status": status
        }
    )


@app.get("/api/status")
async def api_status():
    if not orchestrator:
        return {"error": "Orchestrator not running"}
    return orchestrator.get_status()


@app.post("/api/weekend-flags")
async def set_weekend_flags(
    strong_order_flow: bool = False,
    high_volume: bool = False,
    high_impact_news: bool = False
):
    if not orchestrator:
        return {"error": "Orchestrator not running"}
    orchestrator.set_weekend_flags(
        strong_order_flow=strong_order_flow,
        high_volume=high_volume,
        high_impact_news=high_impact_news
    )
    return {"ok": True, "flags": {
        "strong_order_flow": strong_order_flow,
        "high_volume": high_volume,
        "high_impact_news": high_impact_news
    }}


@app.post("/api/stop")
async def stop_trading():
    if orchestrator:
        orchestrator.stop()
    return {"ok": True, "message": "Stop signal sent"}


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
