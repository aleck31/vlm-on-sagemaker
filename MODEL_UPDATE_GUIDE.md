# SageMaker VLM 模型更新指南

## 概述

本文档详细介绍如何在生产环境中安全地更新已部署的VLM模型，包括滚动更新、蓝绿部署等策略。

## 更新策略对比

| 策略 | 停机时间 | 资源消耗 | 回滚速度 | 复杂度 | 适用场景 |
|------|----------|----------|----------|--------|----------|
| **滚动更新** | 零停机 | 低 (5-50%额外) | 中等 | 低 | 生产推荐 |
| **蓝绿部署** | 零停机 | 高 (100%额外) | 快速 | 低 | 关键业务 |
| **重新部署** | 有停机 | 最低 | 慢 | 最低 | 开发测试 |

### 蓝绿部署模式对比

| 模式 | 流量切换 | 观察时间 | 风险控制 | 适用场景 |
|------|----------|----------|----------|----------|
| **金丝雀** | 10% → 90% | 长 | 最安全 | 生产推荐 |
| **线性** | 25% × 4步 | 中等 | 平衡 | 渐进更新 |
| **全量** | 100%一次 | 短 | 较高 | 快速部署 |

## 方案1: 滚动更新 (推荐)

### 特点
- **零停机**: 逐批更新实例，始终保持服务可用
- **资源优化**: 仅需5-50%额外容量
- **自动回滚**: 监控告警触发时自动回滚
- **渐进式**: 可控的批次大小和等待时间

### 实施步骤

#### 1. 准备新模型
```bash
# 上传新版本模型到S3
aws s3 sync ./new-model-v2/ s3://your-bucket/models/qwen2.5-vl-7b-v2/ --region your-region
```

#### 2. 创建新端点配置
```python
import boto3
from datetime import datetime

sagemaker_client = boto3.client('sagemaker')

# 创建新的端点配置
new_config_name = f"vlm-qwen2-5-vl-7b-v2-{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}"

response = sagemaker_client.create_endpoint_config(
    EndpointConfigName=new_config_name,
    ProductionVariants=[{
        'VariantName': 'AllTraffic',
        'ModelName': 'your-model-name',  # 可以是新模型
        'InitialInstanceCount': 2,
        'InstanceType': 'ml.g6e.2xlarge',
        'InitialVariantWeight': 1.0
    }]
)
```

#### 3. 配置滚动更新
```python
# 滚动更新配置
response = sagemaker_client.update_endpoint(
    EndpointName="your-endpoint-name",
    EndpointConfigName=new_config_name,
    DeploymentConfig={
        "AutoRollbackConfiguration": {
            "Alarms": [
                {"AlarmName": "ModelLatency-High"},
                {"AlarmName": "ModelErrors-High"}
            ]
        },
        "RollingUpdatePolicy": {
            "MaximumExecutionTimeoutInSeconds": 3600,  # 1小时超时
            "WaitIntervalInSeconds": 300,              # 5分钟观察期
            "MaximumBatchSize": {
                "Type": "CAPACITY_PERCENTAGE",
                "Value": 25                            # 每批25%实例
            },
            "RollbackMaximumBatchSize": {
                "Type": "CAPACITY_PERCENTAGE", 
                "Value": 100                           # 回滚时全部切换
            }
        }
    }
)
```

#### 4. 监控更新进度
```python
import time

def monitor_update_progress(endpoint_name):
    while True:
        response = sagemaker_client.describe_endpoint(EndpointName=endpoint_name)
        status = response['EndpointStatus']
        
        print(f"端点状态: {status}")
        
        if status == 'InService':
            print("✅ 更新完成")
            break
        elif status == 'Failed':
            print("❌ 更新失败")
            break
        elif status == 'RollingBack':
            print("🔄 正在回滚")
        
        time.sleep(30)

# 监控更新
monitor_update_progress("your-endpoint-name")
```

### CloudWatch告警配置

