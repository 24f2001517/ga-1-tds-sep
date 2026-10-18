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


def as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "on"}


def normalize_key(key):
    key = key.strip().lower()
    aliases = {
        "app_port": "port",
        "num_workers": "workers",
        "app_debug": "debug",
        "app_log_level": "log_level",
        "app_api_key": "api_key",
    }
    return aliases.get(key, key)


def normalize_value(key, value):
    if key in {"port", "workers"}:
        return int(value)
    if key == "debug":
        return as_bool(value)
    return str(value)


def load_config():
    config = DEFAULTS.copy()

    # Layer 2: environment-specific YAML
    environment = os.getenv("APP_ENV", "development")
    yaml_path = BASE_DIR / f"config.{environment}.yaml"
    if yaml_path.exists():
        with yaml_path.open("r", encoding="utf-8") as file:
            yaml_config = yaml.safe_load(file) or {}
        for key, value in yaml_config.items():
            normalized = normalize_key(key)
            if normalized in DEFAULTS:
                config[normalized] = value

    # Layer 3: .env file
    env_file = dotenv_values(BASE_DIR / ".env")
    for key, value in env_file.items():
        if value is not None:
            normalized = normalize_key(key)
            if normalized in DEFAULTS:
                config[normalized] = value

    # Layer 4: OS environment variables with APP_ prefix
    for key, value in os.environ.items():
        if key.startswith("APP_"):
            normalized = normalize_key(key)
            if normalized in DEFAULTS:
                config[normalized] = value

    # Coerce after all config layers are merged.
    for key in DEFAULTS:
        config[key] = normalize_value(key, config[key])

    return config


@app.get("/")
def root():
    return {"message": "Effective Configuration API is running"}


@app.get("/effective-config")
def effective_config(set: list[str] | None = Query(default=None)):
    config = load_config()

    # Request-local CLI overrides: never persist between requests.
    for item in set or []:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = normalize_key(key)
        if key in DEFAULTS:
            config[key] = normalize_value(key, value)

    # Never expose the actual API key.
    config["api_key"] = "****"
    return config
