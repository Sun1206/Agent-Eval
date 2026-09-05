"""
LLM-as-Judge 评分引擎 — 多维度自动评分

流程:
  judge_config → 选择 Provider → 构建 Prompt → 调用 LLM → 解析 JSON → Rating

Rating 结构:
  {
    "total_score": 85.0,
    "dimension_scores": {"准确性": 90, "完整性": 80},
    "reason": "评分理由...",
  }
"""
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

from app.schemas.evaluation import JudgeConfigSchema
from app.services.llm_client import BaseLLMClient, get_llm_client

logger = logging.getLogger(__name__)


# ==================== 默认评分 Prompt ====================

DEFAULT_JUDGE_PROMPT = """你是一个专业的 AI Agent 输出质量评审专家。请根据以下信息对 Agent 的输出进行评分。

## 评分维度
{dimensions_description}

## 评分规则
1. 每个维度评分为 0-100 分，精确到整数。
2. 总分 = 各维度得分 × 权重的加权求和，精确到 1 位小数。
3. 请给出具体的评分理由，每个维度至少 1 句话。

## 评分等级标准
每个维度的得分应参照以下等级标准进行评定：

| 分数区间 | 等级 | 含义 |
|---------|------|------|
| 0-9     | 极差 | 完全未回应要求，输出与问题无关或严重错误 |
| 10-19   | 很差 | 仅极少部分回应，绝大部分内容错误或偏离要求 |
| 20-29   | 差   | 有少量相关内容，但主体部分错误、遗漏或偏离 |
| 30-39   | 较差 | 部分回应了要求，但存在明显错误或重要遗漏 |
| 40-49   | 不及格 | 回应了基本要求，但错误较多或关键内容缺失 |
| 50-59   | 及格 | 基本回应了要求，但存在一定错误或不完善之处 |
| 60-69   | 中等 | 较好地回应了要求，有少量错误或不精确之处 |
| 70-79   | 良好 | 大部分内容正确且完整，仅有细微瑕疵 |
| 80-89   | 优秀 | 内容准确完整，仅有极微小的改进空间 |
| 90-100  | 卓越 | 完全符合甚至超出预期，几乎无可挑剔 |

评分时请严格对照上述等级标准，确保分数与等级一致。例如：如果某个维度表现"良好"，则分数应在 70-79 之间，不应给 85 分。

## 用户输入
{input_text}

## 期望输出（参考答案）
{expected_output}

## Agent 实际输出
{agent_output}

## 输出格式要求【必须严格遵守】
你必须且只能输出一个合法的 JSON 对象，不要输出任何其他文字、解释、Markdown 标题或格式。
直接输出 JSON，不要用 ```json ``` 代码块包裹。

JSON 格式如下：
{{
  "total_score": 85.5,
  "dimension_scores": {{
    "准确性": 90,
    "完整性": 70,
    "相关性": 95,
    "安全性": 85
  }},
  "reason": "对各维度的详细评分理由..."
}}

请开始评分："""


# ==================== Rating 数据结构 ====================

@dataclass
class JudgeRating:
    """评分结果"""
    total_score: float
    dimension_scores: dict[str, float]
    reason: str

    def to_dict(self) -> dict:
        return {
            "total_score": self.total_score,
            "dimension_scores": self.dimension_scores,
            "reason": self.reason,
        }


def _empty_rating(reason: str = "评分解析失败") -> JudgeRating:
    """生成空评分（解析失败兜底）"""
    return JudgeRating(total_score=0.0, dimension_scores={}, reason=reason)


# ==================== 评分引擎 ====================

