#
#  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

"""
图片转PDF工具

用于将图片批量转换为PDF格式，以便使用Textin进行解析。
"""

import argparse
import logging
import sys
from pathlib import Path

from PIL import Image


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


# 支持的图片格式
SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}


def is_image_file(file_path: Path) -> bool:
    """判断是否为支持的图片文件"""
    return file_path.suffix.lower() in SUPPORTED_FORMATS


def convert_image_to_pdf(image_path: Path, output_path: Path) -> bool:
    """
    将单个图片转换为PDF

    Args:
        image_path: 图片文件路径
        output_path: 输出PDF文件路径

    Returns:
        是否转换成功
    """
    try:
        # 打开图片
        image = Image.open(image_path)

        # 转换为RGB模式（PDF需要）
        if image.mode in ('RGBA', 'LA', 'P'):
            # 创建白色背景
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')

        # 保存为PDF
        image.save(output_path, 'PDF', resolution=100.0)
        logger.info(f"✓ {image_path.name} -> {output_path.name}")
        return True

    except Exception as e:
        logger.error(f"✗ {image_path.name} 转换失败: {e}")
        return False


def batch_convert(input_dir: Path, output_dir: Path):
    """
    批量转换目录中的图片

    Args:
        input_dir: 输入图片目录
        output_dir: 输出PDF目录
    """
    # 验证输入目录
    if not input_dir.is_dir():
        logger.error(f"输入路径不是有效的目录: {input_dir}")
        sys.exit(1)

    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)

    # 查找所有图片文件
    image_files = [f for f in input_dir.glob('*') if f.is_file() and is_image_file(f)]

    if not image_files:
        logger.warning(f"目录中没有找到支持的图片文件: {input_dir}")
        return

    logger.info(f"找到 {len(image_files)} 个图片文件")
    logger.info("="*50)

    # 批量转换
    success_count = 0
    error_count = 0

    for i, image_path in enumerate(image_files, start=1):
        logger.info(f"[{i}/{len(image_files)}] 正在转换: {image_path.name}")
        output_path = output_dir / f"{image_path.stem}.pdf"

        if convert_image_to_pdf(image_path, output_path):
            success_count += 1
        else:
            error_count += 1

    # 输出统计
    logger.info("="*50)
    logger.info("转换完成统计:")
    logger.info(f"  总文件数: {len(image_files)}")
    logger.info(f"  成功转换: {success_count}")
    logger.info(f"  转换失败: {error_count}")
    logger.info(f"  输出目录: {output_dir}")
    logger.info("="*50)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='图片转PDF工具 - 批量将图片转换为PDF以便Textin解析',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python img2pdf.py --input OmniDocBench/images/ --output OmniDocBench/pdfs/

支持的图片格式:
  JPG, JPEG, PNG, BMP, TIFF, TIF, WEBP
        """
    )
    parser.add_argument(
        '--input',
        type=Path,
        required=True,
        help='输入图片目录'
    )
    parser.add_argument(
        '--output',
        type=Path,
        required=True,
        help='输出PDF目录'
    )

    args = parser.parse_args()

    # 执行批量转换
    batch_convert(args.input, args.output)
    logger.info("\n✓ 所有转换任务完成")


if __name__ == "__main__":
    main()
