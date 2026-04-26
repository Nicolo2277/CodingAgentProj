DEFAULT_MODEL = "qwen2.5-coder:3b"
DEFAULT_PROVIDER = "ollama"
OLLAMA_BASE_URL= "http://localhost:11434"

OUTPUT_DIR = "Output_results"

MODELS = {
    "ollama":    "qwen2.5-coder:3b",
    "openai":    "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
}

EXCLUDED_DIRS = {".venv", "__pycache__", ".git", "node_modules", ".mypy_cache", ".pytest_cache"}

LOG_LEVEL = "DEBUG"
LOG_DIR = "logs/"