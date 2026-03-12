# RAGFlow 文档解析器效果对比工具

<div align="center">

通过自动化问答测试和 LLM 评分，对比评估 RAGFlow 不同 PDF 文档解析器（TextIn、DeepDOC 等）的实际效果

</div>

---

## 📖 简介

本工具通过 RAGFlow 问答质量测试，对比评估不同 PDF 文档解析器（TextIn、DeepDOC、PaddlePaddle 等）的实际效果，支持：

- ✅ **自动化问答测试** - 批量调用 RAGFlow API 获取答案
- ✅ **LLM 三维度评分** - 准确性、完整性、清晰度全面评估
- ✅ **智能助手检测** - 自动识别并评分所有助手
- ✅ **多解析器对比** - 一键生成多助手对比报告
- ✅ **增量测试支持** - 自动跳过已测试的问题，支持断点续测

我们基于 [OmniDocBench](https://opendatalab.com/OpenDataLab/OmniDocBench) 数据集准备了测试示例，用于验证文档解析效果。

---

## 📑 目录

- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [命令行工具](#命令行工具)
- [完整示例](#完整示例)
- [测试验证](#测试验证)
- [致谢](#致谢)

---

## 📂 项目结构

```
test_qa/
├── README.md                    # 本文档
└── benchmark/
    ├── chat.py                  # 问答测试脚本
    ├── score.py                 # LLM 评分脚本
    ├── img2pdf.py               # 图片转PDF工具
    ├── config.py                # 配置文件
    ├── requirements.txt         # Python 依赖列表
    └── OmniDocBench/            # 数据集目录（所有数据文件都在这里）
        ├── images/              # 原始图片（从 OpenDataLab 下载）
        ├── pdfs/                # 转换后的PDF
        ├── qa.jsonl             # 原始问答对数据（不会被修改）
        ├── results.jsonl        # 测试结果（包含 RAGFlow 答案和评分）
        ├── chat.log             # 问答测试日志
        └── score.log            # 评分日志
```

## 🚀 快速开始

### 步骤 1：安装依赖库

```bash
# 安装必要的第三方库
pip3 install requests pillow ragflow-sdk
```

### 步骤 2：下载测试数据集

访问 [OpenDataLab](https://opendatalab.com/OpenDataLab/OmniDocBench/tree/main) 下载 OmniDocBench 数据集：

**① 下载文件**

在页面中下载 `images.zip` 文件到本地。

**② 解压文件**

```bash
cd test_qa/benchmark
unzip /path/to/downloaded/images.zip -d OmniDocBench/
```

> 💡 **提示**：OpenDataLab 的下载链接会动态生成，无法直接使用 wget。请通过浏览器访问上述地址手动下载。

### 步骤 3：转换图片为 PDF

> ⚠️ **重要**：由于 RAGFlow 采用插件方式接入 Textin，目前只支持对 PDF 样本调用 Textin 解析。

```bash
cd test_qa/benchmark
python3 img2pdf.py --input OmniDocBench/images/ --output OmniDocBench/pdfs/
```

转换完成后，PDF 文件将保存在 `OmniDocBench/pdfs/` 目录。

### 步骤 4：RAGFlow 配置

**① 创建知识库**
- 登录 RAGFlow 管理界面
- 创建新的知识库（或使用现有知识库）
- **选择 Textin 作为解析器**

**② 上传文档**
- 上传步骤 3 生成的 PDF 文件
- 等待所有样本解析完成

> 💡 **提示**：批量上传大量文件可使用 [ragflow-upload](https://github.com/Samge0/ragflow-upload) 工具。

**③ 创建助手**
- 创建新的聊天助手
- 在助手设置中关联知识库
- 记录助手名称（后续测试需要用到）

### 步骤 5：配置测试参数

**方式一：环境变量（推荐）**

```bash
# RAGFlow 配置（运行 chat.py 时必填）
export RAGFLOW_BASE_URL="https://ragflow.intsig.net"
export RAGFLOW_API_KEY="ragflow-xxxxxxxx"
export RAGFLOW_ASSISTANT_NAME="textin_assistant"

# LLM 配置（运行 score.py 时必填）
export LLM_API_URL="http://your-llm-api/v1/chat/completions"
export LLM_MODEL="gpt-5.2"
export LLM_API_KEY="your-llm-api-key"
```

**方式二：配置文件**

编辑 `benchmark/config.py` 直接设置相关参数。

### 步骤 6：运行问答测试

```bash
cd test_qa/benchmark
python3 chat.py --assistant-name "textin_assistant" \
               --question-file OmniDocBench/qa.jsonl \
               --output-file OmniDocBench/results.jsonl
```

> 💡 **说明**：`results.jsonl` 是输出文件，不会覆盖原始的 `qa.jsonl`。

### 步骤 7：运行 LLM 评分

```bash
python3 score.py --data-file OmniDocBench/results.jsonl \
                --answer-keys "textin_assistant_answer"
```

评分完成后，会输出详细的统计报告（平均得分和分数区间分布）。

---

## 🔧 命令行工具

### img2pdf.py

批量将图片文件转换为 PDF 格式。

#### 基本用法

```bash
python3 img2pdf.py \
  --input "OmniDocBench/images/" \    # 图片目录路径
  --output "OmniDocBench/pdfs/"       # 输出PDF目录
```

#### 功能特性

- **支持格式**：JPG, JPEG, PNG, BMP, TIFF, TIF, WEBP
- **自动转换**：RGBA/LA/P 模式自动转为 RGB（白色背景）
- **保持质量**：保持原始分辨率
- **进度显示**：实时显示转换统计信息

---

### chat.py

调用 RAGFlow API 获取问答答案并保存到结果文件。

#### 基本用法

```bash
# 使用默认配置
python3 chat.py

# 指定助手名称
python3 chat.py --assistant-name "textin_assistant"
```

#### 完整参数

```bash
python3 chat.py \
  --assistant-name "助手名称" \           # 可选，默认从 config.py 读取
  --question-file "qa.jsonl" \           # 可选，默认 OmniDocBench/qa.jsonl
  --output-file "results.jsonl" \        # 可选，默认 OmniDocBench/results.jsonl
  --base-url "https://..." \             # 可选，默认从 config.py 读取
  --api-key "ragflow-xxx" \              # 可选，默认从 config.py 读取
  --overwrite                            # 可选，覆盖已有答案（默认跳过）
```

#### 功能特性

- ✅ 支持 JSONL 格式问题集
- ✅ 自动调用 RAGFlow API
- ✅ 增量追加支持（断点续测）
- ✅ 自动跳过已有答案（可选覆盖）

---

### score.py

使用 LLM 对问答结果进行三维度评分（准确性、完整性、清晰度）。

#### 基本用法

```bash
# 默认模式：调用 LLM 评分所有未评分的助手
python3 score.py

# 对比模式：读取已有评分数据并生成对比报告（不调用 LLM API）
python3 score.py --compare
```

#### 完整参数

```bash
python3 score.py \
  --data-file "results.jsonl" \          # 可选，默认 OmniDocBench/results.jsonl
  --compare \                            # 可选，生成多助手对比报告
  --api-url "http://..." \               # 可选，默认从 config.py 读取
  --model "gpt-5.2" \                    # 可选，默认从 config.py 读取
  --api-key "your-key" \                 # 可选，默认从 config.py 读取
  --overwrite                            # 可选，覆盖已有评分（默认跳过）
```

#### 功能特性

- ✅ 三维度评分：准确性（50%）+ 完整性（30%）+ 清晰度（20%）
- ✅ 自动检测助手：自动识别数据中的所有助手答案（`*_answer` 格式）
- ✅ 增量评分：自动跳过已评分的数据，支持断点续测
- ✅ 对比报告：使用 `--compare` 读取已有评分生成对比表格（不调用 API）

#### 查看日志

```bash
cd test_qa/benchmark
tail -f OmniDocBench/chat.log   # 实时查看问答日志
tail -f OmniDocBench/score.log  # 实时查看评分日志
```


## 📋 完整示例

以下是一个完整的测试流程：

```bash
# ① 安装依赖
pip3 install requests pillow ragflow-sdk

# ② 下载数据集（从 OpenDataLab 网站手动下载 images.zip）
cd test_qa/benchmark
unzip /path/to/downloaded/images.zip -d OmniDocBench/

# ③ 转换图片为 PDF
python3 img2pdf.py --input OmniDocBench/images/ --output OmniDocBench/pdfs/

# ④ 在 RAGFlow 中配置
#    - 创建知识库
#    - 上传 PDF 文件
#    - 选择 Textin 解析器
#    - 创建助手并关联知识库

# ⑤ 配置环境变量
export RAGFLOW_BASE_URL="https://ragflow.intsig.net"
export RAGFLOW_API_KEY="ragflow-xxxxx"
export RAGFLOW_ASSISTANT_NAME="textin_assistant"
export LLM_API_URL="http://your-llm-api/v1/chat/completions"
export LLM_MODEL="gpt-5.2"
export LLM_API_KEY="your-llm-key"

# ⑥ 运行问答测试
python3 chat.py --question-file OmniDocBench/qa.jsonl \
               --output-file OmniDocBench/results.jsonl

# ⑦ 运行 LLM 评分（调用 LLM API 评分）
python3 score.py

# 💡 提示：如果需要测试多个知识库或助手，需要分别执行步骤 ⑥ 和 ⑦
#    - 修改 RAGFLOW_ASSISTANT_NAME 为不同的助手名称
#    - 重复执行 chat.py 和 score.py
#    - 所有助手的答案和评分会保存在同一个 results.jsonl 文件中

# ⑧ 查看对比报告（读取已有评分数据，不调用 API）
python3 score.py --compare

```

---

## 📊 测试验证

我们在本地环境按照上述流程，使用 OmniDocBench 问答任务对 TextIn 解析器进行了测试验证。

### 测试环境

| 配置项 | 值 |
|--------|-----|
| **文档解析器** | TextIn vs RAGFlow 内置 DeepDOC |
| **嵌入模型** | text-embedding-v4 |
| **评分模型** | gpt-5.2 |
| **测试数据集** | OmniDocBench |
| **问答对数量** | 132 |
| **其他配置** | RAGFlow 默认配置 |

### 评分对比结果

| 助手名称 | 总数 | 成功 | 平均分 | 100 | 80-99 | 60-79 | 1-59 | 0 |
|---------|------|------|--------|-----|-------|-------|------|---|
| textin  | 132 | 132 | **85.51** | **55.3%** | **26.5%** | 2.3% | 10.6% | 5.3% |
| ragflow | 132 | 132 | 73.00 | 32.6% | 31.8% | 7.6% | 21.2% | 6.8% |

### 典型案例分析

以下是从测试集中挑选的典型错误案例，展示两种解析器在实际文档中的差异表现。

#### 案例 1：表格大面积漏识别

**测试问题**：截至"十一五"末，全公路总里程完成情况如何？

**原始文档**

<img src="benchmark/OmniDocBench/cmpare_images/1.jpg" width="400" alt="案例1-原始文档">

**解析结果对比**

<table>
<tr>
<th width="50%">TextIn 解析结果（得分：75）</th>
<th width="50%">RAGFlow DeepDoc 解析结果（得分：0）</th>
</tr>
<tr>
<td><img src="benchmark/OmniDocBench/cmpare_images/1-textin.jpg" alt="TextIn解析"></td>
<td><img src="benchmark/OmniDocBench/cmpare_images/1-ragflow.jpg" alt="DeepDoc解析"></td>
</tr>
</table>

**问题分析**：RAGFlow 表格大面积漏识别，导致关键数据缺失，无法正确回答问题。

---

#### 案例 2：表格结构错乱

**测试问题**：库存现金收入日记账中，应贷科目一共有几列？

**原始文档**

<img src="benchmark/OmniDocBench/cmpare_images/2.jpg" width="400" alt="案例2-原始文档">

**解析结果对比**

<table>
<tr>
<th width="50%">TextIn 解析结果（得分：100）</th>
<th width="50%">RAGFlow DeepDoc 解析结果（得分：10）</th>
</tr>
<tr>
<td><img src="benchmark/OmniDocBench/cmpare_images/2-textin.jpg" alt="TextIn解析"></td>
<td><img src="benchmark/OmniDocBench/cmpare_images/2-ragflow.jpg" alt="DeepDoc解析"></td>
</tr>
</table>

**问题分析**：RAGFlow 表格结构错乱，行列关系识别错误，导致答案完全不准确。

---

#### 案例 3：表格层级还原差

**测试问题**：根据全球科研实力对比表，二级主题词计算机视觉下有哪些三级主题词？

**原始文档**

<img src="benchmark/OmniDocBench/cmpare_images/3.jpg" width="400" alt="案例3-原始文档">

**解析结果对比**

<table>
<tr>
<th width="50%">TextIn 解析结果（得分：100）</th>
<th width="50%">RAGFlow DeepDoc 解析结果（得分：74）</th>
</tr>
<tr>
<td><img src="benchmark/OmniDocBench/cmpare_images/3-textin.jpg" alt="TextIn解析"></td>
<td><img src="benchmark/OmniDocBench/cmpare_images/3-ragflow.jpg" alt="DeepDoc解析"></td>
</tr>
</table>

**问题分析**：RAGFlow 表格层级还原差，复杂表格的层次关系识别不准确，导致答案不够精准。

---

#### 案例 4：文本分块错误

**测试问题**：1977年9月，邓小平在会见英籍作家韩素音时说了什么？

**原始文档**

<img src="benchmark/OmniDocBench/cmpare_images/4.jpg" width="400" alt="案例4-原始文档">

**解析结果对比**

<table>
<tr>
<th width="50%">TextIn 解析结果（得分：100）</th>
<th width="50%">RAGFlow DeepDoc 解析结果（得分：64）</th>
</tr>
<tr>
<td><img src="benchmark/OmniDocBench/cmpare_images/4-textin.jpg" alt="TextIn解析"></td>
<td><img src="benchmark/OmniDocBench/cmpare_images/4-ragflow.jpg" alt="DeepDoc解析"></td>
</tr>
</table>

**问题分析**：RAGFlow 文本分块错误，导致合并后的语义错误，检索内容缺失。

---

#### 案例 5：文字识别漏识与顺序错误

**测试问题**：鎏金舞马衔杯纹银壶的尺寸是多少？

**原始文档**

<img src="benchmark/OmniDocBench/cmpare_images/5.jpg" width="400" alt="案例5-原始文档">

**解析结果对比**

<table>
<tr>
<th width="50%">TextIn 解析结果（得分：100）</th>
<th width="50%">RAGFlow DeepDoc 解析结果（得分：58）</th>
</tr>
<tr>
<td><img src="benchmark/OmniDocBench/cmpare_images/5-textin.jpg" alt="TextIn解析"></td>
<td><img src="benchmark/OmniDocBench/cmpare_images/5-ragflow.jpg" alt="DeepDoc解析"></td>
</tr>
</table>

**问题分析**：RAGFlow 图片下方文字漏识别，且文字顺序错误，导致关键信息缺失。

---

### 测试结论

**TextIn 解析器表现显著优于 RAGFlow 内置 DeepDOC：**

- ✅ **平均得分**：TextIn (85.51) 领先 DeepDOC (73.00) **12.51 分**
- ✅ **满分率**：TextIn (55.3%) 比 DeepDOC (32.6%) 高出 **22.7%**
- ✅ **高分率**：TextIn 的 80 分以上占比 81.8%，DeepDOC 为 64.4%
- ✅ **低分率**：TextIn 的 60 分以下占比 15.9%，低于 DeepDOC 的 28.0%

**结论**：对于 OmniDocBench 数据集，TextIn 在文档解析质量上具有明显优势，特别是在复杂文档的准确性和完整性方面表现更佳

---

## 🙏 致谢

感谢以下开源项目和工具的支持：

- **[RAGFlow](https://github.com/infiniflow/ragflow)** - 强大的开源 RAG 引擎
- **[ragflow-upload](https://github.com/Samge0/ragflow-upload)** - 便捷的文件批量上传工具
- **[OpenDataLab](https://opendatalab.com/)** - 提供 OmniDocBench 等高质量数据集

---

## 📄 许可证

```
Copyright 2026 The InfiniFlow Authors. All Rights Reserved.

Licensed under the Apache License, Version 2.0.
```