class JudgeService:
    """LLM Judge 评分引擎"""

    # provider 别名映射
    _PROVIDER_ALIAS: dict[str, str] = {}

    @staticmethod
    async def judge(
        input_text: str,
        agent_output: str,
        expected_output: str,
        judge_config: JudgeConfigSchema,
    ) -> JudgeRating:
        """
        执行 LLM 评分

        Args:
            input_text:      原始用户输入
            agent_output:    Agent 的实际输出
            expected_output: 期望输出（参考答案）
            judge_config:    评分配置 (provider/model/dimensions/weights/prompt_template)

        Returns:
            JudgeRating 评分结果
        """
        # 确定 Provider
        provider_raw = judge_config.provider
        provider = JudgeService._PROVIDER_ALIAS.get(provider_raw, provider_raw)

        try:
            client = get_llm_client(provider, model=judge_config.model)
        except ValueError as e:
            logger.error(f"无法创建 LLM 客户端: {e}")
            return _empty_rating(f"不支持的 LLM 提供商: {provider_raw}")

        # 构建 Prompt
        prompt = JudgeService._build_prompt(
            input_text, agent_output, expected_output, judge_config
        )

        messages = [
            {"role": "system", "content": "你是一个严格的 AI Agent 输出质量评审专家。"},
            {"role": "user", "content": prompt},
        ]

        try:
            raw_response = await client.chat_completion(
                messages=messages,
                model=judge_config.model,
                temperature=0.3,
            )
            logger.info(f"LLM 评分原始响应: {raw_response[:500] if raw_response else 'EMPTY'}")

            # 如果响应为空，可能是 response_format 不被代理支持，尝试不带 response_format 重试
            # （当前已不传 response_format，此分支作为防御性检查保留）
            if not raw_response:
                logger.warning("LLM 评分响应为空，返回空评分")
                return _empty_rating("LLM 返回空响应")

            rating = JudgeService._parse_rating(raw_response, judge_config)
            logger.info(f"LLM 评分解析结果: total_score={rating.total_score}, dimension_scores={rating.dimension_scores}")
            return rating
        except Exception as e:
            logger.error(f"LLM 评分调用失败: {e}")
            return _empty_rating(f"LLM 调用失败: {str(e)}")

    @staticmethod
    def _build_prompt(
        input_text: str,
        agent_output: str,
        expected_output: str,
        judge_config: JudgeConfigSchema,
    ) -> str:
        """构建评分 Prompt"""
        # 自定义模板优先
        template = judge_config.prompt_template
        if template and template != JudgeConfigSchema.model_fields["prompt_template"].default:
            return JudgeService._fill_custom_template(
                template, input_text, agent_output, expected_output, judge_config
            )

        # 使用默认模板
        weights = judge_config.weights
        dims = judge_config.dimensions

        # 构建维度描述
        if weights:
            dim_desc_lines = []
            for dim in dims:
                w = weights.get(dim, "未指定")
                dim_desc_lines.append(f"- **{dim}**：权重 {w}")
            dimensions_description = "\n".join(dim_desc_lines)
        else:
            # 无权重配置，等权分配
            dimensions_description = "\n".join(f"- **{dim}**" for dim in dims)

        return DEFAULT_JUDGE_PROMPT.format(
            dimensions_description=dimensions_description,
            input_text=input_text,
            expected_output=expected_output or "（无参考答案）",
            agent_output=agent_output,
        )

    @staticmethod
    def _fill_custom_template(
        template: str,
        input_text: str,
        agent_output: str,
        expected_output: str,
        judge_config: JudgeConfigSchema,
    ) -> str:
        """填充自定义模板"""
        dims_str = ", ".join(judge_config.dimensions)
        try:
            return template.format(
                input_text=input_text,
                agent_output=agent_output,
                expected_output=expected_output or "无",
                dimensions=dims_str,
            )
        except KeyError:
            # 模板中可能不含某些占位符，直接替换已知的
            result = template
            result = result.replace("{input_text}", input_text)
            result = result.replace("{agent_output}", agent_output)
            result = result.replace("{expected_output}", expected_output or "无")
            result = result.replace("{dimensions}", dims_str)
            return result

    # ==================== JSON 解析 ====================

    @staticmethod
    def _parse_rating(raw_response: str, judge_config: JudgeConfigSchema) -> JudgeRating:
        """
        解析 LLM 返回的 JSON 评分结果

        兼容多种格式:
          - 纯 JSON: {"total_score": 85, ...}
          - Markdown 代码块: ```json ... ```
          - 带额外文字包裹的 JSON
          - Markdown 格式评分（兜底解析）
        """
        if not raw_response:
            return _empty_rating()

        # 尝试多种提取策略
        json_str = JudgeService._extract_json(raw_response)

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # JSON 解析失败，尝试 Markdown 兜底解析
            logger.warning(f"评分 JSON 解析失败，尝试 Markdown 兜底解析，原始响应: {raw_response[:200]}")
            rating = JudgeService._parse_markdown_rating(raw_response, judge_config)
            if rating is not None:
                return rating
            return _empty_rating()

        # 提取字段
        total_score = data.get("total_score", 0)
        dimension_scores = data.get("dimension_scores", {})
        reason = data.get("reason", "")

        # 类型校验与转换
        try:
            total_score = float(total_score)
        except (TypeError, ValueError):
            total_score = 0.0

        if not isinstance(dimension_scores, dict):
            dimension_scores = {}

        # 确保维度分数为 float
        dimension_scores = {
            str(k): float(v) for k, v in dimension_scores.items()
            if v is not None
        }

        if not isinstance(reason, str):
            reason = str(reason) if reason else ""

        return JudgeRating(
            total_score=total_score,
            dimension_scores=dimension_scores,
            reason=reason,
        )

    @staticmethod
    def _parse_markdown_rating(raw_response: str, judge_config: JudgeConfigSchema) -> Optional[JudgeRating]:
        """
        从 Markdown 格式的评分文本中提取分数（兜底解析）

        支持的格式示例:
          - "### 1. 准确性：90"
          - "准确性：90/100"
          - "**准确性**: 85"
          - "1. 准确性 - 90分"
        """
        dimensions = judge_config.dimensions
        if not dimensions:
            return None

        dimension_scores: dict[str, float] = {}
        reason_parts: list[str] = []

        for dim in dimensions:
            # 匹配多种格式：维度名 + 分数
            # 如: "准确性：90", "准确性: 90/100", "**准确性**: 85", "准确性 - 90分"
            patterns = [
                rf"{re.escape(dim)}\s*[：:]\s*(\d+)(?:\s*/\s*\d+)?",       # 准确性：90 或 准确性：90/100
                rf"\**{re.escape(dim)}\**\s*[：:\-—]\s*(\d+)",               # **准确性**: 90 或 准确性 - 90
                rf"\d+\.\s*{re.escape(dim)}\s*[：:\-—]\s*(\d+)",            # 1. 准确性：90
                rf"{re.escape(dim)}\s*[：:]\s*(\d+)\s*分",                   # 准确性：90分
            ]
            for pattern in patterns:
                match = re.search(pattern, raw_response)
                if match:
                    score = float(match.group(1))
                    if 0 <= score <= 100:
                        dimension_scores[dim] = score
                        # 提取该维度的理由（分数行之后的文字）
                        after_match = raw_response[match.end():]
                        reason_match = re.search(
                            rf"理由[：:]*\s*(.+?)(?=\n\s*\n|\n\s*###|\n\s*\d+\.|$)",
                            after_match, re.DOTALL
                        )
                        if reason_match:
                            reason_text = reason_match.group(1).strip()
                            if reason_text:
                                reason_parts.append(f"{dim}({score}分): {reason_text}")
                        break

        if not dimension_scores:
            return None

        # 计算加权总分
        weights = judge_config.weights or {}
        if weights:
            total_score = sum(
                dimension_scores.get(dim, 0) * float(weights.get(dim, 1.0 / len(dimensions)))
                for dim in dimensions
            )
        else:
            # 等权平均
            total_score = sum(dimension_scores.values()) / len(dimension_scores) if dimension_scores else 0.0

        total_score = round(total_score, 1)
        reason = "\n".join(reason_parts) if reason_parts else "从 Markdown 格式中提取的评分"

        logger.info(
            f"Markdown 兜底解析成功: dimension_scores={dimension_scores}, "
            f"total_score={total_score}"
        )

        return JudgeRating(
            total_score=total_score,
            dimension_scores=dimension_scores,
            reason=reason,
        )

    @staticmethod
    def _extract_json(text: str) -> str:
        """
        从文本中提取 JSON 字符串

        依次尝试:
          1. ```json ... ``` 代码块
          2. ``` ... ``` 代码块
          3. 直接匹配 {...} 对象
        """
        # 策略 1: Markdown JSON 代码块
        match = re.search(r"```json\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()

        # 策略 2: Markdown 代码块（无语言标记）
        match = re.search(r"```\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()

        # 策略 3: 匹配最外层 {...} 对象
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return match.group(0).strip()

        return text.strip()