import json
from pathlib import Path

from app.schemas.service_policy import ServicePolicy

POLICY_PATH = Path(__file__).resolve().parents[2] / "data" / "service_policy.json"


def get_service_policy() -> ServicePolicy:
    if not POLICY_PATH.exists():
        return ServicePolicy()
    try:
        return ServicePolicy.model_validate(json.loads(POLICY_PATH.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValueError):
        return ServicePolicy()


def update_service_policy(policy: ServicePolicy) -> ServicePolicy:
    POLICY_PATH.parent.mkdir(parents=True, exist_ok=True)
    POLICY_PATH.write_text(json.dumps(policy.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return policy


def keyword_matches(message: str, keywords: str) -> bool:
    return any(keyword.strip() and keyword.strip().lower() in message.lower() for keyword in keywords.split(","))
