# -*- coding: utf-8 -*-
import logging
import sys
import os
import wcwidth
from colorama import init, Fore, Style
from ..config import Config

import re

# 初始化 colorama
init(autoreset=True)

class TableFormatter(logging.Formatter):
    """
    表格样式的日志格式化器
    """
    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT,
    }
    
    # 边框字符
    BORDER_V = "│"
    
    # ANSI Color Code Regex
    ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    def __init__(self, fmt=None, datefmt=None):
        super().__init__(fmt, datefmt)
        # 打印表头 (只打印一次，可以通过全局变量控制，或者在 setup_logger 中打印)
        # 这里为了简单，不打印表头，只保证每行像表格的一行

    def strip_ansi(self, text):
        return self.ANSI_ESCAPE.sub('', text)

    def get_display_width(self, text):
        """
        使用 wcwidth 计算字符串的实际显示宽度 (忽略颜色代码)
        """
        clean_text = self.strip_ansi(text)
        return wcwidth.wcswidth(clean_text)

    def pad_text(self, text, width):
        """
        填充文本以达到指定的显示宽度
        """
        current_width = self.get_display_width(text)
        padding_len = max(0, width - current_width)
        return text + " " * padding_len

    def format(self, record):
        # 1. 时间 (固定 12)
        asctime = self.formatTime(record, "%H:%M:%S")
        # 2. 级别 (固定 12)
        levelname = record.levelname
        level_color = self.COLORS.get(levelname, "")
        levelname_padded = f"{levelname:<8}"
        
        # 3. 模块名 (固定 16)
        name = record.name
        if len(name) > 12:
            name = name[:12]
        name_padded = f"{name:<12}"
        
        # 4. 消息 (固定 120, 单行截断)
        message = record.getMessage()
        # 清理换行符
        message = message.replace('\n', ' ').replace('\r', '')
        max_msg_width = 122 # Increased to match header calculation
        
        # 严格按视觉宽度截断
        current_width = 0
        truncated_msg = ""
        for char in message:
            char_width = wcwidth.wcwidth(char)
            if char_width < 0: char_width = 0
            
            if current_width + char_width > max_msg_width - 3: # 预留 ...
                truncated_msg += "..."
                break
            
            truncated_msg += char
            current_width += char_width
        
        # 填充对齐
        message_padded = self.pad_text(truncated_msg, max_msg_width)
        
        # 组合单行表格
        # Header widths: Time=12, Level=12, Module=16, Message=122
        formatted_line = (
            f"{self.BORDER_V}  {Fore.CYAN}{asctime}{Style.RESET_ALL}  "
            f"{self.BORDER_V}  {level_color}{levelname_padded}{Style.RESET_ALL}  "
            f"{self.BORDER_V}  {Fore.MAGENTA}{name_padded}{Style.RESET_ALL}  "
            f"{self.BORDER_V} {message_padded} {self.BORDER_V}"
        )
        
        return formatted_line

# 全局变量控制表头是否已打印
_header_printed = False

def print_header():
    global _header_printed
    if not _header_printed:
        # 统一表头宽度
        # Time: 12 (10 inner + 2 padding)
        # Level: 12 (8 inner + 2 padding + 2 extra?) -> Actually format uses 8 padded + 2 spaces = 10 inner. Wait.
        # Let's align with format() strictly.
        # Format: "│  HH:MM:SS  │  LEVEL     │  MODULE      │ MESSAGE... │"
        # Spacing:
        # │__ (2)
        # TIME (8)
        # __│__ (5)
        # LEVEL (8)
        # __│__ (5)
        # MODULE (12)
        # __│_ (4)
        # MESSAGE (122)
        # _│ (2)
        
        # Total line length: 2+8+5+8+5+12+4+122+2 = 168 chars (visual)
        
        # Line 1 (Top Border)
        # ┌───...
        # Time col (12 chars total width including padding): 10 dashes? No.
        # Let's just hardcode the visual separator based on format()
        
        # Time col: "  HH:MM:SS  " -> 12 chars
        # Level col: "  LEVEL     " -> 12 chars
        # Module col: "  MODULE      " -> 16 chars
        # Message col: " MESSAGE... " -> 124 chars (1 space + 122 content + 1 space)
        
        # Border
        print("┌" + "─"*12 + "┬" + "─"*12 + "┬" + "─"*16 + "┬" + "─"*124 + "┐")
        print("│" + " Time ".center(12) + "│" + " Level ".center(12) + "│" + " Module ".center(16) + "│" + " Message ".center(124) + "│")
        print("├" + "─"*12 + "┼" + "─"*12 + "┼" + "─"*16 + "┼" + "─"*124 + "┤")
        
        _header_printed = True

def setup_logger(name):
    # 如果已经存在同名 logger 且有 handlers，直接返回
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
        
    logger.setLevel(logging.DEBUG) # Set logger level to DEBUG to capture everything
    
    # 打印表头 (如果还没打印)
    print_header()
    
    # Console Handler (Table Style) - Keep INFO for cleaner console
    console_formatter = TableFormatter(datefmt="%H:%M:%S")
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(console_formatter)
    ch.setLevel(logging.INFO) 
    logger.addHandler(ch)
    
    # File Handler (Plain text, DEBUG level for full details)
    # Ensure log dir exists
    log_dir = os.path.dirname(Config.LOG_FILE)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    file_formatter = logging.Formatter(Config.LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
    fh = logging.FileHandler(Config.LOG_FILE, encoding='utf-8')
    fh.setFormatter(file_formatter)
    fh.setLevel(logging.DEBUG) 
    logger.addHandler(fh)
    
    return logger
