# memL 稳定性巡检（Daily/24h）

## 目标
每天自动产出一份可审计的稳定性报告，覆盖健康、指标、日志、备份状态。

## 脚本
- `scripts/ops_daily_check.sh`

## 运行示例
```bash
chmod +x scripts/ops_daily_check.sh
sudo ./scripts/ops_daily_check.sh http://127.0.0.1:8000 /opt/memL/reports
```

输出示例：
- `/opt/memL/reports/meml-24h-YYYYmmdd-HHMMSS.txt`

## 建议观察项
- `meml_embedding_fail_total` 是否持续上升
- `meml_pending_queue_size` 是否长期 > 0 或 > 20
- `systemctl status memL` 是否出现重启震荡
- 备份文件是否持续新增且有 checksum

## 异常分级
- P0: 服务不可用（health 失败）
- P1: embedding 连续失败、队列持续积压
- P2: 单次失败可自动恢复
