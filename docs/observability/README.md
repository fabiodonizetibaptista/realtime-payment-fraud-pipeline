# Consultas da Metrics API

Modelos usados no J5 do roteiro de execução. Copie para `.local/`, substitua os marcadores e consulte com `curl.exe -K .local/metrics.curlrc` (credencial da service account `desafio-metrics`, papel `MetricsViewer`; nunca na linha de comando).

| Marcador | Valor |
|---|---|
| `__KAFKA_ID__` | `terraform -chdir=infra/terraform output -raw kafka_cluster_id` |
| `__START_UTC__` | Início da janela faturável, ISO-8601 UTC (ex.: `2026-11-12T13:00:00Z`) |
| `__END_UTC__` | Agora menos 5 minutos, por causa da latência de ingestão das métricas |

```powershell
$k = terraform -chdir=infra/terraform output -raw kafka_cluster_id
$s = "2026-11-12T13:00:00Z"
$e = (Get-Date).ToUniversalTime().AddMinutes(-5).ToString("yyyy-MM-ddTHH:mm:00Z")
foreach ($q in "q-received-bytes", "q-consumer-lag") {
  (Get-Content "docs/observability/$q.json" -Raw).Replace("__KAFKA_ID__", $k).Replace("__START_UTC__", $s).Replace("__END_UTC__", $e) |
    Set-Content ".local/$q.json" -Encoding ascii
}
curl.exe -s -K .local/metrics.curlrc -H "Content-Type: application/json" -d "@.local/q-received-bytes.json" https://api.telemetry.confluent.cloud/v2/metrics/cloud/query
```

Resposta vazia não prova ausência de tráfego: repita a cada 10 minutos e registre como limitação somente após 3 tentativas.
