# -*- coding: utf-8 -*-
"""密令 seed 脚本：把运营/用户提供的一批兑换码录入 codes 表。

密令为公开兑换码（非攻略原文），可入库维护。奖励未知时留空并由 remark 标注。
用法：
    D:\\SoftWare\\Python312\\python.exe scripts\\seed_codes.py
    D:\\SoftWare\\Python312\\python.exe scripts\\seed_codes.py --status 已过期   # 默认生效
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.core.models import Code  # noqa: E402
from server.rag.kb import KB  # noqa: E402

log = logging.getLogger("seed_codes")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# 用户提供的密令清单（已去重；奖励未知，待补）
CODES = [
    "喜欢是放肆爱是克制", "朴实无华且枯燥", "烈焰红唇", "whosyourdaddy",
    "greedisgood", "triple kill", "go go go", "i have a dream", "first blood",
    "freedom", "宅男女神", "发现好蜗牛", "果美人出版", "你好呀", "全员写真",
    "宣传图里藏着密令", "我们来啦", "有钱能使鬼推磨", "QC-GAME", "showmethemoney",
    "图里有密令", "杀手个人简历", "Hail hydra", "你不开心我不答应", "摩擦能生热",
    "一起玩耍", "最惨官方", "平安", "有金币有密令", "封口费", "规则在说谎",
    "下手轻点别打脸", "盛夏光年", "蝉鸣夏日曲", "恋与哈兰德", "游泳健将一枚鸭",
    "十一年的冠军", "青蛙教练", "今天先不内耗", "蜗起大狙对面输了", "蜗走香蕉道",
    "和空调双排", "蜗真的特别爱鹂", "辣炒嘎啦配西瓜", "现在开始放晴了",
    "海盐柠檬苏打汽水", "蜗是冠军他是什么", "先假装淡定", "今天谁都别演",
    "蜗先许个愿", "冰汽水准备好了", "巧乐兹真好吃", "太阳在北半球", "来杯好茶摇",
    "帮蜗涂防晒霜", "下雨打伞变蘑菇", "鹂好帅鸭", "鹂听蜗讲丫", "区区黄毛丫头",
    "咕嘎咕咕嘎嘎", "来口风油精", "阳光准时打卡", "蜗先插个队", "再试一次不亏",
    "先别急着笑", "不信你试试", "鹂先别羡慕", "课桌藏着秘密", "烦恼暂停服务",
    "蜗差点信了", "月满花时", "冰粥清补凉", "没灵根不许修仙", "秋江水冷鸭先知",
    "下次还填非常简单", "高贵名门需要队友",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", default="生效", choices=["生效", "停用", "已过期"])
    ap.add_argument("--batch", default="2026-09-09 玩家提供", help="批次/来源备注")
    args = ap.parse_args()

    kb = KB()
    seen = {r["text"] for r in kb._conn.execute("SELECT text FROM codes").fetchall()}
    added = skipped = 0
    for text in CODES:
        if text in seen:
            skipped += 1
            continue
        kb.add_code(Code(text=text, reward="", status=args.status, batch=args.batch,
                         remark="奖励未知，待运营核实补充"))
        seen.add(text)
        added += 1
    log.info("新增 %d 条，跳过已存在 %d 条；当前生效密令共 %d 条",
             added, skipped, len(kb.search_codes()))
    kb.close()
    log.info("提示：奖励未知（reward 为空），待运营核实后在管理后台补充。")


if __name__ == "__main__":
    main()