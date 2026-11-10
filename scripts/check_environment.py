"""Preflight portavel e somente leitura, sem imprimir segredos ou executar nuvem.

Uso: python -m scripts.check_environment
Este script nao instala programas, nao faz login e nao le conteudo de .env.
"""

import importlib.metadata
import json
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIN_PYTHON = (3, 12, 0)
MIN_TERRAFORM = (1, 16, 0)
MIN_CONFLUENT = (4, 81, 0)
REQUIRED_PACKAGES = ("pg8000", "confluent-kafka")


def parse_version(raw: str) -> tuple[int, int, int] | None:
    match = re.search(r"(?<!\d)(\d+)\.(\d+)\.(\d+)", raw)
    return tuple(map(int, match.groups())) if match else None


def tool_version(command: str, args: list[str], json_field: str | None = None) -> tuple[int, int, int] | None:
    if shutil.which(command) is None:
        return None
    try:
        result = subprocess.run(
            [command, *args], capture_output=True, text=True,
            check=False, timeout=15, shell=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    if json_field:
        try:
            value = json.loads(result.stdout).get(json_field, "")
        except (ValueError, TypeError, AttributeError):
            return None
        return parse_version(str(value))
    return parse_version(result.stdout + "\n" + result.stderr)


def check_status(found: tuple[int, int, int] | None, minimum: tuple[int, int, int]) -> str:
    if found is None:
        return "MISSING_OR_UNAVAILABLE"
    return "OK" if found >= minimum else "BELOW_MINIMUM"


def report() -> int:
    system = platform.system()
    print("=== LOCAL ENVIRONMENT CHECK (READ ONLY) ===")
    print(f"OS={system}")
    print("SUPPORTED_OS=" + str(system in {"Windows", "Linux", "Darwin"}))

    python_version = sys.version_info[:3]
    terraform_version = tool_version("terraform", ["version", "-json"], "terraform_version")
    confluent_version = tool_version("confluent", ["version"])
    statuses = {
        "PYTHON": check_status(python_version, MIN_PYTHON),
        "TERRAFORM": check_status(terraform_version, MIN_TERRAFORM),
        "CONFLUENT_CLI": check_status(confluent_version, MIN_CONFLUENT),
    }
    for key, status in statuses.items():
        print(f"{key}_STATUS={status}")

    for package in REQUIRED_PACKAGES:
        try:
            importlib.metadata.version(package)
            present = True
        except importlib.metadata.PackageNotFoundError:
            present = False
        print(f"PACKAGE_{package.replace('-', '_').upper()}_PRESENT={present}")
        if not present:
            statuses[f"PACKAGE_{package}"] = "MISSING"

    print("ENV_TEMPLATE_PRESENT=" + str((ROOT / ".env.example").is_file()))
    print("ENV_FILE_PRESENT=" + str((ROOT / ".env").is_file()))
    print("CREDENTIAL_VALUES_PRINTED=False")
    print("CLOUD_CALLS=False")
    print("INSTALLATION_PERFORMED=False")
    print("READY=" + str(
        system in {"Windows", "Linux", "Darwin"}
        and all(status == "OK" for status in statuses.values())
    ))
    return 0 if system in {"Windows", "Linux", "Darwin"} and all(status == "OK" for status in statuses.values()) else 1


if __name__ == "__main__":
    raise SystemExit(report())
