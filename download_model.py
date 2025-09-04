#!/usr/bin/env python3
"""
VLM模型下载脚本 - 从Hugging Face下载模型并上传到S3
"""

import os
import argparse
import boto3
import shutil
from transformers import AutoModel, AutoProcessor, AutoTokenizer
import torch

# 支持的模型配置
SUPPORTED_MODELS = {
    "qwen2.5-vl-3b": "Qwen/Qwen2.5-VL-3B-Instruct",
    "qwen2.5-vl-7b": "Qwen/Qwen2.5-VL-7B-Instruct",
    "qwen2.5-vl-72b": "Qwen/Qwen2.5-VL-72B-Instruct"
}

def download_model(model_id, local_path):
    """从Hugging Face下载模型"""
    print(f"📥 下载模型: {model_id}")
    print(f"📁 本地保存: {local_path}")
    
    os.makedirs(local_path, exist_ok=True)
    
    # 下载模型、处理器和分词器
    model = AutoModel.from_pretrained(model_id, torch_dtype=torch.float16, trust_remote_code=True)
    processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    
    # 保存到本地
    model.save_pretrained(local_path)
    processor.save_pretrained(local_path)
    tokenizer.save_pretrained(local_path)
    
    print(f"✅ 下载完成: {local_path}")

def upload_to_s3(local_path, s3_bucket, s3_prefix, region):
    """上传模型到S3"""
    print(f"📤 上传到S3: s3://{s3_bucket}/{s3_prefix}")
    
    # 检查是否为S3 Express存储桶
    if "--x-s3" in s3_bucket:
        print("🚀 检测到S3 Express存储桶，将获得更快的加载性能")
        print("⚠️  请确保SageMaker端点部署在相同可用区")
    
    s3_client = boto3.client('s3', region_name=region)
    
    # 统计文件数量
    file_count = sum(len(files) for _, _, files in os.walk(local_path))
    print(f"📋 准备上传 {file_count} 个文件...")
    
    # 上传所有文件
    uploaded = 0
    for root, dirs, files in os.walk(local_path):
        for file in files:
            local_file = os.path.join(root, file)
            relative_path = os.path.relpath(local_file, local_path)
            s3_key = f"{s3_prefix.rstrip('/')}/{relative_path}"
            s3_client.upload_file(local_file, s3_bucket, s3_key)
            uploaded += 1
            if uploaded % 10 == 0:
                print(f"  已上传 {uploaded}/{file_count} 个文件...")
    
    s3_path = f"s3://{s3_bucket}/{s3_prefix}"
    print(f"✅ 上传完成: {s3_path}")
    return s3_path

def main():
    parser = argparse.ArgumentParser(description="下载VLM模型并上传到S3")
    parser.add_argument("--model", required=True, choices=list(SUPPORTED_MODELS.keys()), help="模型名称")
    parser.add_argument("--s3-bucket", required=True, help="S3存储桶名称 (推荐S3 Express)")
    parser.add_argument("--region", default="us-west-2", help="AWS区域")
    parser.add_argument("--keep-local", action="store_true", help="保留本地文件")
    
    args = parser.parse_args()
    
    model_id = SUPPORTED_MODELS[args.model]
    local_path = f"./models/{args.model}"
    s3_prefix = f"models/{args.model}/"
    
    print("🚀 VLM模型下载器")
    print(f"📋 模型: {args.model} ({model_id})")
    print(f"📁 本地目录: {local_path}")
    print(f"☁️  S3目标: s3://{args.s3_bucket}/{s3_prefix}")
    print("-" * 60)
    
    try:
        # 1. 下载模型
        download_model(model_id, local_path)
        
        # 2. 上传到S3
        s3_path = upload_to_s3(local_path, args.s3_bucket, s3_prefix, args.region)
        
        # 3. 清理本地文件
        if not args.keep_local:
            print("🧹 清理本地文件...")
            shutil.rmtree(local_path)
            print("✅ 本地文件已清理")
        else:
            print(f"📁 本地文件保留在: {local_path}")
        
        # 4. 输出结果
        print("\n" + "=" * 60)
        print("🎉 模型下载和上传完成!")
        print(f"📍 S3路径: {s3_path}")
        print("\n📝 在notebook中使用:")
        print(f'MODEL_S3_PATH = "{s3_path}"')
        
        if "--x-s3" in args.s3_bucket:
            print("\n💡 S3 Express提示:")
            print("   - 确保SageMaker端点在相同可用区部署")
            print("   - 享受更快的模型加载速度")
        
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
