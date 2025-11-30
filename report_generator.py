# report_generator.py (覆盖此文件)

import os
from fpdf import FPDF
from datetime import datetime
from typing import List, Tuple
import markdown 
import re 
import traceback

REPORT_DIR = "reports"
os.makedirs(REPORT_DIR, exist_ok=True)

CHINESE_FONT_PATH = os.path.join(os.path.dirname(__file__), "NotoSansSC-Regular.ttf")
FONT_NAME = 'Chinese'
FONT_LOADED = False

class PDFReport(FPDF):
    def __init__(self, orientation='P', unit='mm', format='A4'):
        super().__init__(orientation, unit, format)
        global FONT_LOADED
        if os.path.exists(CHINESE_FONT_PATH):
            try:
                self.add_font(FONT_NAME, '', CHINESE_FONT_PATH, uni=True)
                self.add_font(FONT_NAME, 'B', CHINESE_FONT_PATH, uni=True)
                FONT_LOADED = True
            except Exception:
                pass

    def header(self):
        if FONT_LOADED:
            self.set_font(FONT_NAME, 'B', 15)
        else:
            self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'AI 医疗咨询报告 (AI Medical Report)', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', 0, 0, 'C')

def create_medical_report(chat_history: List[Tuple[str, str]], image_context_path: str) -> str:
    global FONT_LOADED
    pdf = PDFReport()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    font_style = FONT_NAME if FONT_LOADED else 'Arial'
    
    # 1. 报告信息
    pdf.set_font(font_style, 'B', 12)
    pdf.cell(0, 10, '1. 报告概览 (Overview)', 0, 1)
    
    pdf.set_font(font_style, '', 10)
    pdf.cell(0, 8, f'Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 1)
    
    if image_context_path and os.path.exists(image_context_path):
        file_name = os.path.basename(image_context_path)
        pdf.cell(0, 8, f'Image Analyzed: {file_name}', 0, 1)
        pdf.ln(2)
        
        # 修复重叠的核心逻辑：
        # 1. 记录当前 Y 坐标
        start_y = pdf.get_y()
        # 2. 放置图片，限制最大高度 100mm
        pdf.image(image_context_path, x=15, y=start_y, w=150)
        # 3. 手动计算图片实际占用的高度。这里假设宽度占满按比例缩放，
        # 为了安全起见，我们直接给足够的空间。
        pdf.set_y(start_y + 110) # 强制下移 110mm，确保不覆盖
    else:
        pdf.cell(0, 8, 'Image Analyzed: None', 0, 1)
    
    pdf.ln(10)

    # 2. 对话记录
    pdf.set_font(font_style, 'B', 12)
    pdf.cell(0, 10, '2. 详细对话 (Dialogue Details)', 0, 1)
    
    font_tag = f'<font face="{font_style}" size="10">'
    
    for user_msg, ai_msg in chat_history:
        # User
        pdf.set_text_color(0, 50, 160)
        user_html = font_tag + f'<b>Patient:</b> {user_msg}</font>'
        pdf.write_html(user_html)
        pdf.ln(5)

        # AI
        pdf.set_text_color(0, 0, 0)
        if ai_msg:
             # 处理 markdown 粗体
             ai_msg = ai_msg.replace('**', '') 
             ai_html = markdown.markdown(ai_msg)
             if ai_html.startswith('<p>'): ai_html = ai_html[3:-4]
             
             final_html = font_tag + f'<b>AI Assistant:</b> {ai_html}</font>'
             pdf.write_html(final_html)
        pdf.ln(8) # 段落间距

    pdf.ln(10)
    
    # 3. 免责
    pdf.set_font(font_style, 'B', 12)
    pdf.set_text_color(200, 0, 0)
    pdf.cell(0, 10, '3. 免责声明 (Disclaimer)', 0, 1)
    
    pdf.set_text_color(80, 80, 80)
    pdf.set_font(font_style, '', 9)
    disclaimer = "本报告仅供参考，不构成医疗诊断建议。请务必咨询专业医生。\nThis report is for reference only."
    pdf.multi_cell(0, 5, disclaimer)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f'report_{timestamp}.pdf'
    report_path = os.path.join(REPORT_DIR, report_filename)
    pdf.output(report_path)

    return report_path