import json
import os
import platform
import shutil
from importlib import metadata

_MODEL_CONFIGURATION_KEYS = (
    "DEEPSEEK_API_KEY",
    "DASHSCOPE_API_KEY",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_BASE_URL",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "HF_TOKEN",
    "HUGGINGFACE_HUB_TOKEN",
)


def _dependency_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def collect_environment() -> dict[str, object]:
    return {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "disk_free_bytes": shutil.disk_usage(".").free,
        "dependencies": {
            name: _dependency_version(name)
            for name in ("GitPython", "networkx", "pydantic", "pytest")
        },
        "model_configuration": {
            name: "present" if os.environ.get(name) else "absent"
            for name in _MODEL_CONFIGURATION_KEYS
        },
    }


def main() -> int:
    print(json.dumps(collect_environment(), ensure_ascii=False, indent=2))
    return 0
