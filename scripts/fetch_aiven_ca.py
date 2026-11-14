"""Obtém a CA do projeto Aiven e configura PG_CA no .env do clone atual.

Faz apenas GET na API da Aiven. Não imprime token, CA ou conteúdo do .env.
Não reutiliza certificado de outra execução: baixa e substitui o arquivo local.
"""

import argparse
import json
import os
import re
import subprocess
import ssl
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from safety import load_env_file

TARGET = ROOT / ".local" / "aiven-ca.pem"
ENV_FILE = ROOT / ".env"


def _write_atomic(path: Path, content: str, *, secret: bool = False) -> None:
    """Atualiza um arquivo sem deixar conteúdo parcial se a gravação falhar."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}-",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            if os.name == "posix" and secret:
                os.fchmod(handle.fileno(), 0o600)
            handle.write(content)
        os.replace(temporary, path)
        if os.name == "posix" and secret:
            os.chmod(path, 0o600)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _configure_pg_ca(path: Path) -> None:
    """Preserva o .env existente; substitui exclusivamente a chave PG_CA."""
    existing = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    lines = [
        line for line in existing.splitlines()
        if not re.match(r"^\s*(?:export\s+)?PG_CA\s*=", line)
    ]
    # Caminho absoluto da própria reprodução, independente do diretório atual.
    lines.append(f"PG_CA={path.resolve()}")
    _write_atomic(ENV_FILE, "\n".join(lines) + "\n", secret=True)


def _validate_aiven_project_state(configured_project: str) -> str:
    """Confere projeto PostgreSQL do State local; nunca mostra conteudo do State.

    Falha fechado se o Terraform nao estiver acessivel, State estiver ausente,
    ou o recurso nao corresponder ao projeto configurado para a chamada Aiven.
    """
    try:
        result = subprocess.run(
            ["terraform", "show", "-json"],
            cwd=ROOT / "infra" / "terraform",
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env={**os.environ, "TF_LOG": "OFF"},
        )
        if result.returncode != 0:
            return "STATE_UNAVAILABLE"

        state = json.loads(result.stdout)
        resources = state["values"]["root_module"]["resources"]
        matches = [
            item for item in resources
            if item.get("address") == "aiven_pg.payments"
        ]
        if len(matches) != 1:
            return "POSTGRES_RESOURCE_MISSING"

        values = matches[0]["values"]
        state_project = values.get("project")
        if not isinstance(state_project, str) or not state_project:
            return "STATE_PROJECT_MISSING"
        if state_project != configured_project:
            return "PROJECT_MISMATCH"
        return "PASS"
    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError, KeyError, IndexError):
        return "STATE_UNAVAILABLE"


def main() -> int:
    env = load_env_file(ENV_FILE)
    token = os.environ.get("AIVEN_TOKEN") or env.get("AIVEN_TOKEN")
    project = os.environ.get("TF_VAR_aiven_project") or env.get("TF_VAR_aiven_project")

    print("========== CERTIFICADO AIVEN ==========")
    print("AIVEN_TOKEN_AVAILABLE=", bool(token))

    if not token or not project:
        missing = [
            key for key, value in (
                ("AIVEN_TOKEN", token),
                ("TF_VAR_aiven_project", project),
            ) if not value
        ]
        print("MISSING_KEYS=" + ",".join(missing))
        print("CA_GATE=BLOCKED")
        return 1

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*", project):
        print("INVALID_PROJECT_NAME=True")
        print("CA_GATE=BLOCKED")
        return 1

    # Nao consultar a API de outro projeto por heranca de ambiente obsoleta.
    state_gate = _validate_aiven_project_state(project)
    if state_gate != "PASS":
        print("AIVEN_STATE_GATE=" + state_gate)
        print("CA_GATE=BLOCKED")
        return 1

    print("AIVEN_STATE_GATE=PASS")

    request = urllib.request.Request(
        f"https://api.aiven.io/v1/project/{project}/kms/ca",
        headers={
            "Authorization": f"aivenv1 {token}",
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.load(response)
    except urllib.error.HTTPError as error:
        # Evita imprimir resposta bruta, que pode conter detalhes privados.
        print("AIVEN_HTTP_STATUS=", error.code)
        print("CA_GATE=BLOCKED")
        return 1
    except (urllib.error.URLError, TimeoutError):
        print("AIVEN_CONNECTION_FAILED=True")
        print("CA_GATE=BLOCKED")
        return 1

    certificate = data.get("certificate") if isinstance(data, dict) else None
    if not isinstance(certificate, str):
        print("INVALID_CERTIFICATE_TYPE=True")
        print("CA_GATE=BLOCKED")
        return 1

    certificate = certificate.strip() + "\n"
    if (
        not certificate.startswith("-----BEGIN CERTIFICATE-----")
        or "-----END CERTIFICATE-----" not in certificate
    ):
        print("INVALID_PEM_FORMAT=True")
        print("CA_GATE=BLOCKED")
        return 1

    try:
        ssl.PEM_cert_to_DER_cert(certificate)
    except ValueError:
        print("INVALID_X509_CERTIFICATE=True")
        print("CA_GATE=BLOCKED")
        return 1

    # Segura contra commit acidental no repositório do clone.
    exclude = ROOT / ".git" / "info" / "exclude"
    if not exclude.is_file():
        print("GIT_EXCLUDE_NOT_FOUND=True")
        print("CA_GATE=BLOCKED")
        return 1

    current = exclude.read_text(encoding="utf-8")
    excluded = current.splitlines()
    additions = []
    if "/.local/" not in excluded:
        additions.append("/.local/")
    if "/.env" not in excluded:
        additions.append("/.env")
    if additions:
        with exclude.open("a", encoding="utf-8") as handle:
            handle.write("\n" + "\n".join(additions) + "\n")

    # CA sempre vem desta chamada à API, nunca é reutilizado do disco.
    # Salva a CA recem-baixada antes de atualizar a configuracao.
    _write_atomic(TARGET, certificate, secret=True)
    _configure_pg_ca(TARGET)

    print("CA_RETRIEVED=True")
    print("PEM_FORMAT_VALID=True")
    print("CERTIFICATE_STORED_LOCALLY=True")
    print("PG_CA_CONFIGURED=True")
    print("GIT_EXCLUDED=True")
    print("CERTIFICATE_CONTENT_PRINTED=False")
    print("TOKEN_PRINTED=False")
    print("REMOTE_CHANGES=False")
    print("CA_GATE=PASS")
    return 0


def cli(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Baixa a CA do projeto Aiven e configura PG_CA no .env deste clone."
    )
    parser.parse_args(argv)
    return main()


if __name__ == "__main__":
    try:
        raise SystemExit(cli())
    except Exception as error:
        # Não mostrar traceback com dados de rede ou conteúdo privado.
        print("ERROR_TYPE=", type(error).__name__)
        print("CA_GATE=BLOCKED")
        raise SystemExit(1)
