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
LLM 评分脚本

使用大语言模型对 RAGFlow 的问答结果进行质量评估，输出评分报告。
支持 .json 和 .jsonl 两种格式。
"""

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

import requests

from config import Config


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Config.EVAL_DIR / 'score.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class LLMScorer:
    """LLM 评分器"""

    def __init__(self, api_url: str, model: str, api_key: str):
        """
        初始化评分器

        Args:
            api_url: LLM API 地址
            model: 模型名称
            api_key: API 密钥
        """
        self.api_url = api_url
        self.model = model
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

    @staticmethod
    def extract_json(text: str) -> Dict[str, Any]:
        """
        从 LLM 响应中提取 JSON

        Args:
            text: LLM 返回的文本

        Returns:
            解析后的 JSON 字典
        """
        # 去除代码块标记
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        # 提取 JSON 内容
        match = re.search(r'\{[\s\S]*\}', text)
        if not match:
            raise ValueError("未找到有效 JSON 格式")

        json_str = match.group(0)
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            raise

        # 标准化数值格式
        if "details" in data:
            for key in data["details"]:
                data["details"][key] = round(float(data["details"][key]), 2)
        if "score" in data:
            data["score"] = round(float(data["score"]), 2)

        return data

    def build_score_prompt(self, question: str, reference_answer: str, actual_answer: str) -> str:
        """
        构建评分提示词

        Args:
            question: 问题
            reference_answer: 参考答案
            actual_answer: 实际答案

        Returns:
            评分提示词
        """
        weights = Config.SCORING_WEIGHTS
        return f"""# 任务
请根据以下维度评估回答质量：
问题：{question}
参考回答：{reference_answer}
实际回答：{actual_answer}

# 要求
1. 事实准确性：回答是否包含问题相关的核心事实和数据（权重{weights['accuracy']}%）
2. 信息完整性：是否覆盖参考回答的关键要素（权重{weights['completeness']}%）
3. 表述清晰度：信息组织是否逻辑清晰（权重{weights['clarity']}%）

说明：
- 满分100分
- 无有效信息和存在明显误导性内容时直接评0分
- 数值误差超过±5%时扣减该项50%分数
- **务必仅输出 JSON 内容，不要添加任何说明或注释**

