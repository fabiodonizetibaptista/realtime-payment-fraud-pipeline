"""Confere se as credenciais de conta do .env funcionam (J0, somente leitura).

`check_configuration` confere apenas a presenca das variaveis. Na execucao
guiada, uma Cloud API key invalida so apareceu no apply da fundacao (401).
Este script faz uma leitura em cada provedor e imprime apenas OK ou o codigo
HTTP — nunca valores.

- Confluent: GET /org/v2/environments com CONFLUENT_CLOUD_API_KEY/SECRET.
  Uma chave de cluster (Kafka) ou revogada responde 401.
- Aiven: GET /v1/project/<TF_VAR_aiven_project> com AIVEN_TOKEN.
"""

import argparse
import base64
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from safety import load_env_file  # noqa: E402

CONFLUENT_URL = "https://api.confluent.cloud/org/v2/environments?page_size=1"
AIVEN_URL = "https://api.aiven.io/v1/project/{project}"

HINTS = {
    "CONFLUENT": (
        "Crie uma Cloud API key (nao de cluster): "
        "confluent api-key create --resource cloud --description terraform-desafio"
    ),
    "AIVEN": "Gere um token no console da Aiven e confira o nome tecnico do projeto",
}


def http_status(request, opener=urllib.request.urlopen) -> int:
    try:
        with opener(request, timeout=30) as reply:
            return reply.status
    except urllib.error.HTTPError as error:
        return error.code
    except urllib.error.URLError:
        return 0


def confluent_request(key, secret):
    token = base64.b64encode(f"{key}:{secret}".encode()).decode()
    return urllib.request.Request(CONFLUENT_URL, headers={"Authorization": f"Basic {token}"})


def aiven_request(token, project):
    url = AIVEN_URL.format(project=urllib.parse.quote(project, safe=""))
    return urllib.request.Request(url, headers={"Authorization": f"aivenv1 {token}"})


def check(environment, opener=urllib.request.urlopen) -> dict:
    results = {}
    key, secret = environment.get("CONFLUENT_CLOUD_API_KEY"), environment.get("CONFLUENT_CLOUD_API_SECRET")
    results["CONFLUENT"] = http_status(confluent_request(key, secret), opener) if key and secret else None
    token, project = environment.get("AIVEN_TOKEN"), environment.get("TF_VAR_aiven_project")
    results["AIVEN"] = http_status(aiven_request(token, project), opener) if token and project else None
    return results


CREDENTIAL_KEYS = (
    "CONFLUENT_CLOUD_API_KEY", "CONFLUENT_CLOUD_API_SECRET",
    "AIVEN_TOKEN", "TF_VAR_aiven_project",
)


def credential_sources(process, dotenv) -> dict:
    """De onde cada credencial vem; o ambiente do processo tem precedencia.

    Codespaces secrets e variaveis do perfil chegam como ambiente e vencem o
    .env silenciosamente — causa de 401 com uma chave nova no .env.
    """
    sources = {}
    for key in CREDENTIAL_KEYS:
        in_process, in_file = bool(process.get(key)), bool(dotenv.get(key))
        if in_process and in_file and process[key] != dotenv[key]:
            sources[key] = "CONFLICT"
        elif in_process:
            sources[key] = "ENVIRONMENT"
        elif in_file:
            sources[key] = "DOTENV"
        else:
            sources[key] = "MISSING"
    return sources


def main() -> int:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args()
    dotenv = load_env_file(ROOT / ".env") if (ROOT / ".env").is_file() else {}
    process = {k: v for k, v in os.environ.items() if v}
    environment = {**dotenv, **process}
    passed = True
    for key, source in credential_sources(process, dotenv).items():
        print(f"{key}_SOURCE={source}")
        if source == "CONFLICT":
            print(
                f"{key}_NEXT_ACTION=O ambiente (ex.: Codespaces secret ou perfil) "
                "tem outro valor e vence o .env; remova-o do ambiente "
                f"(unset {key}) e apague o secret antigo em github.com/settings/codespaces"
            )
            passed = False
    for provider, status in check(environment).items():
        if status is None:
            print(f"{provider}_CREDENTIALS=MISSING")
            passed = False
        elif status == 200:
            print(f"{provider}_CREDENTIALS=OK")
        else:
            print(f"{provider}_CREDENTIALS=FAILED HTTP={status or 'NETWORK'}")
            print(f"{provider}_NEXT_ACTION={HINTS[provider]}")
            passed = False
    print("CREDENTIAL_VALUES_PRINTED=False")
    print("CREDENTIALS_GATE=" + ("PASS" if passed else "BLOCKED"))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
