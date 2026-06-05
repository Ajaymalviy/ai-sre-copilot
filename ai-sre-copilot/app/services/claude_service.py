"""
LLM Service (Multiple providers support)
========================================
Anthropic, OpenAI, Groq - sab support karta hai.

.env mein set karo:
  LLM_PROVIDER=groq
  GROQ_API_KEY=gsk_xxxx  (free tier available!)
"""
import httpx
import structlog
from app.core.config import settings

logger = structlog.get_logger()


class LLMService:

    async def analyze(self, system_prompt: str, user_message: str) -> str:
        """
        Claude ke jaise analyze karwao, but any LLM se.
        """
        provider = settings.LLM_PROVIDER.lower()

        if provider == "anthropic":
            return await self._anthropic(system_prompt, user_message)
        elif provider == "openai":
            return await self._openai(system_prompt, user_message)
        elif provider == "groq":
            return await self._groq(system_prompt, user_message)
        else:
            # Default: mock response
            return self._mock_response(user_message)

    async def _anthropic(self, system_prompt: str, user_message: str) -> str:
        """Anthropic API call"""
        if not settings.ANTHROPIC_API_KEY:
            logger.warning("Anthropic API key not set, using mock")
            return self._mock_response(user_message)

        headers = {
            "x-api-key":         settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type":      "application/json",
        }

        payload = {
            "model":      "claude-3-5-haiku-20241022",
            "max_tokens": 1024,
            "system":     system_prompt,
            "messages": [{"role": "user", "content": user_message}],
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload
                )
                resp.raise_for_status()
                data = resp.json()
                return data["content"][0]["text"]
        except Exception as e:
            logger.error("Anthropic API failed", error=str(e))
            return self._mock_response(user_message)

    async def _openai(self, system_prompt: str, user_message: str) -> str:
        """OpenAI API call (GPT-3.5 Turbo - cheap!)"""
        if not settings.OPENAI_API_KEY:
            logger.warning("OpenAI API key not set, using mock")
            return self._mock_response(user_message)

        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type":  "application/json",
        }

        payload = {
            "model":       "gpt-3.5-turbo",
            "temperature": 0.7,
            "max_tokens":  1024,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message},
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error("OpenAI API failed", error=str(e))
            return self._mock_response(user_message)

    async def _groq(self, system_prompt: str, user_message: str) -> str:
        """Groq API call (NEW MODELS! llama-3.1-8b-instant)"""
        if not settings.GROQ_API_KEY:
            logger.warning("Groq API key not set, using mock")
            return self._mock_response(user_message)

        headers = {
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type":  "application/json",
        }

        # Updated models (mixtral-8x7b-32768 is decommissioned)
        # Use llama-3.1-70b-versatile for best quality
        # Or llama-3.1-8b-instant for faster responses
        payload = {
            "model":       "c,  # NEW: Updated model
            "temperature": 0.7,
            "max_tokens":  1024,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message},
            ],
        }

        try:
            print("i am in try")
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=payload
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error("Groq API failed", error=str(e))
            logger.info("Groq error details", error_str=str(e))
            return self._mock_response(user_message)

    def _mock_response(self, message: str) -> str:
        """Mock response - koi API key nahi lagi to yeh use hota hai"""
        if "metric" in message.lower() or "cpu" in message.lower():
            return (
                "MOCK ANALYSIS: CPU usage has spiked to ~85% over the last 15 minutes. "
                "Memory usage is elevated at 78%. HTTP error rate increased to 12% "
                "suggesting the service is struggling under load. "
                "The spike pattern indicates a sudden traffic increase or memory leak."
            )
        elif "log" in message.lower():
            return (
                "MOCK ANALYSIS: Logs show database connection pool exhaustion followed by "
                "OOM Kill events. Multiple 'runtime: out of memory' errors detected. "
                "Pod has restarted 3 times in the last 30 minutes. "
                "Readiness probe failures indicate service instability."
            )
        elif "trace" in message.lower():
            return (
                "MOCK ANALYSIS: Trace data shows significant latency increase. "
                "P99 latency jumped from 45ms to 30+ seconds. "
                "Database query spans are timing out, causing cascade failures "
                "across the checkout and product listing endpoints."
            )
        else:
            return (
                "MOCK ANALYSIS: Based on available evidence, the service is experiencing "
                "resource exhaustion. Root cause appears to be memory leak combined with "
                "database connection saturation."
            )


# Backward compatibility - pehle ClaudeService tha
class ClaudeService(LLMService):
    pass