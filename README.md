# memL

自建 OpenClaw 云端记忆服务（支持多实例对接、可观测、可治理）。

> 当前推荐版本：`v0.3.3`

---

## 1. 能力概览

memL 现在具备以下核心能力：

- 多 tenant 隔离（按 token -> collection）
- 记忆 CRUD + 语义检索 + 标签过滤
- 混合检索（向量 + 关键词）+ explain 可解释打分
- 时间衰减 + 标签加权排序
- 去重写入（阈值可配）
- 幂等写入（`Idempotency-Key`）
- 异步补算向量（embedding 故障降级写入，恢复后回填）
- tenant 配额与写入限流
- 权限分层（viewer/editor/admin）
- 管理审计日志（`/admin/audit`）
- 可视化控制台（`/ui`）
- Prometheus 指标（`/metrics/prom`）与告警规则模板
- 长短期分仓（short/long 自动路由）+ 统一读取视图
- 灾备工具（备份/恢复、tenant 导出/导入）

---

## 2. 架构说明（v0.3.3）

### 2.1 分仓模型

以 tenant 的 `collection=personal` 为例，系统自动使用：

- `personal_short`：短期记忆（低/中价值）
- `personal_long`：长期记忆（高价值或里程碑）
- `personal`：历史 legacy 数据（兼容旧版本）

写入路由规则：

- `importance_score >= MEML_IMPORTANCE_LONGTERM_THRESHOLD` 或 `promote_to_longterm=true` -> `*_long`
- 否则 -> `*_short`

读取规则：统一聚合 `short + long + legacy`，调用方无需改接口。

### 2.2 标准标签体系

推荐/默认标签三元组：

- `type:*`（例如 `type:project` / `type:test` / `type:ops` / `type:milestone`）
- `source:*`（例如 `source:runtime` / `source:migration`）
- `scope:*`（例如 `scope:personal`）

---

## 3. 快速开始

## 3.1 安装部署

```bash
git clone https://github.com/xuzhe1368-lgtm/memL.git
cd memL
cp .env.example .env
# 编辑 .env 与 tenants.yaml
chmod +x deploy.sh
sudo ./deploy.sh
sudo systemctl start memL
sudo systemctl enable memL
```

### 给“龙虾”用户的一键命令（直接复制）

> 下面这段是给直接在龙虾里看的同学准备的：按顺序复制执行即可。

```bash
# 0) 安装到 /opt/memL
sudo mkdir -p /opt && cd /opt
sudo git clone https://github.com/xuzhe1368-lgtm/memL.git || true
cd /opt/memL

# 1) 生成配置
sudo cp -n .env.example .env
sudo cp -n tenants.yaml tenants.yaml.bak 2>/dev/null || true

# 2) 编辑关键参数（至少改这三项）
# MEML_ADMIN_TOKEN=你自己的强口令
# MEML_EMBED_API_URL=你的 embedding API 地址
# MEML_EMBED_API_KEY=你的 embedding API key
sudo nano /opt/memL/.env

# 3) 部署并启动
sudo chmod +x /opt/memL/deploy.sh
sudo /opt/memL/deploy.sh
sudo systemctl enable --now memL

# 4) 健康检查
curl -sS http://127.0.0.1:8000/health/live
curl -sS http://127.0.0.1:8000/metrics/prom | head
```

# 5) OpenClaw 接入（在本机 ~/.openclaw/openclaw.json 里配置）
# apiUrl 填 memL 地址，apiKey 填 tenants.yaml 对应 token

验证：

```bash
curl http://127.0.0.1:8000/health/live
```

## 3.2 安全同步升级（推荐）

使用安全同步脚本避免误删运行态文件：

```bash
chmod +x scripts/sync_remote.sh
./scripts/sync_remote.sh root@192.168.2.240 /path/to/memL
```

该脚本会排除：`.env`、`venv/`、`data/`、`backups/`。

---

## 4. 配置项（重点）