# 输出格式
请严格按照以下 JSON 格式输出（不要添加反引号、说明）：
{{
  "score": 综合评分,
  "details": {{
    "accuracy": 事实得分,
    "completeness": 完整得分,
    "clarity": 清晰得分
  }},
  "error_reason": 扣分说明
}}
"""

    def score_answer(self, question: str, reference_answer: str, actual_answer: str) -> Optional[Dict[str, Any]]:
        """
        对单个答案进行评分

        Args:
            question: 问题
            reference_answer: 参考答案
            actual_answer: 实际答案

        Returns:
            评分结果字典，失败返回 None
        """
        prompt = self.build_score_prompt(question, reference_answer, actual_answer)
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "stream": False
        }

        for attempt in range(Config.MAX_RETRIES):
            try:
                response = requests.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload,
                    timeout=Config.REQUEST_TIMEOUT
                )
                response.raise_for_status()
                result = response.json()
                content = result['choices'][0]['message']['content']
                return self.extract_json(content)
            except Exception as e:
                logger.warning(f"第 {attempt + 1}/{Config.MAX_RETRIES} 次请求失败: {e}")
                if attempt < Config.MAX_RETRIES - 1:
                    delay = Config.RETRY_DELAY * ((attempt + 1) ** 2)
                    logger.info(f"等待 {delay} 秒后重试...")
                    time.sleep(delay)
                else:
                    logger.error("所有重试均失败")
                    return None

    def run_scoring(self, data_file: Path, answer_keys: List[str], overwrite: bool = False, show_comparison: bool = False) -> None:
        """
        运行批量评分

        Args:
            data_file: 数据文件路径（支持 .json 和 .jsonl 格式）
            answer_keys: 要评分的答案键列表
            overwrite: 是否覆盖已有评分（默认 False）
            show_comparison: 是否显示对比报告（默认 False）
        """
        # 加载数据
        logger.info(f"加载数据文件: {data_file}")
        data_list = self._load_data(data_file)

        total = len(data_list)
        logger.info(f"共加载 {total} 条数据")

        if overwrite:
            logger.info("覆盖模式已启用：将重新评分所有项")
        else:
            logger.info("跳过模式已启用：将跳过已有评分的项")

        # 评分统计
        stats = {key: {"sum": 0.0, "count": 0, "success": 0, "skip": 0, "fail": 0, "scores": []} for key in answer_keys}

        # 对比模式：仅读取已有评分，不调用 LLM API
        if show_comparison:
            logger.info("对比模式：读取已有评分数据...")
            for i, data in enumerate(data_list, start=1):
                for answer_key in answer_keys:
                    score_key = f"{answer_key}评分"

                    if score_key in data and data[score_key]:
                        # 读取已有评分
                        score_result = data[score_key]
                        if isinstance(score_result, dict) and "score" in score_result:
                            score_value = score_result["score"]
                            stats[answer_key]["sum"] += score_value
                            stats[answer_key]["count"] += 1
                            stats[answer_key]["success"] += 1
                            stats[answer_key]["scores"].append(score_value)
                        else:
                            stats[answer_key]["fail"] += 1
                    else:
                        # 没有评分数据，记为 0 分
                        stats[answer_key]["count"] += 1
                        stats[answer_key]["scores"].append(0)
                        logger.warning(f"[{i}/{total}] {answer_key} - 无评分数据，记为 0 分")
        else:
            # 默认模式：调用 LLM API 评分
            for i, data in enumerate(data_list, start=1):
                for answer_key in answer_keys:
                    score_key = f"{answer_key}评分"

                    # 根据 overwrite 参数决定是否跳过已评分项
                    if not overwrite and score_key in data:
                        logger.info(f"[{i}/{total}] {answer_key} - 已有评分，跳过")
                        stats[answer_key]["skip"] += 1
                        continue

                    # 获取问题和答案（支持 query 或 question 字段）
                    question = data.get("query") or data.get("question", "")
                    reference_answer = data.get("answer", "")
                    actual_answer = data.get(answer_key, "")

                    if not actual_answer:
                        logger.warning(f"[{i}/{total}] {answer_key} - 无实际答案，跳过")
                        data[score_key] = None
                        stats[answer_key]["fail"] += 1
                        continue

                    file_name = data.get('file_name', '')
                    logger.info(f"[{i}/{total}] 文件: {file_name} | 评分 {answer_key}...")

                    # 调用 LLM 评分
                    try:
                        score_result = self.score_answer(question, reference_answer, actual_answer)
                        if score_result:
                            data[score_key] = score_result
                            score_value = score_result["score"]
                            stats[answer_key]["sum"] += score_value
                            stats[answer_key]["count"] += 1
                            stats[answer_key]["success"] += 1
                            stats[answer_key]["scores"].append(score_value)  # 保存分数用于区间统计
                            logger.info(f"[{i}/{total}] {answer_key} - 得分: {score_value}")
                        else:
                            data[score_key] = None
                            stats[answer_key]["fail"] += 1
                    except Exception as e:
                        logger.error(f"[{i}/{total}] {answer_key} - 评分失败: {e}")
                        data[score_key] = None
                        stats[answer_key]["fail"] += 1

                    # 保存进度
                    self._save_data(data_file, data_list)

                    # 限流
                    time.sleep(Config.RATE_LIMIT_DELAY)

        # 输出统计报告
        self.print_report(stats, total, show_comparison)

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

    @staticmethod
    def detect_answer_keys(data_list: List[Dict[str, Any]]) -> List[str]:
        """
        自动检测数据中的所有答案键（*_answer 格式）

        Args:
            data_list: 数据列表

        Returns:
            答案键列表
        """
        answer_keys = set()
        for data in data_list:
            for key in data.keys():
                if key.endswith('_answer'):
                    answer_keys.add(key)

        answer_keys = sorted(list(answer_keys))
        logger.info(f"自动检测到 {len(answer_keys)} 个助手答案: {', '.join(answer_keys)}")
        return answer_keys

    @staticmethod
    def print_report(stats: Dict[str, Dict[str, Any]], total: int, show_comparison: bool = False) -> None:
        """
        打印评分报告

        Args:
            stats: 统计数据
            total: 总数据量
            show_comparison: 是否显示对比报告
        """
        logger.info("\n" + "="*60)
        logger.info("评分统计报告")
        logger.info("="*60)

        # 对比模式：生成纵向对比表格（每行一个助手）
        if show_comparison and len(stats) > 1:
            logger.info("\n【多助手对比报告】")

            # 定义分数区间用于计算百分比（从大到小）
            ranges = [
                ("100", 100, 100),
                ("80-99", 80, 99),
                ("60-79", 60, 79),
                ("1-59", 1, 59),
                ("0", 0, 0)
            ]

            # 构建表头
            header = f"| {'助手名称':<20} | {'总数':>5} | {'成功':>5} | {'平均分':>6} | {'100':>5} | {'80-99':>6} | {'60-79':>6} | {'1-59':>6} | {'0':>4} |"
            separator = f"|{'-'*22}|{'-'*7}|{'-'*7}|{'-'*8}|{'-'*7}|{'-'*8}|{'-'*8}|{'-'*8}|{'-'*6}|"

            logger.info(header)
            logger.info(separator)

            # 输出每个助手的数据
            for answer_key, stat in stats.items():
                # 截取助手名称（去掉 _answer 后缀）
                short_name = answer_key.replace('_answer', '')[:20]

                avg_score = stat["sum"] / stat["count"] if stat["count"] > 0 else 0
                scores = stat["scores"]
                success_count = stat["success"]

                if scores:
                    total_scores = len(scores)

                    # 计算各区间百分比
                    percentages = []
                    for _, min_score, max_score in ranges:
                        if min_score == max_score:  # 100分和0分单独统计
                            count = sum(1 for s in scores if s == min_score)
                        else:
                            count = sum(1 for s in scores if min_score <= s <= max_score)
                        percentage = (count / total_scores * 100) if total_scores > 0 else 0
                        percentages.append(percentage)

                    # 构建数据行：100和0列宽度较小，其他列宽度为6
                    row = f"| {short_name:<20} | {total:>5} | {success_count:>5} | {avg_score:>6.2f} | {percentages[0]:>4.1f}% | {percentages[1]:>5.1f}% | {percentages[2]:>5.1f}% | {percentages[3]:>5.1f}% | {percentages[4]:>3.1f}% |"

                    logger.info(row)
                else:
                    logger.info(f"| {short_name:<20} | {total:>5} | {0:>5} | {0:>6.2f} | {0:>4.1f}% | {0:>5.1f}% | {0:>5.1f}% | {0:>5.1f}% | {0:>3.1f}% |")

        else:
            # 默认模式：详细报告
            for answer_key, stat in stats.items():
                logger.info(f"\n【{answer_key}】")
                logger.info(f"  总数据量: {total}")
                logger.info(f"  成功评分: {stat['success']}")
                logger.info(f"  跳过评分: {stat['skip']}")
                logger.info(f"  评分失败: {stat['fail']}")

                # 分数区间分布
                scores = stat["scores"]
                if scores:
                    logger.info(f"\n  分数区间分布:")

                    # 定义分数区间
                    ranges = [
                        ("不及格(<60)", 0, 60),
                        ("及格(60-70)", 60, 70),
                        ("中等(70-80)", 70, 80),
                        ("良好(80-90)", 80, 90),
                        ("优秀(90-100)", 90, 100)
                    ]

                    # 统计各区间数量
                    total_scores = len(scores)
                    logger.info(f"  | {'区间':<15} | {'数量':>6} | {'百分比':>8} |")
                    logger.info(f"  |{'-'*17}|{'-'*8}|{'-'*10}|")

                    for range_name, min_score, max_score in ranges:
                        count = sum(1 for s in scores if min_score <= s < max_score or (max_score == 100 and s == 100))
                        percentage = (count / total_scores * 100) if total_scores > 0 else 0
                        logger.info(f"  | {range_name:<15} | {count:>6} | {percentage:>7.1f}% |")

        logger.info("\n" + "="*60)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='LLM 评分脚本')
    parser.add_argument(
        '--data-file',
        type=Path,
        default=None,
        help=f'包含问答数据的文件路径（支持 .json 和 .jsonl 格式，默认: OmniDocBench/{Config.DEFAULT_OUTPUT_FILE}）'
    )
    parser.add_argument(
        '--compare',
        action='store_true',
        help=f'生成多助手对比报告（默认：仅输出各助手详细统计）'
    )
    parser.add_argument(
        '--api-url',
        type=str,
        default=Config.LLM_API_URL,
        help=f'LLM API 地址（默认: {Config.LLM_API_URL}）'
    )
    parser.add_argument(
        '--model',
        type=str,
        default=Config.LLM_MODEL,
        help=f'LLM 模型名称（默认: {Config.LLM_MODEL}）'
    )
    parser.add_argument(
        '--api-key',
        type=str,
        default=Config.LLM_API_KEY,
        help='LLM API 密钥（或使用环境变量 LLM_API_KEY）'
    )
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='覆盖已有评分（默认：跳过已评分项）'
    )
    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()

    # 验证 LLM 配置
    try:
        Config.validate_llm_config()
    except ValueError as e:
        logger.error(f"配置错误: {e}")
        sys.exit(1)

    # 设置默认值（默认读取 results.jsonl）
    if args.data_file is None:
        data_file = Config.EVAL_DIR / Config.DEFAULT_OUTPUT_FILE
    else:
        data_file = args.data_file

    # 验证数据文件
    if not data_file.exists():
        logger.error(f"数据文件不存在: {data_file}")
        sys.exit(1)

    # 加载数据并检测所有助手
    data_list = LLMScorer._load_data(data_file)
    all_answer_keys = LLMScorer.detect_answer_keys(data_list)

    if not all_answer_keys:
        logger.error("未检测到任何助手答案（*_answer 格式）")
        sys.exit(1)

    # 确定要评分的答案键（自动评分所有助手）
    answer_keys = all_answer_keys

    if args.compare:
        logger.info(f"对比模式：将评分 {len(answer_keys)} 个助手并生成对比报告")
    else:
        logger.info(f"默认模式：自动评分所有未评分的助手（共 {len(answer_keys)} 个）")

    # 创建评分器并运行
    try:
        scorer = LLMScorer(
            api_url=args.api_url,
            model=args.model,
            api_key=args.api_key
        )
        scorer.run_scoring(data_file, answer_keys, overwrite=args.overwrite, show_comparison=args.compare)
    except Exception as e:
        logger.error(f"评分失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
