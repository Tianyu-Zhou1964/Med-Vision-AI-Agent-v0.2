# yolo_video_processor.py (Full Overwrite)

import os
import numpy as np
import cv2
import traceback
import json
from collections import defaultdict
import yolo_state 

# ----------------------------------------------------
# Core Logic Function (Video with Generator)
# ----------------------------------------------------

def process_video_entry(pt_file_obj, input_video_path):
    """
    Generator function that streams progress and finally returns the result.
    Yields JSON strings:
    - {"type": "progress", "current": 10, "total": 100, "log": "Processing..."}
    - {"type": "result", "data": { ... }}
    - {"type": "error", "message": "..."}
    """
    
    # 1. Load Model
    load_status = yolo_state.load_model(pt_file_obj)
    if yolo_state.current_model is None:
        yield json.dumps({"type": "error", "message": f"Model load failed: {load_status}"})
        return

    if not input_video_path or not os.path.exists(input_video_path):
        yield json.dumps({"type": "error", "message": "Input video file not found."})
        return

    # 2. Setup Video Capture
    cap = cv2.VideoCapture(input_video_path)
    if not cap.isOpened():
        yield json.dumps({"type": "error", "message": "Could not open video file."})
        return
    
    # --- 修复 1：安全的参数读取 ---
    # .mov 文件有时候会返回 0 或者异常的 FPS，这里做兜底
    original_fps = cap.get(cv2.CAP_PROP_FPS)
    if original_fps is None or original_fps <= 0 or original_fps > 120:
        original_fps = 30.0 # 默认兜底值
        
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # 如果总帧数读不到，设为一个大数，避免进度条崩溃
    if total_frames <= 0:
        total_frames = 1000 
    
    # --- 策略：每 3 帧处理一次 (平衡速度和流畅度) ---
    FRAME_STEP = 3
    new_fps = original_fps / FRAME_STEP
    
    # 确保 FPS 至少为 1
    if new_fps < 1: 
        new_fps = 1
        
    # --- 修复 2：强制输出文件名必须是 .mp4 ---
    # 无论输入是 .mov 还是 .avi，输出统一为 .mp4 以保证浏览器兼容性
    base_name = os.path.splitext(os.path.basename(input_video_path))[0]
    output_video_path = os.path.join(os.path.dirname(input_video_path), f"{base_name}_processed.mp4")
    
    # --- 修复 3：关键的编码器选择 ---
    # 浏览器只认 H.264 (avc1)。
    # 尝试顺序：avc1 (最佳) -> h264 (备选) -> mp4v (兼容性差但通用)
    
    out = None
    codec_attempts = ['avc1', 'h264', 'mp4v']
    used_codec = ""

    for codec in codec_attempts:
        try:
            fourcc = cv2.VideoWriter_fourcc(*codec)
            temp_out = cv2.VideoWriter(output_video_path, fourcc, new_fps, (width, height))
            if temp_out.isOpened():
                out = temp_out
                used_codec = codec
                print(f"DEBUG: Successfully initialized video writer with codec: {codec}")
                break
        except Exception as e:
            print(f"DEBUG: Failed to init codec {codec}: {e}")
            continue

    if out is None or not out.isOpened():
        cap.release()
        yield json.dumps({"type": "error", "message": "Failed to initialize Video Writer (Codec issue)."})
        return

    frame_idx = 0
    processed_count = 0
    total_detections = 0
    class_counts = defaultdict(int)
    
    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            # --- 跳帧逻辑 ---
            if frame_idx % FRAME_STEP != 0:
                frame_idx += 1
                continue

            # --- 推理 ---
            # 增加 verbose=False 防止后台日志爆炸
            results = yolo_state.current_model.predict(source=frame, save=False, conf=0.25, verbose=False)
            result = results[0]
            
            # 绘图
            plotted_frame = result.plot()
            
            # 写入视频
            out.write(plotted_frame)
            
            # 统计
            det_count = len(result.boxes)
            total_detections += det_count
            if det_count > 0:
                class_indices = result.boxes.cls.cpu().numpy().astype(int).tolist()
                for cls_id in class_indices:
                    name = yolo_state.current_model.names.get(cls_id, str(cls_id))
                    class_counts[name] += 1

            # --- 实时 Yield 进度 ---
            progress_data = {
                "type": "progress",
                "current": frame_idx,
                "total": total_frames,
                "percent": min(int((frame_idx / total_frames) * 100), 99), # 保持在99直到完成
                "log": f"Processing frame {frame_idx}/{total_frames}..."
            }
            yield json.dumps(progress_data) + "\n"

            frame_idx += 1
            processed_count += 1

        # --- 循环结束 ---
        # 必须显式释放资源，否则文件尾部数据会丢失导致无法播放
        out.release() 
        cap.release()

        result_text = f"✨ Inference Complete!\n"
        result_text += f"Format: {used_codec.upper()} / .mp4\n"
        result_text += f"Processed Frames: {processed_count}\n"
        result_text += f"Total Detections: {total_detections}\n"
        
        if class_counts:
            result_text += "\n--- Details ---\n"
            for name, count in class_counts.items():
                result_text += f"{name}: {count}\n"

        final_data = {
            "type": "result",
            "data": {
                "output_path": output_video_path,
                "text": result_text,
                "fps": new_fps,
                # 关键：返回 context_path 用于后续问答
                "context_path": output_video_path 
            }
        }
        yield json.dumps(final_data) + "\n"

    except Exception as e:
        traceback.print_exc()
        if out: out.release()
        if cap: cap.release()
        yield json.dumps({"type": "error", "message": f"Processing error: {str(e)}"}) + "\n"