"""预测引擎 — 基于5大策略 + 补充策略生成号码，每组采用不同策略侧重"""
import random
from collections import Counter
from typing import Optional

from logger import log


# ── 策略档案定义 ──

STRATEGY_PROFILES = [
    # 热门号组
    {"name": "热门号优先",     "red_weight": "boost_hot",  "blue_weight": None,          "extra": []},
    {"name": "热门号+连号",   "red_weight": "boost_hot",  "blue_weight": None,          "extra": ["must_consecutive"]},
    {"name": "热门号+重号",   "red_weight": "boost_hot",  "blue_weight": None,          "extra": ["overlap_1"]},
    # 冷门号组
    {"name": "冷门号优先",     "red_weight": "boost_cold", "blue_weight": None,          "extra": []},
    {"name": "冷门号+连号",   "red_weight": "boost_cold", "blue_weight": None,          "extra": ["must_consecutive"]},
    {"name": "冷门号+重号",   "red_weight": "boost_cold", "blue_weight": None,          "extra": ["overlap_1"]},
    # 连号组
    {"name": "双连号",         "red_weight": None,         "blue_weight": None,          "extra": ["must_consecutive"]},
    {"name": "三连号尝试",     "red_weight": None,         "blue_weight": None,          "extra": ["must_triple_consecutive"]},
    {"name": "连号+重号",     "red_weight": None,         "blue_weight": None,          "extra": ["must_consecutive", "overlap_1"]},
    # 重号组
    {"name": "重号1个",       "red_weight": None,         "blue_weight": None,          "extra": ["overlap_1"]},
    {"name": "重号2个",       "red_weight": None,         "blue_weight": None,          "extra": ["overlap_2"]},
    # AC值组
    {"name": "高AC值",         "red_weight": None,         "blue_weight": None,          "extra": ["ac_high"]},
    {"name": "中AC值+连号",   "red_weight": None,         "blue_weight": None,          "extra": ["ac_medium", "must_consecutive"]},
    # 尾数组
    {"name": "尾数分散",       "red_weight": None,         "blue_weight": None,          "extra": ["tail_diverse"]},
    {"name": "热尾偏重",       "red_weight": "boost_hot_tail", "blue_weight": None,      "extra": []},
    # 蓝球侧重
    {"name": "热门蓝球",       "red_weight": None,         "blue_weight": "boost_hot",   "extra": []},
    {"name": "冷门蓝球",       "red_weight": None,         "blue_weight": "boost_cold",  "extra": []},
    # 结构组
    {"name": "均衡3:3奇偶",   "red_weight": None,         "blue_weight": None,          "extra": ["odd_even_3_3"]},
    {"name": "均衡2:2:2区间", "red_weight": None,         "blue_weight": None,          "extra": ["zone_222"]},
    {"name": "经典均衡",       "red_weight": None,         "blue_weight": None,          "extra": []},
]


# ── 辅助函数 ──

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


def _check_extra_constraints(reds: list[int], last_reds: set,
                              constraints: list[str]) -> bool:
    """检查额外策略约束，全部满足返回 True"""
    for c in constraints:
        if c == "must_consecutive":
            if not any(reds[i + 1] == reds[i] + 1 for i in range(len(reds) - 1)):
                return False
        elif c == "must_triple_consecutive":
            # 至少3连号
            count = 1
            found = False
            for i in range(1, len(reds)):
                if reds[i] == reds[i - 1] + 1:
                    count += 1
                    if count >= 3:
                        found = True
                        break
                else:
                    count = 1
            if not found:
                return False
        elif c == "overlap_1":
            if len(set(reds) & last_reds) != 1:
                return False
        elif c == "overlap_2":
            if len(set(reds) & last_reds) != 2:
                return False
        elif c == "ac_high":
            if _calc_ac(reds) < 8:
                return False
        elif c == "ac_medium":
            ac = _calc_ac(reds)
            if not (6 <= ac <= 8):
                return False
        elif c == "tail_diverse":
            if len(set(x % 10 for x in reds)) != 6:
                return False
        elif c == "odd_even_3_3":
            if sum(1 for x in reds if x % 2 == 1) != 3:
                return False
        elif c == "zone_222":
            z1 = sum(1 for x in reds if 1 <= x <= 11)
            z2 = sum(1 for x in reds if 12 <= x <= 22)
            z3 = sum(1 for x in reds if 23 <= x <= 33)
            if not (z1 == 2 and z2 == 2 and z3 == 2):
                return False
    return True


