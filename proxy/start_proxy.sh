#!/bin/bash
# LiteLLM代理服务器启动脚本

# 激活虚拟环境
source ../.venv/bin/activate

# 设置AWS配置
export AWS_PROFILE=your_profile

# 启动LiteLLM代理服务器
echo "🚀 启动LiteLLM代理服务器..."
echo "📍 配置文件: litellm_config.yaml"
echo "🌐 服务地址: http://localhost:4000"
echo "📋 API文档: http://localhost:4000/docs"

litellm --config litellm_config.yaml --port 4000 --num_workers 2
