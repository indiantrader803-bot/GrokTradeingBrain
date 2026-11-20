import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
import httpx

log = logging.getLogger("TelegramNotifier")

class TelegramNotifier:
    """
    Non-blocking Async Telegram Alert Dispatcher
    ============================================
    Sends real-time platform event messages to a designated Telegram chat.
    Will never block trading execution or alter risk engine decisions.
    """

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None, enabled: bool = False):
        self.bot_token = bot_token or ""
        self.chat_id = chat_id or ""
        self.enabled = enabled and bool(self.bot_token and self.chat_id)
        self.client = httpx.AsyncClient(timeout=5.0)

    async def send_message(self, text: str):
        if not self.enabled:
            return
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML"
            }
            await self.client.post(url, json=payload)
        except Exception as e:
            log.warning("Telegram notification failed: %s", e)

    async def notify_startup(self, mode: str, env: str, equity: float):
        msg = f"🚀 <b>Delta AI Trading Platform Started</b>\n• Mode: <code>{mode}</code>\n• Environment: <code>{env}</code>\n• Account Equity: <b>${equity:.2f}</b>"
        await self.send_message(msg)

    async def notify_trade_signal(self, symbol: str, direction: str, strategy: str, score: float, sl: float, tp: float):
        msg = (
            f"⚡ <b>New Trading Signal</b>\n"
            f"• Market: <b>{symbol}</b>\n"
            f"• Action: <b>{direction}</b>\n"
            f"• Strategy: <code>{strategy}</code>\n"
            f"• Score: <b>{score}/100</b>\n"
            f"• SL: ${sl:.4f} | TP: ${tp:.4f}"
        )
        await self.send_message(msg)

    async def notify_order_filled(self, mode: str, symbol: str, side: str, price: float, size: float):
        msg = f"✅ <b>[{mode}] Order Executed</b>\n• {side} {size}x <b>{symbol}</b> @ ${price:.4f}"
        await self.send_message(msg)

    async def notify_position_closed(self, mode: str, symbol: str, pnl: float, reason: str):
        sign = "+" if pnl >= 0 else ""
        icon = "🎉" if pnl >= 0 else "🛑"
        msg = f"{icon} <b>[{mode}] Position Closed</b>\n• Market: <b>{symbol}</b>\n• Reason: {reason}\n• Net PnL: <b>{sign}${pnl:.4f}</b>"
        await self.send_message(msg)

    async def notify_risk_alert(self, reason: str):
        msg = f"⚠️ <b>RISK ALERT</b>\n{reason}"
        await self.send_message(msg)
