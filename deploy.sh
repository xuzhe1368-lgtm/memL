#!/bin/bash
# memL 部署脚本
set -e

echo "=== memL 部署脚本 ==="

# 1. 创建用户
if ! id meml &>/dev/null; then
    echo "创建 meml 用户..."
    useradd -r -s /usr/sbin/nologin meml
fi

# 2. 安装依赖
echo "安装 Python 依赖..."
apt update && apt install -y python3 python3-pip python3-venv

# 3. 创建虚拟环境
if [ ! -d "/opt/memL/venv" ]; then
    echo "创建虚拟环境..."
    cd /opt/memL
    python3 -m venv venv
fi

# 4. 安装 Python 包
echo "安装 Python 包..."
/opt/memL/venv/bin/pip install -r /opt/memL/requirements.txt

# 5. 创建数据目录
mkdir -p /opt/memL/data/chromadb

# 6. 设置权限（最小范围）
echo "设置权限..."
chown -R meml:meml /opt/memL/app /opt/memL/data /opt/memL/venv /opt/memL/.env /opt/memL/tenants.yaml 2>/dev/null || true

# 7. 安装 systemd 服务
echo "安装 systemd 服务..."
cp /opt/memL/memL.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable memL

echo ""
echo "=== 部署完成 ==="
echo ""
echo "下一步："
echo "1. 编辑 /opt/memL/.env 配置 API Key"
echo "   cp /opt/memL/.env.example /opt/memL/.env"
echo "   nano /opt/memL/.env"
echo ""
echo "2. 启动服务"
echo "   systemctl start memL"
echo ""
echo "3. 验证"
echo "   curl http://127.0.0.1:8000/health/live"
