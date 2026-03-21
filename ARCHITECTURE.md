# memL — 自建 OpenClaw 云端记忆服务

## 一、项目目标

构建一个**独立协议**的云端记忆服务，实现：

1. **持久化存储** — 记忆存在独立服务，OpenClaw 重装/更换后连接同一个 API key 即恢复
2. **语义检索** — 按意思找记忆，不只是关键词匹配
3. **多实例共享** — 多个 OpenClaw 实例可共享同一个记忆空间
4. **轻量部署** — 单机运行，资源占用低
5. **独立协议** — 不兼容 mem9，设计更简洁高效的 API

---

## 二、系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         OpenClaw 实例们                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ 本地     │  │ VPS-1    │  │ VPS-2    │  │ 笔记本   │        │
│  │ OpenClaw │  │ OpenClaw │  │ OpenClaw │  │ OpenClaw │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
└───────┼─────────────┼─────────────┼─────────────┼───────────────┘
        │             │             │             │
        └─────────────┴──────┬──────┴─────────────┘
                             │ HTTP (REST API)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    memL 服务 (虚拟机)                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    FastAPI 应用                          │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐    │   │
│  │  │ 路由层  │  │ 认证层  │  │ 业务层  │  │ 嵌入层  │    │   │
│  │  │ Routes  │  │ Auth    │  │ Service │  │Embedding│    │   │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘    │   │
│  └───────┼────────────┼────────────┼────────────┼──────────┘   │
│          │            │            │            │              │
│          └────────────┴─────┬──────┴────────────┘              │
│                               ▼                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    ChromaDB (向量数据库)                  │   │
│  │  ┌──────────────┐  ┌──────────────┐                     │   │
│  │  │ 向量索引     │  │ 元数据存储   │                     │   │
│  │  │ (HNSW)       │  │ (SQLite)     │                     │   │
│  │  └──────────────┘  └──────────────┘                     │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │ Embedding API  │
                    │ (SiliconFlow)  │
                    └────────────────┘
```

---

## 三、技术栈

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| **运行时** | Python 3.11+ | 成熟生态，AI 首选 |
| **Web 框架** | FastAPI | 高性能异步，自动生成 API 文档 |
| **ASGI 服务器** | Uvicorn | 生产级性能 |
| **向量数据库** | ChromaDB | 内置 embedding，API 简洁，本地持久化 |
| **认证** | API Key (Header) | 简单有效，兼容 mem9 协议 |
| **Embedding** | SiliconFlow API | 复用现有 key，支持 BGE 系列模型 |
| **进程管理** | systemd | 开机自启，日志管理 |
| **数据备份** | 文件系统复制 | ChromaDB 数据即文件夹 |

### 依赖清单

```
# requirements.txt
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
chromadb>=0.4.22
httpx>=0.26.0
python-multipart>=0.0.6
pydantic>=2.5.0
```

---

## 四、核心功能

### 4.1 API 端点设计（独立协议）

```
Base URL: http://<host>:8000
认证方式: Authorization: Bearer <api-key>
Content-Type: application/json
```

**核心接口：**

| Method | Path | 功能 | 说明 |
|--------|------|------|------|
| `GET` | `/` | 健康检查 | 无需认证 |
| `POST` | `/memory` | 创建记忆 | 返回记忆对象 |
| `GET` | `/memory` | 搜索记忆 | 语义 + 元数据过滤 |
| `GET` | `/memory/{id}` | 获取单条 | 按 ID |
| `PATCH` | `/memory/{id}` | 部分更新 | 只更新传入字段 |
| `DELETE` | `/memory/{id}` | 删除记忆 | 永久删除 |
| `POST` | `/batch` | 批量操作 | 创建/更新/删除多条 |
| `POST` | `/import` | 导入文件 | 上传并解析 |
| `GET` | `/stats` | 统计信息 | 记忆数量、存储占用 |

**简洁设计原则：**
- RESTful 风格
- 单数路径 `/memory`（资源本身）
- PATCH 而非 PUT（部分更新更实用）
- 批量接口合并创建/更新/删除

### 4.2 数据模型

```python
# 记忆实体
class Memory:
    id: str              # UUID，自动生成
    text: str            # 记忆文本内容（必需）
    tags: list[str]      # 标签，用于过滤
    meta: dict           # 自定义元数据（任意 JSON）
    score: float         # 搜索时返回的相似度分数
    created: datetime    # 创建时间，自动
    updated: datetime    # 更新时间，自动
```

**创建记忆：**

```http
POST /memory
Authorization: Bearer <YOUR_MEML_API_KEY>

