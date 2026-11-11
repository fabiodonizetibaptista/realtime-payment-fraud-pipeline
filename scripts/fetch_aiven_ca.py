"""Recupera a CA do projeto Aiven para uso pelo conector CDC V2.

Somente leitura na API Aiven.
Nunca imprime token, certificado ou resposta bruta da API.
"""

import argparse
import json
import re
import os
import ssl
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from safety import load_env_file

TARGET = ROOT / ".local" / "aiven-ca.pem"


def main():
    env = load_env_file(ROOT / ".env")
    # An explicit environment variable wins over the local .env file.
    token = os.environ.get("AIVEN_TOKEN") or env.get("AIVEN_TOKEN")
    project = os.environ.get("TF_VAR_aiven_project") or env.get("TF_VAR_aiven_project")

    print("========== ETAPA 4 — CERTIFICADO AIVEN ==========")
    print("AIVEN_TOKEN_AVAILABLE=", bool(token))

    if not token or not project:
        print("MISSING_KEYS=" + ",".join(
            key for key, value in (("AIVEN_TOKEN", token), ("TF_VAR_aiven_project", project))
            if not value
        ))
        print("CA_GATE=BLOCKED")
        return 1
    # Reject unexpected URL path characters instead of constructing a request
    # to a different endpoint from an untrusted configuration value.
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*", project):
        print("INVALID_PROJECT_NAME=True")
        print("CA_GATE=BLOCKED")
        return 1

    request = urllib.request.Request(
        f"https://api.aiven.io/v1/project/{project}/kms/ca",
        headers={
            "Authorization": f"aivenv1 {token}",
            "Accept": "application/json",
        },
    )

    # Consulta somente GET: nenhuma alteração remota.
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)

    certificate = data.get("certificate", "")

    if not isinstance(certificate, str):
        raise ValueError("INVALID_CERTIFICATE_TYPE")

    certificate = certificate.strip() + "\n"

    if (
        not certificate.startswith("-----BEGIN CERTIFICATE-----")
        or "-----END CERTIFICATE-----" not in certificate
    ):
        raise ValueError("INVALID_PEM_FORMAT")

    # Confirma que o conteúdo é um certificado X.509 válido.
    ssl.PEM_cert_to_DER_cert(certificate)

    # Impede versionamento acidental do diretório operacional.
    exclude = ROOT / ".git" / "info" / "exclude"

    if not exclude.is_file():
        raise RuntimeError("GIT_EXCLUDE_NOT_FOUND")

    current = exclude.read_text(encoding="utf-8")

    if "/.local/" not in current.splitlines():
        with exclude.open("a", encoding="utf-8") as file:
            file.write("\n/.local/\n")

    TARGET.parent.mkdir(parents=True, exist_ok=True)

    temp = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=TARGET.parent,
            prefix=".aiven-ca-",
            delete=False,
        ) as file:
            temp = Path(file.name)
            # fchmod is not provided on Windows; use POSIX permissions only
            # where supported. Windows inherits the directory's ACL.
            if os.name == "posix":
                os.fchmod(file.fileno(), 0o600)
            file.write(certificate)

        os.replace(temp, TARGET)

    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)

    print("CA_RETRIEVED=True")
    print("PEM_FORMAT_VALID=True")
    print("CERTIFICATE_STORED_LOCALLY=True")
    print("GIT_EXCLUDED=True")
    print("CERTIFICATE_CONTENT_PRINTED=False")
    print("TOKEN_PRINTED=False")
    print("REMOTE_CHANGES=False")
    print("CA_GATE=PASS")

    return 0


def cli(argv=None):
    """Processa --help antes de carregar credenciais ou acessar a API."""
    parser = argparse.ArgumentParser(
        description="Recupera o certificado CA do projeto Aiven configurado localmente."
    )
    parser.parse_args(argv)
    return main()


if __name__ == "__main__":
    try:
        raise SystemExit(cli())
    except Exception as error:
        print("ERROR_TYPE=", type(error).__name__)
        print("CA_GATE=BLOCKED")
        raise SystemExit(1)
