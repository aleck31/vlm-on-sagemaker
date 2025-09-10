# LiteLLM SageMaker VLM 集成指南

## 概述

本目录包含LiteLLM代理服务器配置，用于将SageMaker VLM端点转换为OpenAI兼容的API。

## 功能支持状态

### ✅ 支持
- **文本对话**: `sagemaker_chat/` 前缀完美支持
- **OpenAI SDK兼容**: 完全兼容OpenAI Python SDK
- **代理服务**: 稳定的HTTP代理服务器
- **多端点**: 支持VPC和公网部署的端点

### ❌ 限制
- **VLM视觉功能**: `sagemaker_chat/` 前缀的VLM功能存在兼容性问题
- **图像处理**: Qwen2.5-VL预处理器与LiteLLM格式转换不兼容
- **多模态内容**: `sagemaker/` 前缀无法处理OpenAI多模态格式

## 文件结构

```
litellm/
├── README.md                 # 本文档
├── litellm_config.yaml         # LiteLLM代理配置
├── start_proxy.sh           # 代理启动脚本
└── client_example.py        # OpenAI客户端示例
```

## 快速开始

### 1. 启动代理服务器

```bash
cd litellm
./start_proxy.sh
```

服务将在 `http://localhost:4000` 启动

### 2. 测试文本功能

```bash
python client_example.py
```

### 3. 使用OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-1234",
    base_url="http://localhost:4000"
)

response = client.chat.completions.create(
    model="qwen-vlm-private",  # 或 "qwen-vlm-public"
    messages=[
        {"role": "user", "content": "你好！"}
    ],
    temperature=0.3,
    max_tokens=200
)

print(response.choices[0].message.content)
```

## 配置说明

### litellm_config.yaml

```yaml
model_list:
  - model_name: "qwen-vlm-private"
    litellm_params:
      model: "sagemaker_chat/your-vpc-endpoint-name"
      aws_region_name: "eu-west-2"
      temperature: 0.2
      max_tokens: 500
    model_info:
      supports_vision: true  # 标记支持视觉（实际功能有限制）
      
  - model_name: "qwen-vlm-public"  
    litellm_params:
      model: "sagemaker_chat/your-public-endpoint-name"
      aws_region_name: "eu-west-2"
      temperature: 0.2
      max_tokens: 500
    model_info:
      supports_vision: true
```

### 关键配置项

- **模型前缀**: 使用 `sagemaker_chat/` 而非 `sagemaker/`
- **AWS区域**: 确保与SageMaker端点区域一致
- **Worker数量**: 建议1-4个worker，避免过多并发
- **Vision支持**: 配置 `supports_vision: true` 但实际功能受限

## 实测结果总结

### 成功案例
- ✅ 文本对话响应正常，中英文支持良好
- ✅ OpenAI SDK完全兼容，无需修改客户端代码
- ✅ 代理服务稳定，支持并发请求
- ✅ 支持VPC和公网部署的SageMaker端点

### 失败案例
- ❌ VLM图像识别功能无法正常工作
- ❌ 错误信息: `RuntimeError: Failed to apply Qwen2_5_VLProcessor`
- ❌ 问题根源: Qwen2.5-VL预处理器与LiteLLM格式转换不兼容

### 错误分析

**CloudWatch日志显示的错误:**
```
RuntimeError: Failed to apply Qwen2_5_VLProcessor on data={
  'text': '<|image_pad|>', 
  'images': [<PIL.Image.Image image mode=RGB size=10x10>]
} with kwargs={}
```

**根本原因:**
- LiteLLM将OpenAI格式转换为SageMaker格式时，图像处理部分与Qwen2.5-VL的预处理器不兼容
- `sagemaker_chat/` 前缀主要优化文本聊天功能
- `sagemaker/` 前缀无法处理多模态内容（list格式）

## 推荐使用方案

### 混合架构（推荐）

```python
# 文本对话 - 使用LiteLLM代理
def text_chat(message):
    client = OpenAI(base_url="http://localhost:4000", api_key="sk-1234")
    return client.chat.completions.create(
        model="qwen-vlm-private",
        messages=[{"role": "user", "content": message}]
    )

# VLM功能 - 使用原生AWS SDK
def vision_chat(message, image_path):
    # 使用原生AWS SDK调用SageMaker端点
    # 参考主项目中的 call_vlm_endpoint 函数
    pass
```

### 纯LiteLLM方案
- 仅用于文本对话场景
- 完全兼容OpenAI生态系统
- 适合需要统一API接口的应用

## 故障排除

### 常见问题

1. **代理启动失败**
   ```bash
   # 检查端口占用
   lsof -i :4000
   # 重启代理
   ./start_proxy.sh
   ```

2. **AWS认证失败**
   ```bash
   # 确保AWS profile配置正确
   export AWS_PROFILE=lab
   aws sts get-caller-identity
   ```

3. **端点连接失败**
   - 检查端点名称是否正确
   - 确认AWS区域设置
   - 验证IAM权限

### 日志调试

```python
# 启用LiteLLM调试模式
import litellm
litellm._turn_on_debug()
```

## 未来改进

### 待解决问题
- [ ] 完善VLM功能支持
- [ ] 优化图像格式转换
- [ ] 支持更多VLM模型

### 可能的解决方案
- 等待LiteLLM官方更新Qwen2.5-VL支持
- 向LiteLLM项目提交issue和PR
- 考虑使用其他VLM模型测试兼容性

## 相关链接

- [LiteLLM官方文档](https://docs.litellm.ai/)
- [SageMaker VLM部署指南](../README.md)
- [AWS SDK VLM调用示例](../vlm_deploy_sagemaker.ipynb)