def _apply_weight_override(base_scores: dict, override_type: str,
                            hot_nums: list, cold_nums: list,
                            tail_freq: dict = None) -> dict:
    """根据策略类型调整权重"""
    scores = base_scores.copy()
    if override_type == "boost_hot":
        for num in hot_nums:
            scores[num] = scores.get(num, 0) * 2.0
    elif override_type == "boost_cold":
        for num in cold_nums:
            scores[num] = scores.get(num, 0) * 2.0
        for num in hot_nums:
            scores[num] = scores.get(num, 0) * 0.5
    elif override_type == "boost_hot_tail":
        if tail_freq:
            for num in scores:
                tail = num % 10
                scores[num] = scores.get(num, 0) * (1 + tail_freq.get(tail, 0) * 0.5)
    return scores


def _generate_reason(reds: list[int], blue: int, profile: dict,
                     last_reds: set, hot_reds: list, cold_reds: list,
                     hot_blues: list, cold_blues: list) -> str:
    """根据实际选号结果分析特征，生成原因字符串"""
    parts = [f"【{profile['name']}】"]

    # 连号
    cons = _count_consecutive(reds)
    if cons:
        cons_str = ",".join("-".join(str(x) for x in g) for g in cons)
        parts.append(f"连号{cons_str}")

    # 与上期重号
    overlap = set(reds) & last_reds
    if overlap:
        overlap_str = ",".join(f"{x:02d}" for x in sorted(overlap))
        parts.append(f"与上期重号{overlap_str}")

    # 热门号
    hot_in = [x for x in reds if x in hot_reds]
    if hot_in:
        parts.append("热门" + ",".join(f"{x:02d}" for x in hot_in))

    # 冷门号
    cold_in = [x for x in reds if x in cold_reds]
    if cold_in:
        parts.append("冷门" + ",".join(f"{x:02d}" for x in cold_in))

    # 蓝球冷热
    if blue in hot_blues:
        parts.append(f"蓝{blue:02d}热门")
    elif blue in cold_blues:
        parts.append(f"蓝{blue:02d}冷门")

    # AC值
    ac = _calc_ac(reds)
    if ac >= 8:
        parts.append(f"AC={ac}(高)")

    # 奇偶比
    odd = sum(1 for x in reds if x % 2 == 1)
    parts.append(f"奇偶{odd}:{6-odd}")

    return " ".join(parts)


# ── 主函数 ──

