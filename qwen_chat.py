# qwen_chat.py (请直接完整覆盖此文件)

import os
import requests
import base64
import json
from typing import List, Tuple, Iterator, Union

# ----------------------------------------------------
# 1. Configuration
# ----------------------------------------------------
QWEN_API_URL = "http://61.169.118.10:8000/chat" 

# ----------------------------------------------------
# 2. Helper Function
# ----------------------------------------------------
def encode_image_to_base64(image_path: str) -> str:
    if not image_path or not os.path.exists(image_path):
        return None
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None

# ----------------------------------------------------
# 3. Core Functionality
# ----------------------------------------------------

def stream_qwen_response(
    message: str, 
    chat_history: List[Tuple[str, str]], 
    context_path: Union[str, None],
) -> Iterator[str]:
    
    # 1. 准备图片
    image_base64_data = None
    if context_path:
        image_base64_data = encode_image_to_base64(context_path)

    # 2. 构建消息
    messages = []
    for h, a in chat_history:
        messages.append({"role": "user", "content": str(h), "image_base64": None})
        if a:
            messages.append({"role": "assistant", "content": str(a), "image_base64": None})
            
    messages.append({
        "role": "user", 
        "content": str(message), 
        "image_base64": image_base64_data 
    })

    payload = {
        "model": "qwen3-vl", 
        "messages": messages,
        "stream": True 
    }
    
    try:
        print(f"DEBUG: Sending request to {QWEN_API_URL}...")
        
        with requests.post(
            QWEN_API_URL, 
            headers={"Content-Type": "application/json"}, 
            json=payload,
            timeout=60, 
            stream=True
        ) as response:
            
            # 如果状态码不是 200，直接把错误吐给前端
            if response.status_code != 200:
                error_msg = f"❌ API Error: Status {response.status_code} - {response.text}"
                print(error_msg)
                yield error_msg
                return

            print("DEBUG: API connected, receiving stream...")

            # --- 核心修改：万能解析逻辑 ---
            for line in response.iter_lines():
                if not line:
                    continue
                    
                # 解码
                decoded_line = line.decode('utf-8', errors='ignore').strip()
                # 打印原始数据看看到底返回了啥（这行日志会救你的命）
                # print(f"RAW DATA: {decoded_line}") 
                
                if not decoded_line:
                    continue

                # 移除 data: 前缀（如果有）
                json_content = decoded_line
                if decoded_line.startswith('data:'):
                    json_content = decoded_line[5:].strip()

                # 跳过结束符
                if json_content == "[DONE]":
                    continue

                try:
                    # 尝试解析 JSON
                    chunk = json.loads(json_content)
                    
                    # 提取内容 (兼容多种字段名)
                    text = chunk.get("response", "") or chunk.get("content", "") or chunk.get("delta", "") or chunk.get("text", "")
                    
                    # 如果解析到了文字，yield 出去
                    if text:
                        yield text
                        
                except json.JSONDecodeError:
                    # 如果 JSON 解析失败，但只要不是空行，就直接当做文本返回！
                    # 这能防止因为格式不规范导致丢失信息
                    if len(decoded_line) > 0 and "{" not in decoded_line:
                         yield decoded_line
            
    except Exception as e:
        print(f"DEBUG: Connection Exception: {e}")
        yield f"[Connection Error: {str(e)}]"