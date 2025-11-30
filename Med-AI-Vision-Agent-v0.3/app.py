# server.py (Full Overwrite)

import os
import shutil
import traceback
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import json

from yolo_state import TEMP_DIR
import yolo_state
from yolo_image_processor import process_model_and_image
# 注意：process_video_entry 现在是一个生成器
from yolo_video_processor import process_video_entry
from qwen_chat import stream_qwen_response 
from report_generator import create_medical_report

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(TEMP_DIR, exist_ok=True)
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
REPORT_DIR = "reports"
os.makedirs(REPORT_DIR, exist_ok=True)

class MockFileObj:
    def __init__(self, path):
        self.name = path

def ensure_model_loaded():
    if yolo_state.current_model is None:
        yolo_state.load_model(None)

# --- APIs ---

@app.post("/api/upload_model")
async def upload_model(file: UploadFile = File(...)):
    try:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        result = yolo_state.load_model(MockFileObj(file_path))
        return {"status": result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": str(e)})

@app.post("/api/detect_image")
async def detect_image(files: List[UploadFile] = File(...)):
    try:
        ensure_model_loaded()
        saved_input_paths = []
        for file in files:
            path = os.path.join(UPLOAD_DIR, file.filename)
            with open(path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved_input_paths.append(path)
        
        current_model_mock = MockFileObj(yolo_state.current_model_path) if yolo_state.current_model_path else None
        _, text, conf, context_path, saved_output_paths = process_model_and_image(current_model_mock, saved_input_paths)
        
        results_urls = [f"/files/{os.path.basename(p)}" for p in saved_output_paths]
        return {
            "images": results_urls, "text": text, "conf": conf, 
            "context_path": context_path
        }
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"text": str(e)})

# 🔥 核心修改：流式视频接口
@app.post("/api/detect_video")
async def detect_video(file: UploadFile = File(...)):
    try:
        ensure_model_loaded()
        input_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        current_model_mock = MockFileObj(yolo_state.current_model_path) if yolo_state.current_model_path else None
        
        # 这里的生成器负责产生 SSE 数据流
        def video_stream_generator():
            generator = process_video_entry(current_model_mock, input_path)
            for chunk in generator:
                # 检查是否是结果数据，如果是，需要移动文件
                try:
                    data = json.loads(chunk)
                    if data["type"] == "result":
                        output_path = data["data"]["output_path"]
                        if output_path and os.path.exists(output_path):
                            filename = os.path.basename(output_path)
                            final_path = os.path.join(TEMP_DIR, filename)
                            if os.path.abspath(output_path) != os.path.abspath(final_path):
                                shutil.move(output_path, final_path)
                            # 更新 URL 给前端
                            data["data"]["video_url"] = f"/files/{filename}"
                            data["data"]["context_path"] = final_path
                            yield json.dumps(data) + "\n"
                        else:
                            yield json.dumps({"type": "error", "message": "Output file generation failed"}) + "\n"
                    else:
                        yield chunk # 进度或错误直接转发
                except:
                    yield chunk

        return StreamingResponse(video_stream_generator(), media_type="application/x-ndjson")

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

class ChatRequest(BaseModel):
    message: str
    history: List[List[str]] 
    context_path: Optional[str] = None

@app.post("/api/chat_stream")
async def chat_stream(request: ChatRequest):
    def robust_generator():
        try:
            formatted_history = []
            for h in request.history:
                if isinstance(h, list) and len(h) >= 2:
                    formatted_history.append((str(h[0]), str(h[1])))
            iterator = stream_qwen_response(request.message, formatted_history, request.context_path)
            for chunk in iterator:
                yield chunk
        except Exception as e:
            yield f" [System Error: {str(e)}]"
    return StreamingResponse(robust_generator(), media_type="text/plain")

@app.post("/api/generate_report")
async def generate_report(request: ChatRequest):
    try:
        formatted_history = [(h[0], h[1]) for h in request.history]
        report_path = create_medical_report(formatted_history, request.context_path)
        filename = os.path.basename(report_path)
        return {"report_url": f"/reports/{filename}"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# ----------------------------------------------------
# 挂载静态文件 (核心修改)
# ----------------------------------------------------

# 1. 挂载临时文件和报告 (API 使用)
app.mount("/files", StaticFiles(directory=TEMP_DIR), name="files")
app.mount("/reports", StaticFiles(directory=REPORT_DIR), name="reports")

# 2. 挂载前端构建文件 (网页使用)
# 确保你已经把 npm run build 生成的文件夹重命名为 frontend_build 并放在根目录
if os.path.exists("frontend_build"):
    app.mount("/", StaticFiles(directory="frontend_build", html=True), name="frontend")
else:
    print("⚠️ Warning: 'frontend_build' folder not found. Web UI will not be accessible.")

if __name__ == "__main__":
    # ModelScope 强制要求监听 0.0.0.0 和 端口 7860
    uvicorn.run(app, host="0.0.0.0", port=7860)