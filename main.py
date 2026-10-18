import os
from pathlib import Path

import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

app = FastAPI(title="Effective Configuration API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def normalize_key(key: str) -> str:
    key = key.strip().lower()
    aliases = {
        "app_port": "port",
        "num_workers": "workers",
        "app_workers": "workers",
        "app_debug": "debug",
        "app_log_level": "log_level",
        "app_api_key": "api_key",
    }
    return aliases.get(key, key)


def normalize_value(key, value):
    if key in {"port", "workers"}:
        return int(value)
    if key == "debug":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"true", "1", "yes", "on"}
    return str(value)


def load_config():
    config = DEFAULTS.copy()

    # 1. Environment-specific YAML
    environment = os.getenv("APP_ENV", "development")
    yaml_path = BASE_DIR / f"config.{environment}.yaml"
    if yaml_path.exists():
        with yaml_path.open("r", encoding="utf-8") as file:
            yaml_values = yaml.safe_load(file) or {}
        for key, value in yaml_values.items():
            key = normalize_key(key)
            if key in DEFAULTS:
                config[key] = value

    # 2. .env file; NUM_WORKERS is intentionally aliased to workers.
    env_path = BASE_DIR / ".env"
    env_values = dotenv_values(env_path) if env_path.exists() else {}
    for key, value in env_values.items():
        if value is None:
            continue
        key = normalize_key(key)
        if key in DEFAULTS:
            config[key] = value

    # 3. OS environment variables prefixed APP_.
    for key, value in os.environ.items():
        if key.startswith("APP_"):
            key = normalize_key(key)
            if key in DEFAULTS:
                config[key] = value

    # Coerce values after merging.
    for key in DEFAULTS:
        config[key] = normalize_value(key, config[key])

    return config


@app.get("/")
def root():
    return {"message": "Effective Configuration API is running"}


@app.get("/effective-config")
def effective_config(set: list[str] | None = Query(default=None)):
    config = load_config()

    # 4. CLI query overrides: highest precedence, scoped to this request.
    for item in set or []:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = normalize_key(key)
        if key in DEFAULTS:
            config[key] = normalize_value(key, value)

    # Mask secret after all layers and overrides.
    config["api_key"] = "****"
    return config