| 环境变量 | 说明 | 默认值 |
|---|---|---|
| MEML_HOST | 监听地址 | 0.0.0.0 |
| MEML_PORT | 端口 | 8000 |
| MEML_DATA_DIR | Chroma 数据目录 | /opt/memL/data/chromadb |
| MEML_TENANTS_FILE | tenant 映射文件 | /opt/memL/tenants.yaml |
| MEML_ADMIN_TOKEN | 管理接口口令 | - |
| MEML_DEDUP_ENABLED | 是否启用去重 | true |
| MEML_DEDUP_THRESHOLD | 去重阈值 | 0.92 |
| MEML_HYBRID_ALPHA | 混合检索向量权重 | 0.7 |
| MEML_TENANT_MAX_MEMORIES | tenant 总容量上限 | 50000 |
| MEML_TENANT_WRITE_RATE_PER_MIN | tenant 每分钟写入上限 | 120 |
| MEML_QUEUE_FILE | 异步补算队列文件 | /opt/memL/data/pending_writes.jsonl |
| MEML_IDEMP_FILE | 幂等键存储 | /opt/memL/data/idempotency.json |
| MEML_AUDIT_LOG_FILE | 审计日志文件 | /opt/memL/data/audit.log |
| MEML_IMPORTANCE_LONGTERM_THRESHOLD | 长期记忆阈值 | 0.75 |
| MEML_EMBED_API_URL | embedding API 地址 | - |
| MEML_EMBED_API_KEY | embedding API 密钥 | - |
| MEML_EMBED_MODEL | embedding 模型 | BAAI/bge-large-zh-v1.5 |

---

## 5. API（v0.3.3）

认证：`Authorization: Bearer <token>`

### 基础

- `GET /` 服务信息
- `GET /health/live` 存活检查
- `GET /health/ready` 就绪检查
- `GET /stats` 统计（含 short/long/legacy）

### 记忆

- `POST /memory` 创建记忆（支持 `importance_score` / `promote_to_longterm`）
- `GET /memory?q=&tags=&limit=&explain=` 搜索
- `GET /memory/{id}` 获取单条
- `PATCH /memory/{id}` 更新
- `DELETE /memory/{id}` 删除
- `POST /memory/milestone` 里程碑写入（高价值）

### 管理

- `GET /admin/tenants`
- `POST /admin/tenants`
- `POST /admin/tenants/{token}/disable`
- `GET /admin/audit`

### 观测

- `GET /metrics` JSON 指标
- `GET /metrics/prom` Prometheus 文本格式
- `GET /ui` 可视化控制台

---

## 6. 关键调用示例

## 6.1 高价值写入

```bash
curl -X POST http://127.0.0.1:8000/memory \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "text":"我们确定 v0.3.3 后进入治理阶段",
    "tags":["type:project","source:runtime","scope:personal"],
    "importance_score":0.9
  }'
```

## 6.2 里程碑回写

```bash
curl -X POST http://127.0.0.1:8000/memory/milestone \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "project":"memL",
    "stage":"v0.3.3",
    "summary":"分仓与治理闭环完成",
    "next_step":"继续做检索优化"
  }'
```

## 6.3 可解释检索

```bash
curl "http://127.0.0.1:8000/memory?q=治理&limit=5&explain=true" \
  -H "Authorization: Bearer <TOKEN>"
```

## 6.4 幂等写入

```bash
curl -X POST http://127.0.0.1:8000/memory \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Idempotency-Key: my-op-001" \
  -H "Content-Type: application/json" \
  -d '{"text":"同一操作不会重复写","tags":["type:test","source:runtime","scope:personal"]}'
```

---

## 7. OpenClaw 接入

在 `~/.openclaw/openclaw.json` 中配置：

```json
{
  "plugins": {
    "allow": ["meml"],
    "slots": { "memory": "meml" },
    "entries": {
      "meml": {
        "enabled": true,
        "config": {
          "apiUrl": "http://<MEML_HOST>:8000",
          "apiKey": "<YOUR_MEML_API_KEY>",
          "autoInject": true,
          "maxMemories": 10
        }
      }
    }
  }
}
```

---

## 8. 运维与治理

详见：

- `UPGRADE.md`：升级与回滚
- `ops/ALERTING.md`：监控与告警
- `ops/AUDIT.md`：管理审计
- `ops/RBAC.md`：权限分层
- `DR_RUNBOOK.md`：灾备演练

---

## 9. 常见问题

### Q1: 为什么写入返回 `embedding_pending=true`？
表示 embedding 上游暂不可用，系统已降级接收写入并进入异步补算队列。

### Q2: 为什么 viewer token 不能写入？
这是 RBAC 设计：viewer 为只读角色，写入需 editor/admin。

### Q3: 为什么 GitHub Latest 版本不变？
需要创建新 tag/release；仅 push main 不会更新 Latest。
