# 使用 Python 3.10
FROM python:3.10

# 1. 安装系统依赖 (OpenCV 必须)
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 2. 创建用户 (HF 强制要求用户 ID 1000)
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# 3. 设置工作目录
WORKDIR /app

# 4. 复制依赖并安装
COPY --chown=user ./requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# 5. 复制所有代码和前端文件
COPY --chown=user . /app

# 6. 【关键】创建临时目录并给满权限 (777)
# 因为 HF 的 user 没权限在系统目录写文件，必须显式创建并授权
RUN mkdir -p /app/uploads /app/reports /app/temp_qwen_input \
    && chmod -R 777 /app/uploads \
    && chmod -R 777 /app/reports \
    && chmod -R 777 /app/temp_qwen_input

# 7. 设置 YOLO 下载模型的目录到用户空间，防止权限报错
ENV YOLO_CONFIG_DIR="/home/user/.config/Ultralytics"

# 8. 启动命令 (端口必须是 7860)
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "7860"]