# memL

自建 OpenClaw 云端记忆服务。

## 快速开始

```bash
# 1. 复制到目标机器
scp -r /opt/memL user@target:/opt/

# 2. 配置环境变量
cp /opt/memL/.env.example /opt/memL/.env
nano /opt/memL/.env  # 填入你的 API Key

# 3. 运行部署脚本
chmod +x /opt/memL/deploy.sh
/opt/memL/deploy.sh

# 4. 启动服务
systemctl start memL

# 5. 验证
curl http://<MEML_HOST>:8000/health/live
```

## API

```
认证: Authorization: Bearer <token>

GET    /                       # 服务信息
GET    /health/live            # 存活检查
GET    /health/ready           # 就绪检查
POST   /memory                 # 创建记忆
GET    /memory?q=&tags=&limit= # 搜索
GET    /memory/{id}            # 获取单条
PATCH  /memory/{id}            # 更新
DELETE /memory/{id}            # 删除
GET    /stats                  # 统计
```

## 目录结构

```
/opt/memL/
├── .env                 # 环境变量（包含 API Key）
├── .env.example         # 环境变量示例
├── tenants.yaml         # 租户配置
├── requirements.txt     # Python 依赖
├── memL.service         # systemd 服务文件
├── deploy.sh            # 部署脚本
└── app/
    ├── main.py          # FastAPI 入口
    ├── config.py        # 配置管理
    ├── models.py        # 数据模型
    ├── middleware/
    │   └── auth.py      # 认证中间件
    ├── routers/
    │   └── memory.py    # 记忆 API
    └── services/
        ├── embedding.py # Embedding 服务
        └── vectorstore.py # ChromaDB 封装
```

## 配置

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| MEML_HOST | 监听地址 | 0.0.0.0 |
| MEML_PORT | 端口 | 8000 |
| MEML_LOG_LEVEL | 日志级别 | INFO |
| MEML_DATA_DIR | 数据目录 | /opt/memL/data/chromadb |
| MEML_TENANTS_FILE | 租户配置 | /opt/memL/tenants.yaml |
| MEML_EMBED_API_URL | Embedding API | - |
| MEML_EMBED_API_KEY | Embedding Key | - |
| MEML_EMBED_MODEL | 模型 | BAAI/bge-large-zh-v1.5 |
| MEML_EMBED_TIMEOUT_SEC | 超时 | 8 |
| MEML_EMBED_MAX_RETRIES | 重试次数 | 2 |
| MEML_EMBED_MAX_CONCURRENCY | 并发限制 | 16 |

## 示例

```bash
# 创建记忆
curl -X POST http://<MEML_HOST>:8000/memory \
  -H "Authorization: Bearer <YOUR_MEML_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"text":"用户偏好深色主题","tags":["preference","ui"]}'

# 搜索
curl "http://<MEML_HOST>:8000/memory?q=用户喜欢什么&limit=5" \
  -H "Authorization: Bearer <YOUR_MEML_API_KEY>"

# 标签过滤
curl "http://<MEML_HOST>:8000/memory?tags=preference&limit=10" \
  -H "Authorization: Bearer <YOUR_MEML_API_KEY>"
```


## 一键自检（发布版）

```bash
chmod +x scripts/smoke.sh
./scripts/smoke.sh http://<MEML_HOST>:8000 <YOUR_MEML_API_KEY>
```

## OpenClaw 插件接入

在 `~/.openclaw/openclaw.json` 中确保：

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
