#!/usr/bin/env python3
"""
OpenAI兼容客户端示例
"""

from openai import OpenAI

# 连接LiteLLM代理
client = OpenAI(
    api_key="sk-1234",
    base_url="http://localhost:4000"
)

# 调用VLM模型
response = client.chat.completions.create(
    model="qwen-vlm-private",
    messages=[
        {"role": "user", "content": "你好！请简单介绍一下自己。"}
    ],
    temperature=0.3,
    max_tokens=200
)

print(response.choices[0].message.content)
