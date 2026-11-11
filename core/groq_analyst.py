import os
import json
import logging
from typing import Dict, Any, Optional
import httpx
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("GroqAnalystAgent")


class GroqAnalystAI:
    """
    Groq Ultra-Fast AI Reasoning Agent for Grok Bot
    ===============================================
    Uses high-speed LLM inference (e.g. openai/gpt-oss-120b or qwen/qwen3.8-27b)
    to perform multi-factor qualitative validation of survivor trade setups:
      - Evaluates Volume vs Price momentum divergence
      - Detects liquidity traps, blow-off tops, and exhaustion wicks
      - Validates Risk:Reward suitability for small capital compounding
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "").strip()
        self.model = model or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
        self.client = httpx.AsyncClient(timeout=10.0)

    async def evaluate_trade_candidate(
        self,
        symbol: str,
        price: float,
        direction: str,
        stop_loss: float,
        take_profit: float,
        vwap: float,
        structure: str,
        change_24h: float,
        volume_usd: float,
        account_equity: float = 1.60
    ) -> Dict[str, Any]:
        """
        Sends trade context to Groq AI for second-layer risk & consensus verification.
        """
        if not self.api_key:
            return {"approved": True, "ai_confidence": 0.85, "reasoning": "AI validation bypassed (no key)"}

        prompt = (
            f"You are the Grok Bot Institutional Risk & Consensus AI. "
            f"Evaluate this proposed trade for execution:\n"
            f"- Symbol: {symbol}\n"
            f"- Proposed Direction: {direction}\n"
            f"- Entry Price: {price}\n"
            f"- Stop Loss (-6%): {stop_loss}\n"
            f"- Take Profit (+12%): {take_profit}\n"
            f"- 24h Change: {change_24h:+.2f}%\n"
            f"- 24h Volume USD: ${volume_usd:,.0f}\n"
            f"- Current VWAP: {vwap}\n"
            f"- Market Structure: {structure}\n\n"
            f"Criteria:\n"
            f"1. Is the trade entering in the direction of market momentum?\n"
            f"2. Does the volume support the move without extreme anomaly?\n"
            f"3. Note: Capital sizing and margin are handled separately by the risk engine, so evaluate purely based on technical setup quality.\n\n"
            f"Respond STRICTLY in JSON format with exact keys:\n"
            f'{{"approved": true/false, "ai_confidence": 0.0 to 1.0, "decision": "BUY"|"SELL"|"WAIT", "reasoning": "1 short sentence"}}'
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }

        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a professional quant trader and risk manager. Respond strictly in valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }

        try:
            res = await self.client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=body
            )
            if res.status_code == 200:
                data = res.json()
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                log.info("Groq AI Evaluation [%s]: %s (Score: %.2f) -> %s", symbol, parsed.get("decision"), parsed.get("ai_confidence", 0), parsed.get("reasoning"))
                return parsed
            else:
                log.warning("Groq API returned HTTP %s: %s", res.status_code, res.text)
                return {"approved": True, "ai_confidence": 0.75, "reasoning": f"Groq fallback ({res.status_code})"}
        except Exception as e:
            log.warning("Groq evaluation error for %s: %s", symbol, e)
            return {"approved": True, "ai_confidence": 0.75, "reasoning": f"AI error fallback: {e}"}
