# Consultas da Metrics API

Modelos versionados das consultas usadas por
[`scripts/collect_metrics_evidence.py`](../../scripts/collect_metrics_evidence.py)
(J4 do [roteiro](../runbook.md)):

| Arquivo | Métrica | Agrupamento |
|---|---|---|
| `q-received-bytes.json` | `io.confluent.kafka.server/received_bytes` | cluster |
| `q-consumer-lag.json` | `io.confluent.kafka.server/consumer_lag_offsets` | `metric.consumer_group_id` |

O coletor substitui os marcadores (`__KAFKA_ID__`, `__START_UTC__`,
`__END_UTC__`) com o cluster do State, o início da janela informado em
`--start` e "agora − 5 min" (latência de ingestão), consulta com a Cloud API key
da identidade `desafio-metrics` (papel `MetricsViewer`, criada pelo Terraform)
lida do State apenas em memória e grava uma evidência sanitizada com data e
hora em `evidencias/.../observability/`.

Resposta vazia não prova ausência de tráfego: repita após ~10 min. O lag por
grupo só existe para consumidores que fazem commit de offsets.
