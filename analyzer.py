"""预测引擎 — 基于5大策略 + 补充策略生成号码"""
import random
from collections import Counter
from typing import Optional

from logger import log


def _calc_ac(reds: list[int]) -> int:
    """计算 AC 值（算术复杂性）"""
    diffs = set()
    for i in range(len(reds)):
        for j in range(i + 1, len(reds)):
            diffs.add(abs(reds[i] - reds[j]))
    return len(diffs) - (len(reds) - 1)


def _count_consecutive(reds: list[int]) -> list[list[int]]:
    """计算连号组"""
    groups = []
    current = [reds[0]]
    for i in range(1, len(reds)):
        if reds[i] == reds[i - 1] + 1:
            current.append(reds[i])
        else:
            if len(current) >= 2:
                groups.append(current[:])
            current = [reds[i]]
    if len(current) >= 2:
        groups.append(current[:])
    return groups


def generate_predictions(records: list[dict], count: int = 10) -> list[dict]:
    """
    基于策略生成预测号码

    参数:
        records: 历史数据列表, 每项 {"期号", "日期", "红球": [6个int], "蓝球": int}
        count: 生成组数

    返回:
        [{"reds": [6个int], "blue": int}, ...]
    """
    total = len(records)

    # 排除历史完全相同的组合
    historical_combos = set()
    for r in records:
        historical_combos.add((tuple(r["红球"]), r["蓝球"]))

    # 频率统计
    red_counter = Counter()
    blue_counter = Counter()
    for r in records:
        red_counter.update(r["红球"])
        blue_counter[r["蓝球"]] += 1

    # 近50期频率
    recent = records[-50:] if len(records) >= 50 else records
    recent_red = Counter()
    recent_blue = Counter()
    for r in recent:
        recent_red.update(r["红球"])
        recent_blue[r["蓝球"]] += 1

    # 综合频率得分 (近期 0.6, 历史 0.4)
    red_score = {}
    for num in range(1, 34):
        hist_freq = red_counter.get(num, 0) / total
        recent_freq = recent_red.get(num, 0) / len(recent)
        red_score[num] = hist_freq * 0.4 + recent_freq * 0.6

    blue_score = {}
    for num in range(1, 17):
        hist_freq = blue_counter.get(num, 0) / total
        recent_freq = recent_blue.get(num, 0) / len(recent)
        blue_score[num] = hist_freq * 0.4 + recent_freq * 0.6

    def weighted_sample(scores: dict, k: int) -> list[int]:
        items = list(scores.keys())
        weights = [scores[i] + random.random() * 0.02 for i in items]
        total_w = sum(weights)
        probs = [w / total_w for w in weights]
        selected = []
        rem_items = list(items)
        rem_probs = list(probs)
        for _ in range(k):
            chosen = random.choices(rem_items, weights=rem_probs, k=1)[0]
            selected.append(chosen)
            idx = rem_items.index(chosen)
            rem_items.pop(idx)
            rem_probs.pop(idx)
        return selected

    def generate_one() -> Optional[dict]:
        for _ in range(100):
            reds = sorted(weighted_sample(red_score, 6))
            blue = weighted_sample(blue_score, 1)[0]

            # 策略2: 连号
            has_consecutive = any(
                reds[i + 1] == reds[i] + 1 for i in range(len(reds) - 1)
            )

            # 策略4: 奇偶比 (2:4 ~ 4:2)
            odd = sum(1 for x in reds if x % 2 == 1)
            odd_ok = 2 <= odd <= 4

            # 策略4: 和值 (70-130)
            s = sum(reds)
            sum_ok = 70 <= s <= 130

            # 策略4: 跨度 (15-32)
            span = reds[-1] - reds[0]
            span_ok = 15 <= span <= 32

            # 策略5: 与上一期重号 0-3个
            last_reds = set(records[-1]["红球"])
            overlap = len(set(reds) & last_reds)
            overlap_ok = 0 <= overlap <= 3

            # 策略1: 非历史完全重复
            not_dup = (tuple(reds), blue) not in historical_combos

            # 区间分布: 每个区间至少1个
            z1 = sum(1 for x in reds if 1 <= x <= 11)
            z2 = sum(1 for x in reds if 12 <= x <= 22)
            z3 = sum(1 for x in reds if 23 <= x <= 33)
            zone_ok = z1 >= 1 and z2 >= 1 and z3 >= 1

            if odd_ok and sum_ok and span_ok and overlap_ok and not_dup and zone_ok:
                return {"reds": reds, "blue": blue}

        # 放宽条件兜底
        reds = sorted(weighted_sample(red_score, 6))
        blue = weighted_sample(blue_score, 1)[0]
        return {"reds": reds, "blue": blue}

    random.seed()  # 每次运行不同的结果
    predictions = []
    for i in range(count):
        p = generate_one()
        if p:
            predictions.append(p)

    log.info(f"已生成 {len(predictions)} 组预测号码")
    for idx, p in enumerate(predictions, 1):
        red_str = " ".join(f"{x:02d}" for x in p["reds"])
        log.debug(f"  第{idx}组: 红{red_str} 蓝{p['blue']:02d}")

    return predictions