def generate_predictions(records: list[dict], count: int = 20) -> list[dict]:
    """
    基于策略生成预测号码（每组采用不同策略侧重）

    参数:
        records: 历史数据列表, 每项 {"期号", "日期", "红球": [6个int], "蓝球": int}
        count: 生成组数

    返回:
        [{"reds": [6个int], "blue": int, "reason": str, "strategy_name": str}, ...]
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

    # 热门/冷门号码列表
    recent_red_sorted = sorted(recent_red.items(), key=lambda x: -x[1])
    hot_reds = [n for n, _ in recent_red_sorted[:10]]
    cold_reds = [n for n, _ in recent_red_sorted[-10:]]

    recent_blue_sorted = sorted(recent_blue.items(), key=lambda x: -x[1])
    hot_blues = [n for n, _ in recent_blue_sorted[:3]]
    cold_blues = [n for n, _ in recent_blue_sorted[-3:]]

    # 历史蓝球热门/冷门
    hist_blue_sorted = sorted(blue_counter.items(), key=lambda x: -x[1])
    hist_hot_blues = [n for n, _ in hist_blue_sorted[:5]]
    hist_cold_blues = [n for n, _ in hist_blue_sorted[-5:]]

    # 尾数频率 (用于热尾偏重策略)
    tail_counter = Counter()
    for r in records:
        for x in r["红球"]:
            tail_counter[x % 10] += 1
    max_tail = max(tail_counter.values()) if tail_counter else 1
    tail_freq = {t: c / max_tail for t, c in tail_counter.items()}

    # 上一期红球
    last_reds = set(records[-1]["红球"])

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

    def generate_one(profile: dict) -> Optional[dict]:
        # 根据策略调整权重
        r_score = _apply_weight_override(
            red_score, profile["red_weight"],
            hot_reds, cold_reds, tail_freq
        ) if profile["red_weight"] else red_score

        b_score = _apply_weight_override(
            blue_score, profile["blue_weight"],
            hist_hot_blues, hist_cold_blues
        ) if profile["blue_weight"] == "boost_hot" else (
            _apply_weight_override(
                blue_score, profile["blue_weight"],
                hist_hot_blues, hist_cold_blues
            ) if profile["blue_weight"] == "boost_cold" else blue_score
        )

        for attempt in range(200):
            reds = sorted(weighted_sample(r_score, 6))
            blue = weighted_sample(b_score, 1)[0]

            # 基础约束
            odd = sum(1 for x in reds if x % 2 == 1)
            odd_ok = 2 <= odd <= 4

            s = sum(reds)
            sum_ok = 70 <= s <= 130

            span = reds[-1] - reds[0]
            span_ok = 15 <= span <= 32

            overlap = len(set(reds) & last_reds)
            overlap_ok = 0 <= overlap <= 3

            not_dup = (tuple(reds), blue) not in historical_combos

            z1 = sum(1 for x in reds if 1 <= x <= 11)
            z2 = sum(1 for x in reds if 12 <= x <= 22)
            z3 = sum(1 for x in reds if 23 <= x <= 33)
            zone_ok = z1 >= 1 and z2 >= 1 and z3 >= 1

            # 基础约束
            if not (odd_ok and sum_ok and span_ok and overlap_ok and not_dup and zone_ok):
                continue

            # 额外策略约束
            if not _check_extra_constraints(reds, last_reds, profile["extra"]):
                continue

            # 生成原因
            reason = _generate_reason(
                reds, blue, profile, last_reds,
                hot_reds, cold_reds,
                hist_hot_blues, hist_cold_blues
            )

            return {"reds": reds, "blue": blue, "reason": reason, "strategy_name": profile["name"]}

        # 兜底：放宽额外约束，仅保留基础约束
        for attempt in range(100):
            reds = sorted(weighted_sample(r_score, 6))
            blue = weighted_sample(b_score, 1)[0]

            odd = sum(1 for x in reds if x % 2 == 1)
            odd_ok = 2 <= odd <= 4
            s = sum(reds)
            sum_ok = 70 <= s <= 130
            span = reds[-1] - reds[0]
            span_ok = 15 <= span <= 32
            overlap = len(set(reds) & last_reds)
            overlap_ok = 0 <= overlap <= 3
            not_dup = (tuple(reds), blue) not in historical_combos
            z1 = sum(1 for x in reds if 1 <= x <= 11)
            z2 = sum(1 for x in reds if 12 <= x <= 22)
            z3 = sum(1 for x in reds if 23 <= x <= 33)
            zone_ok = z1 >= 1 and z2 >= 1 and z3 >= 1

            if odd_ok and sum_ok and span_ok and overlap_ok and not_dup and zone_ok:
                reason = _generate_reason(
                    reds, blue, profile, last_reds,
                    hot_reds, cold_reds,
                    hist_hot_blues, hist_cold_blues
                ) + " [兜底]"
                return {"reds": reds, "blue": blue, "reason": reason, "strategy_name": profile["name"]}

        # 最终兜底：完全放宽
        reds = sorted(weighted_sample(r_score, 6))
        blue = weighted_sample(b_score, 1)[0]
        reason = _generate_reason(
            reds, blue, profile, last_reds,
            hot_reds, cold_reds,
            hist_hot_blues, hist_cold_blues
        ) + " [兜底]"
        return {"reds": reds, "blue": blue, "reason": reason, "strategy_name": profile["name"]}

    random.seed()  # 每次运行不同的结果
    predictions = []
    seen_combos = set()

    # 确保使用足够的策略档案
    profiles = list(STRATEGY_PROFILES)
    while len(profiles) < count:
        profiles.extend(STRATEGY_PROFILES)
    profiles = profiles[:count]

    for i in range(count):
        profile = profiles[i]
        p = generate_one(profile)
        if p:
            # 去重
            combo_key = (tuple(p["reds"]), p["blue"])
            if combo_key in seen_combos:
                # 重新尝试最多10次
                for _ in range(10):
                    p = generate_one(profile)
                    if p:
                        combo_key = (tuple(p["reds"]), p["blue"])
                        if combo_key not in seen_combos:
                            break
            if p:
                seen_combos.add(combo_key)
                predictions.append(p)

    log.info(f"已生成 {len(predictions)} 组预测号码")
    for idx, p in enumerate(predictions, 1):
        red_str = " ".join(f"{x:02d}" for x in p["reds"])
        log.debug(f"  第{idx}组[{p['strategy_name']}]: 红{red_str} 蓝{p['blue']:02d} | {p['reason']}")

    return predictions
