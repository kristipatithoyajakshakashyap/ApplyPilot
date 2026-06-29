"""Unified LLM client — OpenAI-compatible for openai / featherless / ollama."""
import os
import requests
from openai import OpenAI

_TIMEOUT = 90


def _provider() -> str:
    return os.getenv("LLM_PROVIDER", "openai").lower()


def _check_ollama(base: str, model: str) -> None:
    """Raise a clear error if Ollama is not reachable or the model is not pulled."""
    try:
        resp = requests.get(f"{base}/api/tags", timeout=5)
        resp.raise_for_status()
        available = [m["name"] for m in resp.json().get("models", [])]
        model_base = model.split(":")[0]
        found = any(m == model or m.startswith(model_base + ":") for m in available)
        if available and not found:
            raise RuntimeError(
                f"Ollama model '{model}' is not pulled.\n"
                f"Available models: {', '.join(available)}\n"
                f"Run: ollama pull {model}\n"
                f"Or update OLLAMA_MODEL in .env"
            )
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"Cannot connect to Ollama at '{base}'.\n"
            f"Make sure Ollama is running: ollama serve\n"
            f"Check OLLAMA_BASE_URL in .env (currently: {base})"
        )
    except requests.exceptions.Timeout:
        raise RuntimeError(
            f"Ollama health check timed out at '{base}'.\n"
            f"Check OLLAMA_BASE_URL in .env (currently: {base})"
        )


def _make_client() -> tuple:
    p = _provider()
    if p == "ollama":
        base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        _check_ollama(base, model)
        return OpenAI(base_url=f"{base}/v1", api_key="ollama", timeout=_TIMEOUT), model
    if p == "featherless":
        return (
            OpenAI(base_url="https://api.featherless.ai/v1", api_key=os.getenv("FEATHERLESS_API_KEY", ""), timeout=_TIMEOUT),
            os.getenv("FEATHERLESS_MODEL", "Qwen/Qwen2.5-72B-Instruct"),
        )
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""), timeout=_TIMEOUT), os.getenv("OPENAI_MODEL", "gpt-4o")


def chat(system: str, user: str, temperature: float = 0.2, top_p: float = 1.0) -> str:
    client, model = _make_client()
    p = _provider()
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=temperature,
            top_p=top_p,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        err = str(exc)
        if "model_gated_needs_oauth" in err or "gated" in err.lower():
            raise RuntimeError(
                f"\nModel '{model}' on Featherless is gated (requires HuggingFace OAuth).\n"
                f"Set FEATHERLESS_MODEL in .env to a non-gated model:\n"
                f"  FEATHERLESS_MODEL=Qwen/Qwen2.5-72B-Instruct\n"
                f"  FEATHERLESS_MODEL=mistralai/Mistral-7B-Instruct-v0.2"
            ) from exc
        if "timed out" in err.lower() or "timeout" in err.lower():
            raise RuntimeError(
                f"\nLLM call timed out after {_TIMEOUT}s [{p}/{model}]. Provider may be overloaded."
            ) from exc
        raise RuntimeError(f"LLM call failed [{p}/{model}]: {exc}") from exc
