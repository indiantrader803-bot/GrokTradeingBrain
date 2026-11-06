import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn

import os
from dotenv import load_dotenv

load_dotenv()

from core.config import SystemConfig, TradingMode
from core.orchestrator import MasterOrchestrator
from adapters.paper import PaperAdapter
from adapters.delta_adapter import DeltaAdapter

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

    mode_str = os.getenv("TRADING_MODE", "demo").lower()
    trading_mode = TradingMode.REAL if mode_str == "real" else TradingMode.DEMO
    starting_eq = float(os.getenv("STARTING_EQUITY", "1000.0"))
    check_interval = int(os.getenv("CHECK_INTERVAL_SECONDS", "60"))
    server_ip = os.getenv("SERVER_IP", "127.0.0.1")

    config = SystemConfig(
        mode=trading_mode,
        starting_equity=starting_eq,
        check_interval_seconds=check_interval,
        server_ip=server_ip
    )

    adapters = {
        "paper": PaperAdapter(starting_equity=config.starting_equity)
    }

    delta_key = os.getenv("DELTA_INDIA_API_KEY", "").strip()
    delta_secret = os.getenv("DELTA_INDIA_API_SECRET", "").strip()
    delta_url = os.getenv("DELTA_INDIA_BASE_URL", "https://api.india.delta.exchange").strip()

    if delta_key and delta_secret:
        adapters["delta"] = DeltaAdapter(
            api_key=delta_key,
            api_secret=delta_secret,
            base_url=delta_url
        )
        log.info("Delta Exchange India adapter registered (API Key configured)")
    else:
        log.info("Delta Exchange India adapter not activated (DELTA_INDIA_API_KEY or DELTA_INDIA_API_SECRET not set in .env)")

    orchestrator = MasterOrchestrator(config, adapters)
    background_task = asyncio.create_task(orchestrator.start())
    log.info("Application started in %s mode", trading_mode.value.upper())

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
