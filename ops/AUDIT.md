# memL 管理审计日志

## 文件位置
- 默认：`/opt/memL/data/audit.log`
- 可配置：`MEML_AUDIT_LOG_FILE`

## 记录内容
- tenant upsert
- tenant disable

字段：
- `ts`（UTC时间）
- `action`
- `actor`（当前为 admin）
- `detail`（脱敏 token 前缀、tenant 名称、collection 等）

## API 查询

```bash
curl -H "Authorization: Bearer <MEML_ADMIN_TOKEN>" \
  "http://127.0.0.1:8000/admin/audit?limit=50"
```
