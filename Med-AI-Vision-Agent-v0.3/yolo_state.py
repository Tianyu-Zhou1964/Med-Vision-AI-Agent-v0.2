# yolo_state.py

import os
from ultralytics import YOLO

# ----------------------------------------------------
# 1. Configuration Constants
# ----------------------------------------------------
# Batch size: Adjust based on your hardware (especially VRAM) and desired performance
BATCH_SIZE = 16 

# 🚨 Temporary path used to store the single image required by Qwen3-VL
TEMP_DIR = "temp_qwen_input" 
# Ensure the directory exists (it is created automatically during Hugging Face Space deployment)
os.makedirs(TEMP_DIR, exist_ok=True) 

# 🚨 New default model constant
DEFAULT_MODEL_NAME = "yolo11n.pt"

# ----------------------------------------------------
# 2. Global State Management
# ----------------------------------------------------

# Global variable to store the loaded model, preventing reloading on every click
current_model: YOLO = None
current_model_path: str = ""

# ----------------------------------------------------
# 3. Model Loading Function
# ----------------------------------------------------

def load_model(pt_file: object) -> str:
    """
    Loads the YOLO model based on the uploaded file path.
    If no file is uploaded, it attempts to load the default model yolo11n.pt.
    
    :param pt_file: The object returned by the Gradio File component or a Mock object with .name attribute.
    :return: State information string.
    """
    global current_model, current_model_path
    
    # ----------------------------------------------------
    # 🚨 KEY CHANGE: Handling the case where pt_file is None
    # ----------------------------------------------------
    if pt_file is None:
        new_model_path = os.path.join(os.path.dirname(__file__), DEFAULT_MODEL_NAME)
        
        # Check if the default model file exists
        if not os.path.exists(new_model_path):
             return f"Please upload a model file (.pt), or place the default model {DEFAULT_MODEL_NAME} in the same directory!"
        
        # If a different model is currently loaded, and the user hasn't uploaded a new file, 
        # we load the default model as requested (unless the current one is already the default).
        
        # Avoid reloading the same default model
        if new_model_path == current_model_path and current_model is not None:
             return f"Model {DEFAULT_MODEL_NAME} (default) is already loaded."
        
        # Otherwise, proceed to load the default model
        model_source_desc = f"Default Model {DEFAULT_MODEL_NAME}"

    else:
        # 兼容处理：如果传入的是对象则取.name，如果是字符串则直接使用
        if hasattr(pt_file, 'name'):
            new_model_path = pt_file.name
        else:
            new_model_path = str(pt_file)

        model_source_desc = os.path.basename(new_model_path)
        
        # Avoid reloading the same uploaded model
        if new_model_path == current_model_path and current_model is not None:
            return f"Model {model_source_desc} is already loaded."


    try:
        # Load the YOLO model
        current_model = YOLO(new_model_path)
        current_model_path = new_model_path
        return f"✅ Model {model_source_desc} loaded successfully!"
    except Exception as e:
        current_model = None
        current_model_path = ""
        # Return a unified failure message
        return f"❌ Model loading failed ({model_source_desc}): {e}"