{
  "text": "用户偏好深色主题，尤其是 Solarized Dark",
  "tags": ["preference", "ui"],
  "meta": {
    "confidence": 0.95,
    "from_session": "chat-20260321"
  }
}
```

**响应：**

```json
{
  "ok": true,
  "data": {
    "id": "m_abc123",
    "text": "用户偏好深色主题，尤其是 Solarized Dark",
    "tags": ["preference", "ui"],
    "meta": {
      "confidence": 0.95,
      "from_session": "chat-20260321"
    },
    "created": "2026-03-21T00:30:00Z",
    "updated": "2026-03-21T00:30:00Z"
  }
}
```

**搜索记忆：**

```http
GET /memory?q=用户喜欢什么主题&tags=preference&limit=5
Authorization: Bearer <YOUR_MEML_API_KEY>
```

**响应：**

```json
{
  "ok": true,
  "data": {
    "total": 12,
    "results": [
      {
        "id": "m_abc123",
        "text": "用户偏好深色主题，尤其是 Solarized Dark",
        "tags": ["preference", "ui"],
        "meta": { "confidence": 0.95 },
        "score": 0.89,
        "created": "2026-03-21T00:30:00Z"
      },
      {
        "id": "m_def456",
        "text": "用户不喜欢亮色界面",
        "tags": ["preference", "ui"],
        "meta": {},
        "score": 0.82,
        "created": "2026-03-20T15:00:00Z"
      }
    ]
  }
}
```

**批量操作：**

```http
POST /batch
Authorization: Bearer <YOUR_MEML_API_KEY>

{
  "create": [
    {"text": "记忆1", "tags": ["a"]},
    {"text": "记忆2", "tags": ["b"]}
  ],
  "update": [
    {"id": "m_xyz", "tags": ["new-tag"]}
  ],
  "delete": ["m_old1", "m_old2"]
}
```

**响应：**

```json
{
  "ok": true,
  "data": {
    "created": 2,
    "updated": 1,
    "deleted": 2
  }
}
```

### 4.3 语义搜索

**搜索参数（Query String）：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `q` | string | - | 语义查询（必需，会被转向量） |
| `tags` | string | - | 标签过滤，逗号分隔 `tags=a,b` |
| `tag_mode` | string | `any` | `any`=任一匹配，`all`=全部匹配 |
| `meta.*` | string | - | 元数据过滤，如 `meta.confidence=0.9` |
| `limit` | int | 10 | 返回数量，最大 100 |
| `offset` | int | 0 | 分页偏移 |

**搜索流程：**

```
GET /memory?q=用户喜欢什么主题&tags=preference&limit=5
           ↓
1. Embedding API 将 q 转为向量
           ↓
2. ChromaDB 向量相似度搜索
           ↓
3. 按 tags / meta 过滤
           ↓
4. 返回按 score 排序的结果
```

**示例：**

```bash
# 语义搜索
curl -H "Authorization: Bearer <YOUR_MEML_API_KEY>" \
  "http://localhost:8000/memory?q=用户的技术偏好&limit=5"

# 标签过滤
curl -H "Authorization: Bearer <YOUR_MEML_API_KEY>" \
  "http://localhost:8000/memory?q=&tags=preference,ui&limit=10"

# 纯标签查询（无语义）
curl -H "Authorization: Bearer <YOUR_MEML_API_KEY>" \
  "http://localhost:8000/memory?tags=important&limit=20"
```

### 4.4 文件导入

支持上传文件批量导入：

```http
POST /import
Authorization: Bearer <YOUR_MEML_API_KEY>
Content-Type: multipart/form-data

file: MEMORY.md
parse: markdown    # json / markdown / text
tags: imported     # 给所有导入的记忆加标签
```

**支持的文件格式：**

| 格式 | 解析方式 |
|------|----------|
| `json` | JSON 数组或 JSONL |
| `markdown` | 按段落/标题分割 |
| `text` | 按行或段落分割 |

**响应：**

```json
{
  "ok": true,
  "data": {
    "imported": 45,
    "skipped": 3,
    "errors": []
  }
}
```

### 4.5 统计接口

```http
GET /stats
Authorization: Bearer <YOUR_MEML_API_KEY>
```

**响应：**

```json
{
  "ok": true,
  "data": {
    "total_memories": 1234,
    "tags": {
      "preference": 45,
      "project": 30,
      "decision": 20
    },
    "storage_bytes": 5242880,
    "oldest": "2025-01-15T00:00:00Z",
    "newest": "2026-03-21T00:00:00Z"
  }
}
```

### 4.6 多租户

通过 API Key 区分不同租户：

```
<YOUR_MEML_API_KEY>  → 个人记忆空间
sk-local-work      → 工作记忆空间
sk-local-shared    → 共享记忆空间
```

每个 Key 的数据完全隔离，ChromaDB 使用不同的 collection。

---

## 五、目录结构

```
/opt/memL/
├── venv/                    # Python 虚拟环境
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置管理
│   ├── models.py            # Pydantic 数据模型
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── memory.py        # 记忆 CRUD
│   │   ├── batch.py         # 批量操作
│   │   ├── import.py        # 文件导入
│   │   └── stats.py         # 统计信息
│   ├── services/
│   │   ├── __init__.py
│   │   ├── vectorstore.py   # ChromaDB 封装
│   │   └── embedding.py     # Embedding 调用
│   └── middleware/
│       ├── __init__.py
│       └── auth.py          # API Key 认证
├── data/
│   └── chromadb/            # ChromaDB 数据（备份这个）
├── requirements.txt
└── memL.service       # systemd 服务文件
```

---

## 六、认证机制

### 6.1 API Key 管理

**预配置 Key（config.py）：**

```python
TENANTS = {
    "<YOUR_MEML_API_KEY>": {
        "name": "个人",
        "collection": "personal",
    },
    "sk-local-work": {
        "name": "工作", 
        "collection": "work",
    },
    "sk-local-shared": {
        "name": "共享",
        "collection": "shared",
    },
}
```

### 6.2 请求认证

使用标准 Bearer Token：

```http
Authorization: Bearer <YOUR_MEML_API_KEY>
```

**中间件：**

```python
@app.middleware("http")
async def auth(request: Request, call_next):
    # 健康检查无需认证
    if request.url.path == "/":
        return await call_next(request)
    
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse({"ok": false, "error": "Missing token"}, 401)
    
    token = auth_header[7:]
    if token not in TENANTS:
        return JSONResponse({"ok": false, "error": "Invalid token"}, 401)
    
    request.state.tenant = TENANTS[token]
    return await call_next(request)
