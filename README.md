# AWS SageMaker VLM 生产级部署指南

## 概述

本指南提供在SageMaker Endpoint上部署视觉语言模型(VLM)的生产级解决方案，支持弹性推理集群和自动扩缩容。

## 部署架构

### 推荐架构
- **实时推理端点**: 低延迟交互式推理
- **Large Model Inference (LMI) 容器**: 专为大模型优化的推理容器
- **S3 Express存储**: 提升模型下载性能
- **自动扩缩容**: 基于流量动态调整实例数量 (2-10个实例)
- **多实例部署**: 支持高可用和负载分担

### 部署方式
- 使用AWS预构建的LMI容器，无需自定义AMI
- 模型从S3动态加载，通过serving.properties配置
- 支持vLLM、TensorRT-LLM等多种推理后端

## 实例类型选择 (ml.g5/g6e系列)

### GPU实例推荐
| 实例类型 | GPU | 系统内存 | 适用场景 |
|---------|-----|----------|---------|
| ml.g5.xlarge | 1x A10G (24GB) | 16GB | 小型VLM模型 |
| ml.g5.2xlarge | 1x A10G (24GB) | 32GB | 中型VLM模型 |
| ml.g5.4xlarge | 1x A10G (24GB) | 64GB | 中型VLM模型 |
| ml.g5.12xlarge | 4x A10G (96GB) | 192GB | 多GPU并行推理 |
| ml.g6e.xlarge | 1x L40S (48GB) | 32GB | 中型VLM模型 |
| ml.g6e.2xlarge | 1x L40S (48GB) | 64GB | 大型VLM模型 |
| ml.g6e.4xlarge | 1x L40S (48GB) | 128GB | 超大型VLM模型 |
| ml.g6e.12xlarge | 4x L40S (192GB) | 384GB | 多GPU并行推理 |

### 实例选择建议
- **开发/测试**: ml.g5.xlarge 或 ml.g6e.xlarge (24GB/48GB显存)
- **生产环境**: ml.g6e.2xlarge 起步 (L40S高性能推荐)
- **高并发**: ml.g5.12xlarge 或 ml.g6e.12xlarge (多GPU并行)
- **大模型**: ml.g6e.4xlarge (大内存支持)
- **成本优化**: ml.g5系列 (A10G GPU，成本较低)

## LMI容器配置

### 支持的推理后端
| 后端 | 容器URI模板 | 特点 |
|------|-------------|------|
| vLLM | 763104351884.dkr.ecr.{region}.amazonaws.com/djl-inference:0.33.0-lmi15.0.0-cu128 | 高吞吐量，连续批处理 |
| TensorRT-LLM | 763104351884.dkr.ecr.{region}.amazonaws.com/djl-inference:0.32.0-tensorrtllm0.12.0-cu125 | 低延迟，NVIDIA优化 |

### 关键配置参数
```properties
# 基于项目经验的优化配置
engine=Python
option.model_id=s3://your-bucket/model-path/
option.dtype=fp16                    # 内存优化
option.rolling_batch=vllm            # 高性能推理
option.tensor_parallel_degree=1      # 单GPU配置
option.device_map=auto               # 自动设备映射
option.max_model_len=4096            # 序列长度
option.max_rolling_batch_size=32     # 批处理大小
option.use_v2_block_manager=true     # vLLM v2优化
option.enable_streaming=false        # 根据需求启用
```

## 弹性推理集群

### 自动扩缩容特性
- **水平扩缩容**: 基于GPU利用率自动调整实例数量 (2-10个实例)
- **负载均衡**: 多实例间自动分发请求，故障实例自动剔除
- **快速响应**: 3分钟扩容冷却时间，适应流量突增
- **高可用性**: 最小2个实例确保服务连续性

### 扩缩容策略
```python
# 扩缩容配置
scaling_config = {
    "MinCapacity": 2,                # 最小2个实例确保高可用性
    "MaxCapacity": 10,               # 最大实例数
    "TargetValue": 70.0,             # 目标GPU利用率70%
    "ScaleOutCooldown": 180,         # 3分钟快速扩容
    "ScaleInCooldown": 300           # 5分钟谨慎缩容
}
```

### 监控指标
- **GPUUtilization**: GPU使用率 (主要指标)
- **ModelLatency**: 模型推理延迟
- **InvocationsPerInstance**: 每实例调用数

## 部署步骤

### 执行环境
**推荐**: SageMaker Studio (预配置AWS凭证和权限)
**备选**: SageMaker Notebook Instance

