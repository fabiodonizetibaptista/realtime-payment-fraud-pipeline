"""Coleta evidencia da Metrics API da Confluent (Etapa 13).

Usa a identidade somente leitura `desafio-metrics` (MetricsViewer), criada pelo
Terraform (metrics-identity.tf). A chave e lida do `terraform output` apenas em
memoria: nao vai para linha de comando, arquivo ou tela.

Consultas: os modelos versionados em docs/observability/ (received_bytes e
consumer_lag_offsets), filtrados pelo cluster do State, granularidade PT1M.
O fim do intervalo e agora - 5 min por causa da latencia de ingestao.

Uso:
  python scripts/collect_metrics_evidence.py --start 2026-11-12T01:57:00Z

Resposta vazia nao prova ausencia de trafego: repita apos ~10 min.
"""

import argparse
import base64
import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from safety import evidence_path  # noqa: E402

TF_DIR = ROOT / "infra" / "terraform"
TEMPLATES = ROOT / "docs" / "observability"
ENDPOINT = "https://api.telemetry.confluent.cloud/v2/metrics/cloud/query"
QUERIES = {"received_bytes": "q-received-bytes.json", "consumer_lag_offsets": "q-consumer-lag.json"}


def terraform_outputs() -> dict:
    result = subprocess.run(
        ["terraform", "output", "-json"], cwd=TF_DIR, capture_output=True,
        text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("TERRAFORM_OUTPUT_UNAVAILABLE")
    outputs = json.loads(result.stdout)
    values = {key: (outputs.get(key) or {}).get("value") for key in (
        "kafka_cluster_id", "metrics_api_key_id", "metrics_api_key_secret",
    )}
    if not all(values.values()):
        raise RuntimeError("METRICS_IDENTITY_NOT_IN_STATE")
    return values


def parse_utc(text: str) -> datetime:
    value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("START_MUST_BE_UTC")
    return value.astimezone(timezone.utc)


def build_query(template: str, kafka_id: str, start: datetime, end: datetime) -> dict:
    fmt = "%Y-%m-%dT%H:%M:00Z"
    body = (template.replace("__KAFKA_ID__", kafka_id)
            .replace("__START_UTC__", start.strftime(fmt))
            .replace("__END_UTC__", end.strftime(fmt)))
    return json.loads(body)


def post(body: dict, key: str, secret: str) -> dict:
    request = urllib.request.Request(
        ENDPOINT, data=json.dumps(body).encode(), method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Basic " + base64.b64encode(f"{key}:{secret}".encode()).decode(),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as reply:
            return json.load(reply)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"METRICS_API_HTTP_{error.code}") from None
    except urllib.error.URLError:
        raise RuntimeError("METRICS_API_NETWORK") from None


def summarize(metric: str, response: dict) -> dict:
    """Somente timestamps, valores numericos e o nome do grupo (sem credenciais)."""
    data = response.get("data") or []
    values = [float(point.get("value", 0)) for point in data]
    summary = {"metric": f"io.confluent.kafka.server/{metric}", "points": len(data)}
    if metric == "received_bytes":
        summary.update({
            "total_bytes": sum(values),
            "peak_bytes_per_minute": max(values, default=0),
            "series": [{"t": p.get("timestamp"), "bytes": p.get("value")} for p in data],
        })
    else:
        groups = {}
        for point in data:
            group = str(point.get("metric.consumer_group_id") or "?")
            groups.setdefault(group, []).append(float(point.get("value", 0)))
        summary["groups"] = {g: {"points": len(v), "max_lag": max(v)} for g, v in sorted(groups.items())}
    summary["status"] = "COM_DADOS" if data else "SEM_DADOS"
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", required=True, help="inicio da janela, ISO-8601 UTC (ex.: 2026-11-12T01:57:00Z)")
    args = parser.parse_args()

    start = parse_utc(args.start)
    end = (datetime.now(timezone.utc) - timedelta(minutes=5)).replace(second=0, microsecond=0)
    if end <= start:
        print("METRICS_BLOCKED=WINDOW_TOO_RECENT; aguarde 5 min apos o inicio")
        return 1

    outputs = terraform_outputs()
    results = {}
    for metric, template_name in QUERIES.items():
        template = (TEMPLATES / template_name).read_text(encoding="utf-8")
        body = build_query(template, outputs["kafka_cluster_id"], start, end)
        results[metric] = summarize(metric, post(body, outputs["metrics_api_key_id"], outputs["metrics_api_key_secret"]))
        print(f"{metric.upper()}_POINTS={results[metric]['points']}")

    record = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "interval": f"{start.strftime('%Y-%m-%dT%H:%M:00Z')}/{end.strftime('%Y-%m-%dT%H:%M:00Z')}",
        "granularity": "PT1M",
        "identity": "desafio-metrics (MetricsViewer)",
        **results,
        "credentials_recorded": False,
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = evidence_path(ROOT, f"observability/metrics-api-{stamp}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"EVIDENCE_FILE={path.relative_to(ROOT).as_posix()}")
    if results["received_bytes"]["points"] == 0:
        print("METRICS_STATUS=SEM_DADOS; repita em ~10 min (latencia de ingestao)")
        return 2
    print("METRICS_STATUS=COM_DADOS; CREDENTIALS_PRINTED=False")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError) as error:
        print(f"METRICS_ERROR={error}")
        raise SystemExit(1)
