# -*- coding: utf-8 -*-
"""密令/兑换码自动提取：从攻略文本中识别关键词附近的兑换码与奖励。

背景（D13）：密令藏身攻略长文/图片，靠 RAG 全文检索易答错/答出过期码。
本模块把「密令/兑换码/口令…」引导词附近的码自动抽出来入库 codes 表，
查询走结构化 query_codes（又快又准），由 P3 管理后台维护状态/奖励。

策略（规则式，离线可跑、不花 LLM 调用）：
1. 只在「密令/兑换码/礼包码/口令/激活码/福利码/神秘代码」引导词之后找码，
   避免把攻略正文误判为密令；
2. 码形：连续中文短语（3~20 字）或 字母数字（可含空格/连字符，2~20 位）；
3. 奖励：码之后 60 字内抓「奖励/赠送/礼包/领取…」引导的短语，
   尽力而为，运营可在管理后台修正；
4. 应用场景：建库导入（_ingest）、聊天粘贴链接/附件（chat-upload）、
   scripts/build_kb.py 自动抽取入库（去重）。
"""
import logging
import re

from server.core.models import Code

log = logging.getLogger(__name__)

# 引导词：出现这些词后紧跟的短语视为候选密令
_LEAD = r"(?:密令|兑换码|礼包码|口令|激活码|福利码|神秘代码)"
# 码形：中文连续短语 或 字母数字（含空格/连字符）
_CODE_CJK = r"[\u4e00-\u9fff]{3,20}"
_CODE_ASCII = r"[A-Za-z0-9][A-Za-z0-9\- ]{1,19}"
# 主模式：引导词 [:：=]? 后跟码
_PATTERN = re.compile(_LEAD + r"\s*[:：=]?\s*(" + _CODE_CJK + r"|" + _CODE_ASCII + r")")

# 码内混入的尾缀词（如“密令：烈焰红唇奖励1000…”，把“奖励1000…”切掉）
_TRAIL_CUT = re.compile(
    r"(?:奖励|赠送|礼包|领取|可获得|获得|内含|限量|即可|请输入|请输入密令|兑换|输入|前往|进入|查看|点击).*$"
)

# 明显非密令的结尾词（区分度不足，直接滤掉）
_NOISE_END = re.compile(r"(如下|大全|地址|入口|在哪|获取途径|截止|结束|过期|一览|概要|说明|介绍|引导词|详情|公布|公告|相关)$")

# 奖励引导：码后抓“奖励：xxx”等短语（不含标点/空白/换行）
_REWARD_LEAD = re.compile(
    r"(?:奖励|赠送|礼包|领取|可获得|获得|内含|包含)\s*[:：]?\s*([^。；;，,、\n|【】\s]{1,40})"
)
_REWARD_LOOKAHEAD = 60


def extract_codes(text: str, max_codes: int = 30) -> list[dict]:
    """从文本提取兑换码候选，返回 [{"text", "reward"}]（按出现顺序去重）。

    同一码只保留首次出现的奖励；最多提取 max_codes 条，防止长文误判刷爆。
    """
    if not text:
        return []
    seen: set[str] = set()
    result: list[dict] = []
    for m in _PATTERN.finditer(text):
        raw_code = m.group(1)
        code = _TRAIL_CUT.sub("", raw_code).strip()
        if not _is_valid_code(code) or code in seen:
            continue
        seen.add(code)
        # 从码结束后开始向后找奖励（group(1) 被 _TRAIL_CUT 截断时偏移修正）
        reward_start = m.start(1) + len(code)
        result.append({"text": code, "reward": _find_reward(text, reward_start)})
        if len(result) >= max_codes:
            break
    return result


def _is_valid_code(code: str) -> bool:
    """长度与噪音过滤：至少 3 个有效字符，且不以明显非码词结尾。"""
    if len([c for c in code if c.isalnum()]) < 3:
        return False
    return not _NOISE_END.search(code)


def _find_reward(text: str, start: int) -> str:
    """在码之后一小段窗口里找奖励短语。"""
    window = text[start : start + _REWARD_LOOKAHEAD]
    m = _REWARD_LEAD.search(window)
    if not m:
        return ""
    return m.group(1).strip()[:20]


def extract_codes_to_kb(text: str, kb, batch: str = "", remark: str = "自动提取") -> int:
    """提取密令并去重入库（codes 表），返回新增条数。

    kb 需符合 KB 接口（add_code / list_codes_all）。重复码跳过，不覆盖已有奖励。
    """
    existing = {c["text"] for c in kb.list_codes_all()}
    added = 0
    for item in extract_codes(text):
        if item["text"] in existing:
            continue
        kb.add_code(Code(text=item["text"], reward=item["reward"], status="生效",
                         batch=batch, remark=remark))
        existing.add(item["text"])
        added += 1
    return added