### 获取代码
```bash
# 克隆项目代码
git clone https://github.com/aleck31/vlm-on-sagemaker.git
cd vlm-on-sagemaker
```

### 模型准备

#### 1: 微调模型上传到S3
如果你已有微调好的VLM模型，直接上传到S3：

```bash
# 上传本地模型到S3
aws s3 sync ./your-model-directory/ s3://your-bucket/models/your-model-name/ --region your-region

# 确保包含必要文件
 ✅ config.json                 #模型配置
 ✅ tokenizer.json              #分词器
 ✅ tokenizer_config.json       #分词器配置
 ✅ preprocessor_config.json    #预处理配置 (VLM必需)
 ✅ generation_config.json      #生成配置
 ✅ model-*.safetensors 文件     #模型权重文件
 ✅ model.safetensors.index.json   # 重索引文件
```

#### 2: 下载开源模型到S3
使用提供的下载脚本从Hugging Face下载开源模型并上传到S3：

```bash
# 下载Qwen2.5-VL-7B模型
python download_model.py \
  --model qwen2.5-vl-7b \
  --s3-bucket your-bucket-name \
  --region us-west-2

# 支持的模型
# qwen2.5-vl-3b   - Qwen/Qwen2.5-VL-3B-Instruct
# qwen2.5-vl-7b   - Qwen/Qwen2.5-VL-7B-Instruct  
# qwen2.5-vl-72b  - Qwen/Qwen2.5-VL-72B-Instruct
```

下载完成后，在notebook中使用输出的S3路径：
```python
MODEL_S3_PATH = "s3://your-bucket-name/models/qwen2.5-vl-7b/"
```

**提示信息**:
- 模型会先下载到本地 `./models/` 目录，然后上传到S3
- 如需更快的模型加载性能，可考虑使用S3 Express One Zone存储类

### 部署选项

#### 1. 标准部署 (快速开始)
使用提供的Jupyter Notebook进行部署：

```bash
# 在SageMaker Studio/Notebook中打开
vlm_deploy_sagemaker.ipynb
```

#### 2. VPC部署 (生产环境推荐)
使用VPC部署notebook进行安全的生产级部署：

```bash
# 在SageMaker Studio/Notebook中打开
vlm_deploy_sagemaker_vpc.ipynb
```

