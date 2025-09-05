#!/usr/bin/env python3
"""
VLM模型下载脚本 - 从Hugging Face下载模型并上传到S3
"""

import os
import argparse
import shutil
from huggingface_hub import snapshot_download

# 支持的模型配置
SUPPORTED_MODELS = {
    "qwen2.5-vl-3b": "Qwen/Qwen2.5-VL-3B-Instruct",
    "qwen2.5-vl-7b": "Qwen/Qwen2.5-VL-7B-Instruct",
    "qwen2.5-vl-72b": "Qwen/Qwen2.5-VL-72B-Instruct"
}

def download_model(model_id, local_path):
    """从Hugging Face下载模型文件"""
    print(f"📥 下载模型: {model_id}")
    print(f"📁 本地保存: {local_path}")
    
    # 设置镜像源
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
    
    os.makedirs(local_path, exist_ok=True)
    
    # 重试机制
    import time
    max_retries = 3
    for attempt in range(max_retries):
        try:
            snapshot_download(
                repo_id=model_id,
                local_dir=local_path,
                max_workers=5,  # 多线程下载 (1线程=1文件)
            )
            print(f"✅ 下载完成: {local_path}")
            return
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠️ 下载失败，5秒后重试 ({attempt+1}/{max_retries}): {str(e)[:100]}")
                time.sleep(5)
            else:
                raise e

def upload_to_s3(local_path, s3_bucket, s3_prefix, region):
    """上传模型到S3 - 只上传SageMaker部署必需文件"""
    s3_path = f"s3://{s3_bucket}/{s3_prefix.rstrip('/')}"
    print(f"📤 上传到S3: {s3_path}")
    
    # SageMaker部署必需文件
    essential_files = [
        "config.json",
        "tokenizer.json", 
        "tokenizer_config.json",
        "generation_config.json",
        "preprocessor_config.json"  # VLM模型必需
    ]
    
    # 查找safetensors文件
    import glob
    safetensors_files = glob.glob(os.path.join(local_path, "*.safetensors"))
    index_files = glob.glob(os.path.join(local_path, "*.index.json"))
    
    # 统计要上传的文件
    upload_files = []
    for file in essential_files:
        file_path = os.path.join(local_path, file)
        if os.path.exists(file_path):
            upload_files.append(file)
    
    # 添加safetensors和index文件
    for file_path in safetensors_files + index_files:
        upload_files.append(os.path.basename(file_path))
    
    print(f"📋 上传文件: {len(upload_files)} 个")

    # 逐个上传文件
    import subprocess
    success_count = 0
    for i, file in enumerate(upload_files, 1):
        local_file = os.path.join(local_path, file)
        s3_file = f"{s3_path}/{file}"
        
        # 获取文件大小
        file_size = os.path.getsize(local_file)
        size_mb = file_size / (1024 * 1024)
        
        print(f"  - [{i}/{len(upload_files)}] 上传 {file} ({size_mb:.1f}MB)...")
        
        result = subprocess.run([
            "aws", "s3", "cp", local_file, s3_file,
            "--region", region
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            success_count += 1
            print(f"  ✅ 完成")
        else:
            print(f"  ❌ 失败: {result.stderr}")
    
    if success_count == len(upload_files):
        print(f"✅ 上传完成: {s3_path} ({success_count}个文件)")
        return s3_path
    else:
        raise Exception(f"部分文件上传失败: {success_count}/{len(upload_files)}")

def main():
    parser = argparse.ArgumentParser(description="下载VLM模型并上传到S3")
    parser.add_argument("--model", required=True, choices=list(SUPPORTED_MODELS.keys()), help="模型名称")
    parser.add_argument("--s3-bucket", required=True, help="S3存储桶名称")
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
            print(f"📁 模型文件保留在: {local_path}")
        
        # 4. 输出结果
        print("\n" + "=" * 60)
        print("🎉 模型下载和上传完成!")
        print("\n📝 在notebook中使用:")
        print(f'MODEL_S3_PATH = "{s3_path}"')
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
