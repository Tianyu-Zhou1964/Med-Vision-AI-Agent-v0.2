# yolo_image_processor.py

import os
import numpy as np
import cv2
import traceback
from collections import defaultdict

# 🚨 KEY CHANGE 1: Import the entire yolo_state module
from yolo_state import load_model, TEMP_DIR # Removed current_model
import yolo_state  # 👈 Import the entire module

# ----------------------------------------------------
# Core Logic Function (Image)
# ----------------------------------------------------

def run_inference(input_image_files: list, progress=None) -> tuple:
    """
    Performs batch inference on the input list of images and provides
    additional statistics for instance segmentation models.
    :return: (processed_images, result_text, avg_conf, last_processed_path, saved_output_paths)
    """
    
    # 兼容 Gradio 的 Progress，如果为 None 则创建一个空函数
    if progress is None:
        def progress(p, desc=None): pass

    # 🚨 KEY CHANGE 2: Access via yolo_state.current_model
    if yolo_state.current_model is None: # 👈 Change
        return [], "❌ Error: Please load a .pt model successfully first!", 0.0, None, []

    if not input_image_files:
        return [], "❌ Error: Please upload image files for detection!", 0.0, None, []

    # 兼容处理：支持 Gradio File 对象列表 或 字符串路径列表
    input_image_paths = []
    for f in input_image_files:
        if isinstance(f, str):
            input_image_paths.append(f)
        elif hasattr(f, 'name'):
            input_image_paths.append(f.name)

    total_images = len(input_image_paths)
    if total_images == 0:
        return [], "❌ Error: No valid image file paths found!", 0.0, None, []

    processed_images = []
    saved_output_paths = [] # 新增：保存生成文件的路径列表
    all_detections = []
    all_confs = []
    last_processed_path = None 
    class_counts = defaultdict(int)
    class_mask_areas = defaultdict(list)
    
    progress(0, desc=f"Initializing batch image inference (Total {total_images} images)...")

    try:
        for i, input_path in enumerate(input_image_paths):
            
            # 🚨 KEY CHANGE 3: Access via yolo_state.current_model
            results = yolo_state.current_model.predict( # 👈 Change
                source=input_path, 
                save=False, 
                conf=0.04, 
                verbose=False
            )
            
            result = results[0]
            processed_image_np = result.plot() 
            
            processed_image_rgb = cv2.cvtColor(processed_image_np, cv2.COLOR_BGR2RGB) 
            processed_images.append(processed_image_rgb) 
            
            temp_file_name = f"qwen_input_{os.path.basename(input_path)}"
            temp_path = os.path.join(TEMP_DIR, temp_file_name)
            cv2.imwrite(temp_path, processed_image_np) 
            last_processed_path = temp_path 
            saved_output_paths.append(temp_path)
            
            H, W, _ = processed_image_np.shape
            total_pixels = H * W
            
            num_detections = len(result.boxes)
            all_detections.append(num_detections)
            
            if num_detections > 0:
                confs = result.boxes.conf.cpu().numpy().tolist()
                all_confs.extend(confs)
                class_indices = result.boxes.cls.cpu().numpy().astype(int).tolist()
                
                if hasattr(result, 'masks') and result.masks is not None:
                    mask_data = result.masks.data.cpu().numpy()
                    
                    for j in range(num_detections):
                        class_id = class_indices[j]
                        # 🚨 KEY CHANGE 4: Access via yolo_state.current_model
                        class_name = yolo_state.current_model.names.get(class_id, f"Class {class_id}") # 👈 Change
                        class_counts[class_name] += 1
                        mask_area = mask_data[j].sum()
                        area_percentage = (mask_area / total_pixels) * 100 
                        class_mask_areas[class_name].append(area_percentage)
                else:
                    for class_id in class_indices:
                         # 🚨 KEY CHANGE 5: Access via yolo_state.current_model
                         class_name = yolo_state.current_model.names.get(class_id, f"Class {class_id}") # 👈 Change
                         class_counts[class_name] += 1
                        
            progress((i + 1) / total_images, desc=f"Processing image {i+1}/{total_images}...")

        progress(1, desc="Batch image processing complete, summarizing results...")
        
        total_detections = sum(all_detections)
        avg_conf = np.mean(all_confs).item() if all_confs else 0.0

        result_text = f"✨ Batch Inference Complete!\n"
        result_text += f"Images Processed: {total_images}\n"
        result_text += f"**Total Detections: {total_detections}**\n"
        result_text += f"Average Confidence: {avg_conf:.2f}\n"
        
        if class_counts:
            result_text += "\n--- Instance Segmentation Stats ---\n"
            sorted_counts = sorted(class_counts.items(), key=lambda item: item[1], reverse=True)
            
            for class_name, count in sorted_counts:
                area_stats = ""
                if class_name in class_mask_areas:
                    avg_area_pct = np.mean(class_mask_areas[class_name])
                    area_stats = f" | Avg Area Pct: {avg_area_pct:.2f}%"
                result_text += f"[{class_name}]: {count} times{area_stats}\n"

        # 修改返回值：增加 saved_output_paths
        return processed_images, result_text, float(avg_conf), last_processed_path, saved_output_paths

    except Exception as e:
        error_info = traceback.format_exc()
        print(f"Inference Error: {error_info}")
        return [], f"❌ Error during inference: {e}", 0.0, None, []


def process_model_and_image(pt_file: object, input_image_files: list, progress=None) -> tuple:
    """
    Main function: Responsible for model loading, state checking, and image inference call.
    :return: (processed_images, final_text, avg_conf, processed_image_path, saved_output_paths)
    """
    
    # load_model is imported from yolo_state, and it correctly modifies yolo_state.current_model
    load_status = load_model(pt_file) 
    
    if "load successful" not in load_status.lower() and "already loaded" not in load_status.lower():
        return [], load_status, 0.0, None, []

    # run_inference now correctly reads yolo_state.current_model
    processed_images, result_text, avg_conf, processed_image_path, saved_output_paths = run_inference(input_image_files, progress=progress)
    
    if not processed_images and "error:" in result_text.lower():
           final_text = f"【Model Status】{load_status}\n\n【Inference Error】{result_text}"
           return [], final_text, 0.0, None, []
    
    final_text = f"【Model Status】{load_status}\n\n{result_text}"
    
    return processed_images, final_text, avg_conf, processed_image_path, saved_output_paths