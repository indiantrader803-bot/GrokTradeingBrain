import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn

from core.auth import (
    authenticate_user,
    register_user,
    create_session_token,
    verify_session_token,
    get_users
)

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

    # When in REAL mode and real exchange is configured, do not add paper adapter
    # so risk calculations strictly use the live exchange balance.
    adapters = {}

    delta_key = os.getenv("DELTA_INDIA_API_KEY", "").strip()
    delta_secret = os.getenv("DELTA_INDIA_API_SECRET", "").strip()
    delta_url = os.getenv("DELTA_INDIA_BASE_URL", "https://api.india.delta.exchange").strip()

    if delta_key and delta_secret:
        delta_adapter = DeltaAdapter(
            api_key=delta_key,
            api_secret=delta_secret,
            base_url=delta_url
        )
        adapters["delta"] = delta_adapter
        log.info("Delta Exchange India adapter registered (API Key configured)")

        # Query live balance from exchange to calibrate starting_equity
        if trading_mode == TradingMode.REAL:
            try:
                live_equity = await delta_adapter.get_equity()
                if live_equity > 0:
                    config.starting_equity = live_equity
                    log.info("Calibrated starting equity from live Delta exchange balance: $%.2f", live_equity)
            except Exception as e:
                log.warning("Could not pre-fetch live equity: %s", e)
    else:
        log.info("Delta Exchange India adapter not activated (DELTA_INDIA_API_KEY or DELTA_INDIA_API_SECRET not set in .env)")

    # Only fallback to paper if in DEMO mode or no real exchange configured
    if trading_mode == TradingMode.DEMO or not adapters:
        adapters["paper"] = PaperAdapter(starting_equity=config.starting_equity)


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


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    token = request.cookies.get("session_token")
    if token and verify_session_token(token):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login", response_class=HTMLResponse)
async def handle_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    user = authenticate_user(username, password)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid username or password. Check credentials."}
        )
    token = create_session_token(user["username"])
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(key="session_token", value=token, max_age=86400 * 30, httponly=True)
    return response


@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request, "error": None})


@app.post("/signup", response_class=HTMLResponse)
async def handle_signup(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...)
):
    if len(password) < 6:
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": "Password must be at least 6 characters long."}
        )
    if password != confirm_password:
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": "Passwords do not match."}
        )
    ok = register_user(username, password)
    if not ok:
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": "Username already taken. Please choose another."}
        )
    token = create_session_token(username.lower().strip())
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(key="session_token", value=token, max_age=86400 * 30, httponly=True)
    return response


@app.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("session_token")
    return response


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    token = request.cookies.get("session_token")
    current_user = verify_session_token(token) if token else None
    if not current_user:
        return RedirectResponse("/login", status_code=302)

    status = orchestrator.get_status() if orchestrator else {}
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "status": status,
            "username": current_user
        }
    )


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    token = request.cookies.get("session_token")
    current_user = verify_session_token(token) if token else None
    if not current_user:
        return RedirectResponse("/login", status_code=302)

    status_data = await orchestrator.get_live_exchange_data() if orchestrator else {}
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "status": status_data,
            "exchange": status_data.get("exchange", {}),
            "username": current_user
        }
    )


@app.get("/positions", response_class=HTMLResponse)
async def positions_page(request: Request):
    token = request.cookies.get("session_token")
    current_user = verify_session_token(token) if token else None
    if not current_user:
        return RedirectResponse("/login", status_code=302)

    status_data = await orchestrator.get_live_exchange_data() if orchestrator else {}
    return templates.TemplateResponse(
        "positions.html",
        {
            "request": request,
            "exchange": status_data.get("exchange", {}),
            "username": current_user
        }
    )


@app.get("/coins", response_class=HTMLResponse)
async def coins_page(request: Request):
    token = request.cookies.get("session_token")
    current_user = verify_session_token(token) if token else None
    if not current_user:
        return RedirectResponse("/login", status_code=302)

    coins = orchestrator.config.strategy.crypto_majors if orchestrator else []
    metals = orchestrator.config.strategy.metals if orchestrator else []
    indices = orchestrator.config.strategy.indices if orchestrator else []
    forex = orchestrator.config.strategy.forex_majors if orchestrator else []

    return templates.TemplateResponse(
        "coins.html",
        {
            "request": request,
            "coins": coins,
            "metals": metals,
            "indices": indices,
            "forex": forex,
            "username": current_user
        }
    )


@app.get("/api/status")
async def api_status():
    if not orchestrator:
        return {"error": "Orchestrator not running"}
    return await orchestrator.get_live_exchange_data()


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
    server_port = int(os.getenv("PORT", "8000"))
    server_host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run(
        "app.main:app",
        host=server_host,
        port=server_port,
        reload=False,
        log_level="info"
    )
