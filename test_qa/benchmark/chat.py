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
RAGFlow 问答测试脚本

用于批量测试 RAGFlow 助手的问答能力，将问答结果保存到 JSON/JSONL 文件中。
支持 .json 和 .jsonl 两种格式。
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import List, Dict, Any

from ragflow_sdk import RAGFlow

from config import Config


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Config.EVAL_DIR / 'chat.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class RAGFlowChatTester:
    """RAGFlow 问答测试器"""

    def __init__(self, base_url: str, api_key: str, assistant_name: str):
        """
        初始化测试器

        Args:
            base_url: RAGFlow API 地址
            api_key: RAGFlow API 密钥
            assistant_name: 助手名称
        """
        self.base_url = base_url
        self.api_key = api_key
        self.assistant_name = assistant_name
        self.rag_client = None
        self.assistant = None

    def connect(self) -> None:
        """连接到 RAGFlow 并获取助手实例"""
        try:
            logger.info(f"正在连接到 RAGFlow: {self.base_url}")
            self.rag_client = RAGFlow(api_key=self.api_key, base_url=self.base_url)

            logger.info(f"正在查找助手: {self.assistant_name}")
            assistants = self.rag_client.list_chats(name=self.assistant_name)
            if not assistants:
                raise ValueError(f"未找到名为 '{self.assistant_name}' 的助手")

            self.assistant = assistants[0]
            logger.info(f"成功连接到助手: {self.assistant_name}")
        except Exception as e:
            logger.error(f"连接失败: {e}")
            raise

    def ask_question(self, question: str, retry_count: int = 3) -> str:
        """
        向助手提问

        Args:
            question: 问题内容
            retry_count: 重试次数

        Returns:
            助手的回答
        """
        for attempt in range(retry_count):
            try:
                session = self.assistant.create_session(name=f"test_session_{int(time.time())}")
                gen = session.ask(question=question, stream=False)

                try:
                    response = next(gen)
                except StopIteration as e:
                    response = e.value

                return response.content
            except Exception as e:
                logger.warning(f"第 {attempt + 1}/{retry_count} 次请求失败: {e}")
                if attempt < retry_count - 1:
                    time.sleep(2 ** attempt)  # 指数退避
                else:
                    raise

    def run_test(self, question_file: Path, output_file: Path, overwrite: bool = False) -> None:
        """
        运行批量测试

        Args:
            question_file: 问题文件路径（支持 .json 和 .jsonl 格式）
            output_file: 输出文件路径
            overwrite: 是否覆盖已有答案（默认 False，跳过已有答案）
        """
        # 加载问题数据
        logger.info(f"加载问题文件: {question_file}")
        data_list = self._load_data(question_file)

        total = len(data_list)
        logger.info(f"共加载 {total} 个问题")

        answer_key = f'{self.assistant_name}_answer'
        success_count = 0
        skip_count = 0
        error_count = 0

        # 处理每一条数据
        for i, data in enumerate(data_list, start=1):
            # 跳过已有答案的问题（除非设置了 overwrite）
            if not overwrite and answer_key in data:
                logger.info(f"[{i}/{total}] 跳过已回答的问题")
                skip_count += 1
                continue

            # 支持 query 或 question 字段
            question = data.get('query') or data.get('question', '')
            if not question:
                logger.warning(f"[{i}/{total}] 问题为空，跳过")
                error_count += 1
                continue

            file_name = data.get('file_name', '')
            logger.info(f"[{i}/{total}] 文件: {file_name} | 问题: {question}")

            try:
                # 获取答案
                answer = self.ask_question(question)
                data[answer_key] = answer
                logger.info(f"[{i}/{total}] 答案: {answer[:100]}...")

                # 保存进度
                self._save_data(output_file, data_list)

                success_count += 1

            except Exception as e:
                logger.error(f"[{i}/{total}] 处理失败: {e}")
                data[answer_key] = None
                error_count += 1

        # 输出统计信息
        logger.info("\n" + "="*50)
        logger.info("测试完成统计:")
        logger.info(f"  总问题数: {total}")
        logger.info(f"  成功回答: {success_count}")
        logger.info(f"  跳过问题: {skip_count}")
        logger.info(f"  失败问题: {error_count}")
        logger.info(f"  结果已保存到: {output_file}")
        logger.info("="*50)

    @staticmethod
    def _load_data(file_path: Path) -> List[Dict[str, Any]]:
        """
        加载数据文件（支持 .json 和 .jsonl 格式）

        Args:
            file_path: 文件路径

        Returns:
            数据列表
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            if file_path.suffix == '.jsonl':
                # JSONL 格式：每行一个 JSON 对象
                return [json.loads(line) for line in f if line.strip()]
            else:
                # JSON 格式：整个文件是一个 JSON 数组
                return json.load(f)

    @staticmethod
    def _save_data(file_path: Path, data_list: List[Dict[str, Any]]) -> None:
        """
        保存数据文件（根据扩展名自动选择格式）

        Args:
            file_path: 文件路径
            data_list: 数据列表
        """
        with open(file_path, 'w', encoding='utf-8') as f:
            if file_path.suffix == '.jsonl':
                # JSONL 格式：每行一个 JSON 对象
                for data in data_list:
                    f.write(json.dumps(data, ensure_ascii=False) + '\n')
            else:
                # JSON 格式：整个文件是一个 JSON 数组
                json.dump(data_list, f, ensure_ascii=False, indent=2)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='RAGFlow 问答测试脚本')
    parser.add_argument(
        '--assistant-name',
        type=str,
        default=Config.DEFAULT_ASSISTANT_NAME,
        help=f'RAGFlow 助手名称（默认: {Config.DEFAULT_ASSISTANT_NAME}）'
    )
    parser.add_argument(
        '--question-file',
        type=Path,
        help=f'问题文件路径（支持 .json 和 .jsonl 格式，默认: OmniDocBench/{Config.DEFAULT_QA_FILE}）'
    )
    parser.add_argument(
        '--output-file',
        type=Path,
        help=f'输出文件路径（默认: OmniDocBench/{Config.DEFAULT_OUTPUT_FILE}，不会覆盖原始 qa.jsonl）'
    )
    parser.add_argument(
        '--base-url',
        type=str,
        default=Config.RAGFLOW_BASE_URL,
        help=f'RAGFlow API 地址（默认: {Config.RAGFLOW_BASE_URL}）'
    )
    parser.add_argument(
        '--api-key',
        type=str,
        default=Config.RAGFLOW_API_KEY,
        help='RAGFlow API 密钥（或使用环境变量 RAGFLOW_API_KEY）'
    )
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='覆盖已有答案（默认跳过已有答案）'
    )
    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()

    # 验证 RAGFlow 配置
    try:
        Config.validate_ragflow_config()
    except ValueError as e:
        logger.error(f"配置错误: {e}")
        sys.exit(1)

    # 设置文件路径
    if args.question_file:
        question_file = args.question_file
    else:
        question_file = Config.EVAL_DIR / Config.DEFAULT_QA_FILE

    if not question_file.exists():
        logger.error(f"问题文件不存在: {question_file}")
        sys.exit(1)

    # 默认输出到 results.jsonl，避免覆盖原始 qa.jsonl
    output_file = args.output_file or (Config.EVAL_DIR / Config.DEFAULT_OUTPUT_FILE)

    # 创建测试器并运行
    try:
        tester = RAGFlowChatTester(
            base_url=args.base_url,
            api_key=args.api_key,
            assistant_name=args.assistant_name
        )
        tester.connect()
        tester.run_test(question_file, output_file, overwrite=args.overwrite)
    except Exception as e:
        logger.error(f"测试失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
