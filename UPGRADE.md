# memL 升级与回滚指南（v0.2）

> 适用于从 v0.1.x 升级到 v0.2.x。

## 1) 升级前备份

```bash
TS=$(date +%Y%m%d-%H%M%S)
cp -a /opt/memL /opt/memL.bak.$TS
```

## 2) 同步代码（推荐 rsync）

```bash
rsync -az --delete /path/to/memL/ /opt/memL/
```

## 3) 关键：修复权限（避免 Chroma 启动失败）

```bash
chown -R meml:meml /opt/memL
mkdir -p /opt/memL/data/chromadb
chown -R meml:meml /opt/memL/data
```

## 4) 更新 v0.2 新增配置

在 `/opt/memL/.env` 增加：

```env
MEML_ADMIN_TOKEN=<strong_admin_token>
MEML_DEDUP_ENABLED=true
MEML_DEDUP_THRESHOLD=0.92
MEML_HYBRID_ALPHA=0.7
```

## 5) 重启并验证

```bash
systemctl daemon-reload
systemctl restart memL
systemctl is-active memL

curl http://127.0.0.1:8000/health/live
curl http://127.0.0.1:8000/metrics
curl -H "Authorization: Bearer <MEML_ADMIN_TOKEN>" http://127.0.0.1:8000/admin/tenants
```

---

## 常见故障

### 报错：`chromadb.errors.InternalError: Permission denied (os error 13)`

根因：`/opt/memL` 或 `/opt/memL/data` 非 `meml` 用户可写。

修复：

```bash
chown -R meml:meml /opt/memL /opt/memL/data
systemctl restart memL
```

---

## 回滚（快速）

```bash
LATEST=$(ls -dt /opt/memL.bak.* | head -n1)
rm -rf /opt/memL
cp -a "$LATEST" /opt/memL
chown -R meml:meml /opt/memL
systemctl restart memL
```

验证：

```bash
curl http://127.0.0.1:8000/health/live
```
