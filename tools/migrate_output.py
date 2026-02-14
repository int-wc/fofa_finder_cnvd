# -*- coding: utf-8 -*-
import os
import shutil
import re
from pathlib import Path
import logging
import sys

# 添加项目根目录到 sys.path，以便导入模块
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
sys.path.insert(0, str(project_root))

from fofa_finder.config import Config

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate_output(base_path: str):
    """
    迁移输出目录中的扁平文件夹到嵌套结构。
    """
    output_dir = Path(base_path)
    if not output_dir.exists():
        logger.error(f"输出目录不存在: {output_dir}")
        return

    logger.info(f"开始迁移目录: {output_dir}")

    # 获取所有项目，转换为列表以避免迭代时修改目录结构导致的问题
    items = list(output_dir.iterdir())
    
    for item in items:
        if not item.is_dir():
            continue
            
        dirname = item.name
        
        # 跳过 realtime 目录
        if dirname == "realtime":
            logger.info(f"跳过 realtime 目录: {dirname}")
            continue

        # 匹配 YYYYMMDD (8位数字)
        if re.match(r"^\d{8}$", dirname):
            year = dirname[:4]
            month = dirname[4:6]
            day = dirname[6:8]
            target_dir = output_dir / year / month / day
            logger.info(f"发现 YYYYMMDD 文件夹: {dirname} -> {target_dir}")
            move_contents(item, target_dir)
            
        # 匹配 YYYYMM (6位数字)
        elif re.match(r"^\d{6}$", dirname):
            year = dirname[:4]
            month = dirname[4:6]
            target_dir = output_dir / year / month
            logger.info(f"发现 YYYYMM 文件夹: {dirname} -> {target_dir}")
            move_contents(item, target_dir)
            
        # 匹配 YYYY (4位数字)
        elif re.match(r"^\d{4}$", dirname):
            # YYYY 文件夹保持原样，无需移动内容
            logger.info(f"保留 YYYY 文件夹: {dirname}")
            pass

def move_contents(src_dir: Path, dst_dir: Path):
    """
    移动源目录内容到目标目录，处理子文件夹合并。
    """
    # 避免源目录和目标目录相同
    if src_dir.resolve() == dst_dir.resolve():
        return

    # 创建目标目录
    dst_dir.mkdir(parents=True, exist_ok=True)
    
    # 遍历源目录内容
    for item in list(src_dir.iterdir()):
        src_path = item
        dst_path = dst_dir / item.name
        
        if item.is_dir():
            # 如果是目录 (如 raw_data, analysis_data)，需要合并
            if dst_path.exists():
                logger.info(f"合并子目录: {src_path.name}")
                move_contents(src_path, dst_path)
                try:
                    src_path.rmdir()
                except OSError:
                    pass
            else:
                # 目标不存在，直接移动
                logger.info(f"移动子目录: {src_path.name} -> {dst_path}")
                shutil.move(str(src_path), str(dst_path))
        else:
            # 如果是文件
            if dst_path.exists():
                logger.warning(f"文件已存在，跳过: {dst_path.name}")
            else:
                shutil.move(str(src_path), str(dst_path))

    # 尝试删除源目录 (如果为空)
    try:
        src_dir.rmdir()
        logger.info(f"删除源目录: {src_dir.name}")
    except OSError:
        logger.warning(f"源目录非空，无法删除: {src_dir.name}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate output directory structure.")
    parser.add_argument("output_dir", nargs="?", help="Path to the output directory")
    args = parser.parse_args()

    if args.output_dir:
        target_output_dir = Path(args.output_dir).resolve()
    else:
        target_output_dir = Path(Config.OUTPUT_DIR)
    
    if target_output_dir.exists():
        migrate_output(str(target_output_dir))
    else:
        logger.error(f"找不到目标输出目录: {target_output_dir}")
