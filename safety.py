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
    "PRODUCER_KAFKA_API_KEY",
    "PRODUCER_KAFKA_API_SECRET",
    "CONSUMER_KAFKA_API_KEY",
    "CONSUMER_KAFKA_API_SECRET",
    "TF_VAR_foundation_kafka_api_key",
    "TF_VAR_foundation_kafka_api_secret",
    "TF_VAR_foundation_schema_registry_api_key",
    "TF_VAR_foundation_schema_registry_api_secret",
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
    """Reconhece nomes de variaveis mesmo quando o Windows os normaliza.

    O Windows nao diferencia maiusculas/minusculas no ambiente; ao copiar
    os.environ para dict, as chaves podem aparecer em maiusculas.
    """
    normalized = {key.casefold(): value for key, value in values.items()}
    return tuple(
        value
        for key in SECRET_ENV_KEYS
        if len(value := normalized.get(key.casefold(), "")) >= 4
    )


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
    plan: Mapping[str, object], allow: Iterable[str],
    allow_destroy: Iterable[str] = (),
) -> list[str]:
    """Valida enderecos e acoes sem autorizar recursos por prefixo parcial."""

    create_addresses = frozenset(allow)
    destroy_addresses = frozenset(allow_destroy)

    def authorized(address: str, allowed: frozenset[str]) -> bool:
        # Aceita o recurso exato ou instancias de count/for_each.
        # Impede que "resource.foo" autorize "resource.foo_extra".
        return any(
            address == item or address.startswith(item + "[")
            for item in allowed
        )

    rejected = []
    accepted = []

    for item in changed_resources(plan):
        address = str(item.get("address", ""))
        actions = item.get("change", {}).get("actions", [])

        # Substituicoes tambem incluem delete e exigem autorizacao
        # explicita de destruicao.
        if actions in (["create"], ["update"]):
            allowed = authorized(address, create_addresses)
        elif actions == ["delete"]:
            allowed = authorized(address, destroy_addresses)
        elif actions in (["delete", "create"], ["create", "delete"]):
            allowed = (
                authorized(address, create_addresses)
                and authorized(address, destroy_addresses)
            )
        else:
            allowed = False

        if not address or not allowed:
            rejected.append(f"{'+'.join(map(str, actions))} {address}".strip())
        else:
            accepted.append(address)

    if rejected:
        raise ValueError(
            "APPLY bloqueado; mudancas fora da allow-list: "
            + "; ".join(rejected)
        )

    return accepted


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


EVIDENCE_RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


RUN_ID_FILE = Path(".local") / "evidence_run_id"


def saved_run_id(root: Path) -> str:
    """EVIDENCE_RUN_ID gravado no J0.2, ou vazio."""
    path = root / RUN_ID_FILE
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    return value if EVIDENCE_RUN_ID_PATTERN.fullmatch(value) else ""


def evidence_path(root: Path, relative: str, environment: Mapping[str, str] | None = None) -> Path:
    """Resolve o destino de uma evidencia, isolando cada execucao.

    Sem EVIDENCE_RUN_ID, preserva o caminho historico em evidencias/.
    Com EVIDENCE_RUN_ID, grava em evidencias/runs/<RUN_ID>/, sem tocar
    nas evidencias de execucoes anteriores.
    """
    import os

    source = os.environ if environment is None else environment
    run_id = source.get("EVIDENCE_RUN_ID", "").strip()
    if not run_id and environment is None:
        # Terminal perdido (queda, Codespace reiniciado): o J0.2 grava o id
        # em .local/evidence_run_id para as evidencias nao mudarem de pasta.
        run_id = saved_run_id(root)
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError("EVIDENCE_PATH_INVALID")
    if not run_id:
        return root / "evidencias" / relative_path
    if not EVIDENCE_RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError("EVIDENCE_RUN_ID_INVALID")
    return root / "evidencias" / "runs" / run_id / relative_path


def write_utf8(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def discard_stale_plan(path: Path) -> bool:
    """Remove um plano salvo que sobrou de uma tentativa anterior.

    Um plano que ja existe antes do `plan` nunca foi aplicado (apply bem-
    sucedido ou falho apaga o plano) ou ficou obsoleto; reutiliza-lo e
    proibido e bloquear a nova tentativa travava a reproducao. O novo plano
    passa pelo mesmo gate de revisao.
    """
    if path.exists():
        path.unlink()
        print(f"PREVIOUS_PLAN_DISCARDED={path.name}")
        return True
    return False


def archive_previous(path: Path) -> Path | None:
    """Renomeia o arquivo de uma tentativa anterior em vez de bloquear.

    Mantem o historico (sufixo com data/hora UTC) e libera o nome para a
    nova tentativa do mesmo passo.
    """
    if not path.exists():
        return None
    from datetime import datetime, timezone

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = path.with_name(f"{path.stem}.previous-{stamp}{path.suffix}")
    path.rename(target)
    print(f"PREVIOUS_ATTEMPT_ARCHIVED={target.name}")
    return target