**提示**: 参考 [VPC网络配置](#vpc网络配置) 章节配置VPC、子网和安全组。

### 部署方案功能对比

| 功能 | 标准部署 | VPC部署 |
|------|----------|---------|
| 部署速度 | 10-15分钟 | 15-20分钟 |
| 网络安全 | 公共网络 | 私有VPC |
| 配置复杂度 | 简单 | 中等 |
| 生产就绪 | 适合测试 | 生产推荐 |
| 合规要求 | 基础 | 企业级 |

### 标准部署功能
- **环境准备**: 自动安装依赖和配置
- **参数配置**: 可自定义模型路径、实例类型等
- **LMI配置**: 自动生成serving.properties
- **端点部署**: 一键部署到SageMaker
- **扩缩容配置**: 自动配置弹性伸缩
- **推理测试**: 内置测试函数

### VPC部署额外功能
- **VPC资源验证**: 检查安全组和子网配置
- **网络隔离**: 端点运行在私有网络中
- **安全增强**: 精确的访问控制
- **性能优化**: 降低网络延迟
- **合规支持**: 满足企业安全要求

### 关键配置参数

#### 标准部署配置
```python
# 基础配置
MODEL_S3_PATH = "s3://your-bucket/models/qwen2-5-vl-7b/"
INSTANCE_TYPE = "ml.g6e.2xlarge"
INITIAL_INSTANCE_COUNT = 2
```

#### VPC部署额外配置
```python
# VPC资源配置
VPC_SECURITY_GROUP_IDS = ['sg-xxxxxxxxx']
VPC_SUBNET_IDS = ['subnet-xxxxxxxx', 'subnet-yyyyyyyy']
```

### 推理参数配置(L40S GPU优化)
- **批处理大小**: 推荐max_rolling_batch_size=32-64
- **数据类型**: 使用fp16平衡性能和精度
- **量化**: AWQ量化可减少50%显存占用
- **序列长度**: 根据显存动态调整max_model_len

### 部署时间
- **标准部署**: 10-15分钟
- **VPC部署**: 15-20分钟 (包含网络配置)
- **扩缩容配置**: 1-2分钟

### 部署验证
两个notebook都会自动进行：
- 端点状态检查
- 推理调用测试
- 扩缩容策略确认

## VPC网络配置

### 网络架构建议

**开发测试环境:**
- 可以共用相同子网和安全组简化配置

**生产环境推荐架构:**
```
同一VPC，不同子网和安全组
├── SageMaker Studio: 专用子网 + 安全组
└── SageMaker Endpoint: 专用子网 + 安全组
```

### VPC部署要求

**Public Subnet部署 (开发测试):**
- ✅ 有Internet Gateway，可直接访问S3
- ✅ 安全组允许HTTPS(443)出站到0.0.0.0/0

**Private Subnet部署 (生产推荐):**
- ✅ 必须配置S3 VPC端点 (Gateway类型)
- ✅ 路由表包含S3端点路由
- ✅ 安全组允许HTTPS(443)出站到0.0.0.0/0

### 多子网配置
- **推荐**: 至少2个子网，分布在不同AZ
- **类型**: 相同类型子网 (都是private或都是public)
- **用途**: 高可用性和负载分散

### 安全组配置
```python
# Endpoint安全组入站规则
{
    "Type": "HTTPS",
    "Protocol": "TCP", 
    "Port": 443,
    "Source": "VPC_CIDR"  # 例如: 172.31.0.0/16
}

## 监控和告警

### CloudWatch指标配置
```python
# 关键监控指标
metrics = [
    'InvocationsPerInstance',
    'ModelLatency', 
    'GPUUtilization',
    'GPUMemoryUtilization'
]

# 告警阈值
alerts = {
    'ModelLatency': 3000,        # 3秒延迟告警
    'GPUUtilization': 85,        # 85% GPU告警
    'GPUMemoryUtilization': 90   # 90% GPU内存告警
}
```

## 成本优化

### SageMaker Savings Plans (推荐)
- **支持范围**: 覆盖所有ml.g5和ml.g6e实例类型
- **节省幅度**: 最高64%折扣 (相比按需定价)
- **承诺期**: 1年或3年期
- **灵活性**: 可在不同实例类型、大小、区域间切换
- **购买方式**: AWS Console > Billing > Savings Plans

### 实例成本参考
- **ml.g5.xlarge**: 约$1.8/小时 (开发测试，成本优化)
- **ml.g5.2xlarge**: 约$2.4/小时 (生产环境，成本优化)
- **ml.g6e.xlarge**: 约$2.5/小时 (开发测试)
- **ml.g6e.2xlarge**: 约$3.2/小时 (生产推荐)
- **ml.g6e.4xlarge**: 约$4.8/小时 (大模型)

### 资源优化策略
- **模型压缩**: AWQ量化减少显存占用
- **智能扩缩容**: 根据流量动态调整实例数量
- **批处理优化**: 提高GPU利用率

## 安全配置

### 网络安全
- **VPC**: 支持部署在私有VPC中
- **安全组**: 仅允许必要端口访问
- **NAT Gateway**: 安全的外网访问

### 数据安全
- **加密**: 传输和存储加密
- **访问控制**: API Gateway + IAM认证
- **审计**: CloudTrail记录所有API调用

## 故障排除

### 部署失败诊断
```python
# 查看详细失败原因
endpoint_info = sm_client.describe_endpoint(EndpointName=endpoint_name)
print(f"失败原因: {endpoint_info.get('FailureReason', '未知')}")
```

### 网络连接问题
1. **S3访问失败**: 
   - Private Subnet: 检查S3 VPC端点配置
   - Public Subnet: 检查Internet Gateway和路由表
   - 安全组: 确保允许HTTPS(443)出站

2. **Studio无法访问Endpoint**:
   - 检查安全组入站规则允许Studio访问
   - 确认子网在同一VPC或有正确的网络路由

### 其它常见问题
1. **显存不足**: 启用AWQ量化或减少batch_size
2. **性能不佳**: 检查tensor_parallel_degree设置
3. **启动慢**: L40S GPU初始化时间较长，增加超时时间
4. **网络延迟**: 使用VPC端点优化
5. **配额限制**: 提前申请实例配额增加
6. **模型文件问题**: 检查必需文件是否完整，特别是preprocessor_config.json

## 部署检查清单

- [ ] 确认目标Region配额充足 (ml.g5/g6e实例)
- [ ] 上传VLM模型到S3存储桶
- [ ] 配置IAM角色和权限
- [ ] 准备LMI配置文件 (serving.properties)
- [ ] 选择合适的ml.g5/g6e实例类型
- [ ] 设置VPC和安全组
- [ ] 配置CloudWatch监控
- [ ] 测试自动扩缩容策略
- [ ] 验证推理调用和性能指标
