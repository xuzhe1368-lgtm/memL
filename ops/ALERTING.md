# memL 监控与告警（M1）

## 1) Prometheus 抓取

使用 `ops/prometheus.meml.yml`，抓取目标：
- `http://192.168.2.240:8000/metrics/prom`

## 2) 告警规则

使用 `ops/alert.rules.yml`，当前内置：
- `MemLEmbeddingFailuresHigh`：5分钟内 embedding 失败次数 > 5
- `MemLNoWrites`：30分钟无写入（信息性提示）
- `MemLPendingQueueBacklog`：异步补算队列积压 > 20 持续 5 分钟
- `MemLServiceDown`：Prometheus 抓取失败（服务下线）

## 3) 快速验证

```bash
curl http://192.168.2.240:8000/metrics/prom
```

你应能看到：
- `meml_requests_total`
- `meml_memory_writes_total`
- `meml_memory_search_total`
- `meml_dedup_hits_total`
- `meml_embedding_fail_total`

## 4) 建议阈值（个人场景）

- embedding 失败：`> 5 / 5m` 触发 warning
- 服务存活：若 scrape 连续失败 2 次触发 critical（在 Prometheus/Alertmanager 中配置）