```

---

## 七、Embedding 配置

使用 SiliconFlow API（复用现有 key）：

```python
# services/embedding.py
EMBEDDING_CONFIG = {
    "api_url": "https://api.siliconflow.cn/v1/embeddings",
    "api_key": "<EMBED_API_KEY>",
    "model": "BAAI/bge-large-zh-v1.5",
}

async def embed(text: str) -> list[float]:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            EMBEDDING_CONFIG["api_url"],
            headers={"Authorization": f"Bearer {EMBEDDING_CONFIG['api_key']}"},
            json={"model": EMBEDDING_CONFIG["model"], "input": text},
        )
        return r.json()["data"][0]["embedding"]
```

ChromaDB 调用时传入 embedding function，自动处理向量化。

---

## 八、systemd 服务配置

```ini
# /etc/systemd/system/memL.service
[Unit]
Description=memL Memory Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/memL/app
Environment=PATH=/opt/memL/venv/bin
ExecStart=/opt/memL/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

**管理命令：**

```bash
systemctl enable memL   # 开机自启
systemctl start memL    # 启动服务
systemctl status memL   # 查看状态
journalctl -u memL -f   # 查看日志
```

---

## 九、OpenClaw 集成

由于使用独立协议，需要写一个轻量的 OpenClaw 插件来调用。

**插件配置：**

```json
{
  "plugins": {
    "slots": { "memory": "memL" },
    "entries": {
      "memL": {
        "enabled": true,
        "config": {
          "apiUrl": "http://192.168.x.x:8000",
          "apiKey": "<YOUR_MEML_API_KEY>"
        }
      }
    },
    "allow": ["memL"]
  }
}
```

**插件功能：**
- `memory_store` → `POST /memory`
- `memory_search` → `GET /memory?q=...`
- `memory_get` → `GET /memory/{id}`
- `memory_update` → `PATCH /memory/{id}`
- `memory_delete` → `DELETE /memory/{id}`

或者直接用 `mcporter` 配置 MCP 工具调用，无需写插件代码。

---

## 十、备份策略

### 10.1 数据备份

```bash
# 备份 ChromaDB 数据
rsync -av /opt/memL/data/chromadb/ /backup/mem9-$(date +%Y%m%d)/

# 定时备份 (crontab)
0 3 * * * rsync -av /opt/memL/data/ /backup/mem9-daily/
```

### 10.2 恢复

```bash
# 停止服务
systemctl stop memL

# 恢复数据
rsync -av /backup/mem9-20260321/ /opt/memL/data/chromadb/

# 启动服务
systemctl start memL
```

---

## 十一、性能预估

| 指标 | 预估值 |
|------|--------|
| 内存占用 | 100-200 MB |
| 单次搜索延迟 | 50-200 ms |
| 存储容量 | 10万条记忆 ≈ 500MB |
| 并发能力 | 10-50 QPS（单进程） |

对于 4-5 个 OpenClaw 实例，完全够用。

---

## 十二、扩展方向

未来可考虑：

1. **Web 管理界面** — 可视化管理记忆
2. **记忆过期策略** — 自动清理过期/低价值记忆
3. **记忆去重** — 检测并合并相似记忆
4. **记忆重要性评分** — 按价值排序
5. **多模态支持** — 存储图片描述等

---

## 十三、开发计划

| 阶段 | 内容 | 时间 |
|------|------|------|
| Phase 1 | 基础 CRUD + 语义搜索 | 1-2 小时 |
| Phase 2 | API Key 认证 + 多租户 | 30 分钟 |
| Phase 3 | 批量导入功能 | 1 小时 |
| Phase 4 | 部署 + 测试 | 30 分钟 |

---

## 十四、API 速查表

```
认证: Authorization: Bearer <token>

GET    /                       # 健康检查
POST   /memory                 # 创建记忆
GET    /memory?q=&tags=&limit= # 搜索
GET    /memory/{id}            # 获取单条
PATCH  /memory/{id}            # 更新
DELETE /memory/{id}            # 删除
POST   /batch                  # 批量操作
POST   /import                 # 导入文件
GET    /stats                  # 统计信息
```

---

**准备好了告诉我，我开始写代码。**
