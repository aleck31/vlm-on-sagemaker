#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generated from notebook: deploy_on_SageMaker_endpoint_lmi_vllm (5).ipynb
This script was auto-extracted. Lines starting with notebook magics or shell commands were commented out.
You may need to install packages manually before running.
"""

from datetime import datetime
import io
import os
import cv2
import numpy as np
from PIL import Image
import boto3
import sagemaker
from sagemaker import Model, deserializers, image_uris, serializers
import base64
import json

# ===== Notebook setup & helpers =====

# !pip install boto3
# !pip install sagemaker
import os
os.makedirs("lmi_config", exist_ok=True)
# (tar packaging skipped for invoke script)
from datetime import datetime


deploy_model_name = "qwen2-5-vl-7b-" + datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
print(deploy_model_name)

# !pip install torchvision
# !pip install pillow
# !pip install opencv-python

import io
import os

import cv2
import numpy as np
from PIL import Image


def resize_to_short_side(image: np.ndarray, short_side_length: int):
    height, width = image.shape[:2]
    if height < width:
        new_height = short_side_length
        new_width = int(new_height / height * width)
    else:
        new_width = short_side_length
        new_height = int(new_width / width * height)
    print(f"[Debug]resize image from {image.shape[:2]} to {new_width}x{new_height}")
    image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)
    return image


def load_and_resize_image_in_bytes(image_path: str):
    assert os.path.exists(image_path), f"Image not exists: {image_path}"
    image = cv2.imread(image_path)
    image = resize_to_short_side(image, short_side_length=1024)
    buffer = io.BytesIO()
    image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    image.save(buffer, format="PNG")
    encoded_image = buffer.getvalue()
    return encoded_image


# ===== Inference/invocation cells from notebook =====

import base64
import json

import boto3

import io
import os

import cv2
import numpy as np
from PIL import Image


def resize_to_short_side(image: np.ndarray, short_side_length: int):
    height, width = image.shape[:2]
    if height < width:
        new_height = short_side_length
        new_width = int(new_height / height * width)
    else:
        new_width = short_side_length
        new_height = int(new_width / width * height)
    print(f"[Debug]resize image from {image.shape[:2]} to {new_width}x{new_height}")
    image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)
    return image


def load_and_resize_image_in_bytes(image_path: str):
    assert os.path.exists(image_path), f"Image not exists: {image_path}"
    image = cv2.imread(image_path)
    # image = resize_to_short_side(image, short_side_length=720)
    image = cv2.resize(image,(1024,1024))
    buffer = io.BytesIO()
    image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    image.save(buffer, format="PNG")
    encoded_image = buffer.getvalue()
    return encoded_image

smr_client = boto3.client("sagemaker-runtime")
endpoint_name = "endpoint-qwen2-5-vl-7b-2025-08-21-08-32-08"

image_path = "cc_ocr_data/es/es_000000.jpg"
encoded_image = load_and_resize_image_in_bytes(image_path)
encoded_image_base64 = base64.b64encode(encoded_image).decode("utf-8")
image_url_base64 = f"data:image/png;base64,{encoded_image_base64}"

system_prompt = 'what is the text in the image?'

prompt = {
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": system_prompt},
                {"type": "image_url", "image_url": {"url": image_url_base64}}
            ],
        },
    ],
    "temperature": 0.0,
    "top_p": 0.8,
    "top_k": 20,
    "max_tokens": 64,
}
response = smr_client.invoke_endpoint(
    EndpointName=endpoint_name,
    # InferenceComponentName=inference_component_name_qwen,
    ContentType="application/json",
    Body=json.dumps(prompt),
)
response_dict = json.loads(response["Body"].read().decode("utf-8"))

print("VLM Output:")
print(response_dict["choices"][0]["message"]["content"])