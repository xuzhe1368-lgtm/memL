# memL 灾备演练 Runbook（v0.3 M1）

## 目标
验证 tenant 级数据可导出、可导入、可恢复。

## 前置
- 服务运行中
- 已知 tenant collection 名（如 personal/work/shared）

## 演练步骤

### 1) 导出 tenant
```bash
python3 scripts/export_tenant.py \
  --data-dir /opt/memL/data/chromadb \
  --collection personal \
  --out /opt/memL/backups/personal-$(date +%Y%m%d-%H%M%S).jsonl
```

### 2) 记录基线数量
```bash
curl -H "Authorization: Bearer <TOKEN>" http://127.0.0.1:8000/stats
```

### 3) 导入到临时 collection 验证
```bash
python3 scripts/import_tenant.py \
  --data-dir /opt/memL/data/chromadb \
  --collection personal_restore_test \
  --in /opt/memL/backups/personal-*.jsonl
```

### 4) 验证恢复可读
- 切换测试 token 指向 `personal_restore_test` 后做查询
- 或使用 Chroma collection 计数检查

### 5) 清理
- 删除临时 collection 或保留用于回归

## 验收标准
- 导出文件可读且记录数 > 0
- 导入完成后记录数与基线一致（允许少量时间窗差异）
- 基本检索可返回结果