#### 必需告警
```python
import boto3

cloudwatch = boto3.client('cloudwatch')

# 1. 模型延迟告警
cloudwatch.put_metric_alarm(
    AlarmName='ModelLatency-High',
    ComparisonOperator='GreaterThanThreshold',
    EvaluationPeriods=2,
    MetricName='ModelLatency',
    Namespace='AWS/SageMaker',
    Period=300,
    Statistic='Average',
    Threshold=5000.0,  # 5秒
    ActionsEnabled=True,
    Dimensions=[
        {'Name': 'EndpointName', 'Value': 'your-endpoint-name'},
        {'Name': 'VariantName', 'Value': 'AllTraffic'}
    ]
)

# 2. 错误率告警
cloudwatch.put_metric_alarm(
    AlarmName='ModelErrors-High',
    ComparisonOperator='GreaterThanThreshold',
    EvaluationPeriods=2,
    MetricName='ModelLatency',
    Namespace='AWS/SageMaker',
    Period=300,
    Statistic='Sum',
    Threshold=10.0,  # 10个错误
    ActionsEnabled=True,
    Dimensions=[
        {'Name': 'EndpointName', 'Value': 'your-endpoint-name'},
        {'Name': 'VariantName', 'Value': 'AllTraffic'}
    ]
)
```

## 方案2: 蓝绿部署 (SageMaker原生)

### 特点
- **SageMaker托管**: 完全由SageMaker管理流量切换和实例
- **多种模式**: 支持金丝雀、线性、全量切换
- **自动回滚**: 监控告警触发时自动回滚
- **零停机**: 蓝绿环境并存，无服务中断

### 流量切换模式

#### 1. 金丝雀部署 (推荐)
```python
# 金丝雀部署：先切换10%流量测试
response = sagemaker_client.update_endpoint(
    EndpointName="your-endpoint-name",
    EndpointConfigName=new_config_name,
    DeploymentConfig={
        "BlueGreenUpdatePolicy": {
            "TrafficRoutingConfiguration": {
                "Type": "CANARY",
                "CanarySize": {
                    "Type": "CAPACITY_PERCENTAGE",
                    "Value": 10  # 10%流量先切换到绿色环境
                },
                "WaitIntervalInSeconds": 600  # 观察10分钟
            },
            "TerminationWaitInSeconds": 300,
            "MaximumExecutionTimeoutInSeconds": 3600
        },
        "AutoRollbackConfiguration": {
            "Alarms": [
                {"AlarmName": "ModelLatency-High"},
                {"AlarmName": "ModelErrors-High"}
            ]
        }
    }
)
```

#### 2. 线性切换
```python
# 线性切换：分4步，每步25%流量
response = sagemaker_client.update_endpoint(
    EndpointName="your-endpoint-name", 
    EndpointConfigName=new_config_name,
    DeploymentConfig={
        "BlueGreenUpdatePolicy": {
            "TrafficRoutingConfiguration": {
                "Type": "LINEAR",
                "LinearStepSize": {
                    "Type": "CAPACITY_PERCENTAGE",
                    "Value": 25  # 每步切换25%
                },
                "WaitIntervalInSeconds": 300  # 每步观察5分钟
            },
            "TerminationWaitInSeconds": 300,
            "MaximumExecutionTimeoutInSeconds": 3600
        },
        "AutoRollbackConfiguration": {
            "Alarms": [
                {"AlarmName": "ModelLatency-High"},
                {"AlarmName": "ModelErrors-High"}
            ]
        }
    }
)
```

#### 3. 全量切换
```python
# 全量切换：一次性切换所有流量
response = sagemaker_client.update_endpoint(
    EndpointName="your-endpoint-name",
    EndpointConfigName=new_config_name, 
    DeploymentConfig={
        "BlueGreenUpdatePolicy": {
            "TrafficRoutingConfiguration": {
                "Type": "ALL_AT_ONCE",
                "WaitIntervalInSeconds": 300  # 观察5分钟后清理蓝色环境
            },
            "TerminationWaitInSeconds": 300,
            "MaximumExecutionTimeoutInSeconds": 3600
        },
        "AutoRollbackConfiguration": {
            "Alarms": [
                {"AlarmName": "ModelLatency-High"},
                {"AlarmName": "ModelErrors-High"}
            ]
        }
    }
)
```

