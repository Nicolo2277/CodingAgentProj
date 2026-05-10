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

# Verify bugs config settings
_TEST_TIMEOUT_SEC = 10
_OUTPUT_TRUNCATE  = 1_500  # chars fed back into the interpretation prompt

#Verifier settings
# Retry re-analysis when confirmation_rate is below this threshold.
# Set to 0.0 to disable retries entirely.
VERIFIER_MIN_SCORE: float = 0.5
# Maximum retry attempts per file (initial analysis does not count).
MAX_RETRIES: int = 2


#Tools config settings
_RUN_TIMEOUT_SEC  = 15
_OUTPUT_TRUNCATE  = 2_000  # chars — keep prompts lean

