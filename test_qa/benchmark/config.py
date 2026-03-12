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

import os
from pathlib import Path


class Config:
    """测试配置类"""

    # ==================== RAGFlow 配置（运行 chat.py 时必填） ====================
    RAGFLOW_BASE_URL = os.getenv("RAGFLOW_BASE_URL", "")              # RAGFlow 服务地址
    RAGFLOW_API_KEY = os.getenv("RAGFLOW_API_KEY", "")                # RAGFlow API 密钥
    DEFAULT_ASSISTANT_NAME = os.getenv("RAGFLOW_ASSISTANT_NAME", "")  # 默认助手名称

    # ==================== LLM 评分配置（运行 score.py 时必填） ====================
    LLM_API_URL = os.getenv("LLM_API_URL", "")  # LLM API 地址，例如: http://your-llm-api/v1/chat/completions
    LLM_MODEL = os.getenv("LLM_MODEL", "")      # LLM 模型名称，例如: gpt-4, gpt-5.2
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")  # LLM API 密钥

    # ==================== 文件路径配置 ====================

    BASE_DIR = Path(__file__).parent
    EVAL_DIR = BASE_DIR / "OmniDocBench"

    # 确保目录存在
    EVAL_DIR.mkdir(parents=True, exist_ok=True)

    # 默认文件路径
    DEFAULT_QA_FILE = "qa.jsonl"          # 原始问答数据文件
    DEFAULT_OUTPUT_FILE = "results.jsonl"  # 输出结果文件（不覆盖原始文件）

    # ==================== 重试配置 ====================

    MAX_RETRIES = 3           # 最大重试次数
    RETRY_DELAY = 60          # 重试延迟（秒）
    REQUEST_TIMEOUT = 120     # 请求超时（秒）
    RATE_LIMIT_DELAY = 2      # 请求间隔（秒）

    # ==================== 评分配置 ====================

    SCORING_WEIGHTS = {
        "accuracy": 50,       # 事实准确性权重
        "completeness": 30,   # 信息完整性权重
        "clarity": 20         # 表述清晰度权重
    }

    @classmethod
    def validate_ragflow_config(cls):
        """验证 RAGFlow 配置（运行 chat.py 时需要）"""
        missing = []

        if not cls.RAGFLOW_BASE_URL:
            missing.append("RAGFLOW_BASE_URL")
        if not cls.RAGFLOW_API_KEY:
            missing.append("RAGFLOW_API_KEY")
        if not cls.DEFAULT_ASSISTANT_NAME:
            missing.append("DEFAULT_ASSISTANT_NAME")

        if missing:
            raise ValueError(
                f"RAGFlow 配置缺失，请设置以下环境变量或在 config.py 中配置:\n"
                f"  - {', '.join(missing)}\n\n"
                f"示例:\n"
                f"  export RAGFLOW_BASE_URL='https://ragflow.intsig.net'\n"
                f"  export RAGFLOW_API_KEY='ragflow-xxxxx'\n"
                f"  export RAGFLOW_ASSISTANT_NAME='textin_assistant'"
            )

    @classmethod
    def validate_llm_config(cls):
        """验证 LLM 配置（运行 score.py 时需要）"""
        missing = []

        if not cls.LLM_API_URL:
            missing.append("LLM_API_URL")
        if not cls.LLM_MODEL:
            missing.append("LLM_MODEL")
        if not cls.LLM_API_KEY:
            missing.append("LLM_API_KEY")

        if missing:
            raise ValueError(
                f"LLM 配置缺失，请设置以下环境变量或在 config.py 中配置:\n"
                f"  - {', '.join(missing)}\n\n"
                f"示例:\n"
                f"  export LLM_API_URL='http://your-llm-api/v1/chat/completions'\n"
                f"  export LLM_MODEL='gpt-5.2'\n"
                f"  export LLM_API_KEY='your-api-key'"
            )
