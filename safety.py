"""Funcoes pequenas de seguranca e execucao compartilhadas pelo bootstrap."""

import re
import subprocess
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping, Sequence

SECRET_ENV_KEYS = (
    "AIVEN_TOKEN",
    "CONFLUENT_CLOUD_API_KEY",
    "CONFLUENT_CLOUD_API_SECRET",
    "KAFKA_API_KEY",
    "TF_VAR_cdc_database_password",
    "TF_VAR_cdc_database_sslrootcert",
    "KAFKA_API_SECRET",
    "SCHEMA_REGISTRY_API_KEY",
    "SCHEMA_REGISTRY_API_SECRET",
)


def load_env_file(path: Path) -> dict[str, str]:
    """Le KEY=VALUE sem expansao de shell e sem exibir valores."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Linha {line_number} invalida no arquivo de ambiente.")
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError(f"Nome de variavel invalido na linha {line_number}.")
        if key in values:
            raise ValueError(f"Variavel duplicada na linha {line_number}: {key}.")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def merge_env_file(path: Path, environment: MutableMapping[str, str]) -> None:
    """Aplica somente valores nao vazios e nunca substitui o ambiente existente."""
    for key, value in load_env_file(path).items():
        if value and key not in environment:
            environment[key] = value


def secret_values(values: Mapping[str, str]) -> tuple[str, ...]:
    return tuple(values[key] for key in SECRET_ENV_KEYS if len(values.get(key, "")) >= 4)


def redact_exact_secrets(text: str, secrets: Iterable[str]) -> str:
    """Redige apenas valores exatos; preserva o contexto do erro."""
    for secret in secrets:
        if secret and len(secret) >= 4:
            text = text.replace(secret, "<redigido>")
    return text


def run_command(
    args: Sequence[str], *, cwd: Path,
    env: Mapping[str, str] | None = None, secrets: Iterable[str] = (),
) -> str:
    """stderr nao e falha quando o exit code e zero; nunca usa shell."""
    try:
        result = subprocess.run(
            list(args), cwd=cwd, env=dict(env) if env is not None else None,
            text=True, encoding="utf-8", errors="replace", capture_output=True, check=False,
        )
    except FileNotFoundError:
        executable = Path(args[0]).stem.lower() if args else ""
        messages = {
            "terraform": "Terraform não encontrado no PATH; veja o README.",
            "confluent": "Confluent CLI não encontrado no PATH; veja o README.",
        }
        if executable in messages:
            raise RuntimeError(messages[executable]) from None
        raise RuntimeError(f"Executavel nao encontrado no PATH: {executable or 'desconhecido'}.") from None
    output = redact_exact_secrets(result.stdout + result.stderr, secrets)
    if result.returncode:
        command = redact_exact_secrets(" ".join(args[:2]), secrets)
        raise RuntimeError(f"Comando falhou ({result.returncode}): {command}\n{output}")
    return output


def changed_resources(plan: Mapping[str, object]) -> list[Mapping[str, object]]:
    changes = plan.get("resource_changes", [])
    if not isinstance(changes, list):
        raise ValueError("Formato inesperado em resource_changes.")
    return [item for item in changes if isinstance(item, dict)
            and item.get("change", {}).get("actions") not in (["no-op"], ["read"])]


def validate_apply_allowlist(
    plan: Mapping[str, object], allow: Iterable[str], allow_destroy: Iterable[str] = (),
) -> list[str]:
    """Destruicoes exigem prefixos separados das criacoes/alteracoes."""
    create_prefixes, destroy_prefixes = tuple(allow), tuple(allow_destroy)
    rejected = []
    for item in changed_resources(plan):
        address = str(item.get("address", ""))
        actions = item.get("change", {}).get("actions", [])
        prefixes = destroy_prefixes if "delete" in actions else create_prefixes
        if not address or not any(address.startswith(prefix) for prefix in prefixes):
            rejected.append(f"{'+'.join(actions)} {address}".strip())
    if rejected:
        raise ValueError("APPLY bloqueado; mudancas fora da allow-list: " + "; ".join(rejected))
    return [str(item.get("address", "")) for item in changed_resources(plan)]


def run_with_teardown(work, teardown):
    """Sempre tenta teardown e preserva a excecao principal."""
    primary_error = None
    try:
        return work()
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            teardown()
        except BaseException as cleanup_error:
            if primary_error is None:
                raise
            primary_error.add_note("Teardown tambem falhou: " + type(cleanup_error).__name__)


def write_utf8(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