### 监控部署进度
```python
def monitor_blue_green_deployment(endpoint_name):
    """监控蓝绿部署进度"""
    while True:
        response = sagemaker_client.describe_endpoint(EndpointName=endpoint_name)
        status = response['EndpointStatus']
        
        # 获取部署详情
        if 'PendingDeploymentSummary' in response:
            deployment = response['PendingDeploymentSummary']
            print(f"部署阶段: {deployment.get('StageName', 'Unknown')}")
        
        print(f"端点状态: {status}")
        
        if status == 'InService':
            print("✅ 蓝绿部署完成")
            break
        elif status == 'Failed':
            print("❌ 部署失败")
            break
        elif status == 'RollingBack':
            print("🔄 正在自动回滚")
        
        time.sleep(30)

# 监控部署
monitor_blue_green_deployment("your-endpoint-name")
```

### 部署阶段说明
```python
# SageMaker蓝绿部署自动执行以下阶段：
deployment_stages = {
    "Creating": "创建绿色环境",
    "Baking": "观察期监控",
    "Shifting": "流量切换中", 
    "Terminating": "清理蓝色环境"
}
```

## 方案3: 重新部署

### 适用场景
- 开发测试环境
- 可接受短暂停机
- 资源受限环境

### 实施步骤
```python
# 1. 停止端点
sagemaker_client.delete_endpoint(EndpointName="your-endpoint-name")

# 2. 等待端点删除完成
waiter = sagemaker_client.get_waiter('endpoint_deleted')
waiter.wait(EndpointName="your-endpoint-name")

# 3. 使用新配置重新创建端点
sagemaker_client.create_endpoint(
    EndpointName="your-endpoint-name",
    EndpointConfigName=new_config_name
)
```

## 最佳实践

### 1. 更新前检查
```bash
# 检查清单
- [ ] 新模型已上传到S3
- [ ] CloudWatch告警已配置
- [ ] 测试用例已准备
- [ ] 回滚计划已制定
- [ ] 监控仪表板已就绪
```

### 2. 分阶段更新
```python
# 推荐的批次大小
batch_sizes = {
    "小型端点 (2-4实例)": "50%",
    "中型端点 (5-10实例)": "25%", 
    "大型端点 (10+实例)": "10-20%"
}
```

### 3. 监控指标
```python
# 关键监控指标
key_metrics = [
    'ModelLatency',           # 模型延迟
    'Invocations',           # 调用次数
    'InvocationErrors',      # 调用错误
    'GPUUtilization',        # GPU利用率
    'GPUMemoryUtilization'   # GPU内存利用率
]
```

### 4. 回滚策略
```python
def emergency_rollback(old_config_name, endpoint_name):
    """紧急回滚到旧版本"""
    try:
        sagemaker_client.update_endpoint(
            EndpointName=endpoint_name,
            EndpointConfigName=old_config_name
        )
        print("🔄 紧急回滚已启动")
    except Exception as e:
        print(f"❌ 回滚失败: {e}")
```

## 成本优化

### 1. 更新时间选择
- **低峰期更新**: 减少对用户影响
- **分区域更新**: 全球部署时错峰更新

### 2. 资源管理
```python
# 临时扩容策略
def temporary_scale_up():
    """更新期间临时增加容量"""
    autoscaling_client.register_scalable_target(
        MinCapacity=4,  # 临时增加最小容量
        MaxCapacity=8   # 临时增加最大容量
    )

def restore_normal_capacity():
    """更新完成后恢复正常容量"""
    autoscaling_client.register_scalable_target(
        MinCapacity=2,  # 恢复正常最小容量
        MaxCapacity=4   # 恢复正常最大容量
    )
```

## 总结

### 推荐策略
- **生产环境**: 滚动更新 (零停机 + 资源优化)
- **关键业务**: 蓝绿部署金丝雀模式 (最安全 + SageMaker托管)
- **开发测试**: 重新部署 (简单快速 + 成本最低)

### SageMaker原生优势
- **完全托管**: 无需手动管理流量切换和实例清理
- **多种模式**: 金丝雀、线性、全量切换满足不同需求
- **自动回滚**: CloudWatch告警集成，故障时自动回滚
- **零运维**: 无需额外的负载均衡器或DNS配置

选择合适的更新策略，配置完善的监控告警，利用SageMaker原生能力确保VLM模型更新的安全性和可靠性。
