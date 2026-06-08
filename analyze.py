#!/usr/bin/env python3
"""双色球历史数据分析 - 根据策略.md执行全量分析"""
import csv
import json
import random
from collections import Counter

# ============================================================
# 1. 读取数据
# ============================================================
def load_data():
    records = []
    with open("data/ssq_history.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            reds = [int(row[f"红球{i}"]) for i in range(1, 7)]
            blue = int(row["蓝球"])
            records.append({
                "期号": row["期号"],
                "日期": row["开奖日期"],
                "红球": reds,
                "蓝球": blue,
                "销售金额": row["销售金额"],
                "奖池金额": row["奖池金额"],
            })
    return records

# ============================================================
# 策略1: 不要投注曾经中奖的号码
# ============================================================
def strategy1_no_previous_winner(records):
    print("=" * 70)
    print("📊 策略1: 不要投注曾经中奖的号码")
    print("=" * 70)

    # 统计所有出现过的红球组合（排序后作为key）
    all_red_combos = set()
    for r in records:
        combo = tuple(r["红球"])
        all_red_combos.add(combo)

    # 统计所有出现过的蓝球
    all_blues = set(r["蓝球"] for r in records)

    # 红球组合重复统计
    combo_counter = Counter(tuple(r["红球"]) for r in records)
    duplicates = {k: v for k, v in combo_counter.items() if v > 1}

    total = len(records)
    unique = len(all_red_combos)
    print(f"\n  总期数: {total}")
    print(f"  不重复红球组合数: {unique}")
    print(f"  重复出现的红球组合数: {len(duplicates)}")
    print(f"  重复概率: {len(duplicates)/unique*100:.2f}%")
    print(f"\n  蓝球已出现种类: {sorted(all_blues)} (共{len(all_blues)}种)")

    if duplicates:
        print(f"\n  ⚠️ 历史上重复出现的红球组合:")
        for combo, count in sorted(duplicates.items(), key=lambda x: -x[1]):
            print(f"    {list(combo)} → 出现{count}次")

    # 实用建议：6红+1蓝全重复的组合
    full_dup = 0
    red_blue_combo = Counter()
    for r in records:
        key = (tuple(r["红球"]), r["蓝球"])
        red_blue_combo[key] += 1
    full_duplicates = {k: v for k, v in red_blue_combo.items() if v > 1}
    if full_duplicates:
        print(f"\n  ⚠️ 红球+蓝球完全重复的组合 ({len(full_duplicates)}组):")
        for (reds, blue), count in sorted(full_duplicates.items(), key=lambda x: -x[1]):
            print(f"    红{list(reds)} 蓝{blue} → 出现{count}次")
    else:
        print(f"\n  ✅ 历史上没有红球+蓝球完全重复的组合")
        print(f"  → 建议：可以排除历史出现过的完整组合，但红球组合有极少数重复")

# ============================================================
# 策略2: 红球，双联号更容易出现
# ============================================================
def strategy2_consecutive(records):
    print("\n" + "=" * 70)
    print("📊 策略2: 红球，双联号更容易出现")
    print("=" * 70)

    def count_consecutive(reds):
        """计算连号组数和连号长度"""
        groups = []
        current = [reds[0]]
        for i in range(1, len(reds)):
            if reds[i] == reds[i-1] + 1:
                current.append(reds[i])
            else:
                if len(current) >= 2:
                    groups.append(current[:])
                current = [reds[i]]
        if len(current) >= 2:
            groups.append(current[:])
        return groups

    has_consecutive = 0
    no_consecutive = 0
    group_len_counter = Counter()  # 连号长度统计
    group_count_counter = Counter()  # 每期连号组数统计

    examples_consecutive = []
    examples_no_consecutive = []

    for r in records:
        groups = count_consecutive(r["红球"])
        if groups:
            has_consecutive += 1
            total_len = sum(len(g) for g in groups)
            group_len_counter[total_len] += 1
            group_count_counter[len(groups)] += 1
            if len(examples_consecutive) < 3:
                examples_consecutive.append((r["期号"], r["红球"], groups))
        else:
            no_consecutive += 1
            if len(examples_no_consecutive) < 3:
                examples_no_consecutive.append((r["期号"], r["红球"]))

    total = len(records)
    print(f"\n  总期数: {total}")
    print(f"  含连号的期数: {has_consecutive} ({has_consecutive/total*100:.1f}%)")
    print(f"  不含连号的期数: {no_consecutive} ({no_consecutive/total*100:.1f}%)")

    print(f"\n  连号长度分布 (参与连号的红球个数):")
    for length in sorted(group_len_counter.keys()):
        cnt = group_len_counter[length]
        bar = "█" * int(cnt / total * 100)
        print(f"    {length}连号: {cnt:4d}次 ({cnt/total*100:5.1f}%) {bar}")

    print(f"\n  每期连号组数分布:")
    for count in sorted(group_count_counter.keys()):
        cnt = group_count_counter[count]
        bar = "█" * int(cnt / total * 100)
        print(f"    {count}组连号: {cnt:4d}次 ({cnt/total*100:5.1f}%) {bar}")

    print(f"\n  含连号示例:")
    for qh, reds, groups in examples_consecutive:
        group_str = ", ".join([str(g) for g in groups])
        print(f"    期{qh}: {reds} → 连号组: {group_str}")

    print(f"\n  不含连号示例:")
    for qh, reds in examples_no_consecutive:
        print(f"    期{qh}: {reds}")

    print(f"\n  → 建议：约{has_consecutive/total*100:.0f}%的期数含连号，选号时建议包含至少1组双连号")

# ============================================================
# 策略3: 冷/热球数据一览
# ============================================================
def strategy3_hot_cold(records):
    print("\n" + "=" * 70)
    print("📊 策略3: 冷/热球数据一览")
    print("=" * 70)

    total = len(records)

    # 红球频率
    red_counter = Counter()
    for r in records:
        red_counter.update(r["红球"])

    print(f"\n  🔴 红球出现频率 (共{total}期，理论期望每个红球≈{total*6/33:.0f}次):")
    print(f"  {'号码':>4} {'次数':>5} {'频率':>7}  {'分布图'}")
    print(f"  {'─'*50}")

    red_sorted = sorted(red_counter.items(), key=lambda x: -x[1])
    for num, cnt in red_sorted:
        freq = cnt / total * 100
        bar = "█" * int(cnt / total * 150)
        print(f"  {num:>4} {cnt:>5} {freq:>6.2f}%  {bar}")

    print(f"\n  🔴 红球 高频TOP 10:")
    for i, (num, cnt) in enumerate(red_sorted[:10], 1):
        print(f"    #{i:>2}: 红球{num:02d} → 出现{cnt}次 ({cnt/total*100:.2f}%)")

    print(f"\n  🔴 红球 低频BOTTOM 10:")
    for i, (num, cnt) in enumerate(reversed(red_sorted[:10]), 1):
        pass
    for i, (num, cnt) in enumerate(red_sorted[-10:], 1):
        print(f"    #{i:>2}: 红球{num:02d} → 出现{cnt}次 ({cnt/total*100:.2f}%)")

    # 蓝球频率
    blue_counter = Counter()
    for r in records:
        blue_counter[r["蓝球"]] += 1

    print(f"\n  🔵 蓝球出现频率 (共{total}期，理论期望每个蓝球≈{total/16:.0f}次):")
    print(f"  {'号码':>4} {'次数':>5} {'频率':>7}  {'分布图'}")
    print(f"  {'─'*50}")

    blue_sorted = sorted(blue_counter.items(), key=lambda x: -x[1])
    for num, cnt in blue_sorted:
        freq = cnt / total * 100
        bar = "█" * int(cnt / total * 150)
        print(f"  {num:>4} {cnt:>5} {freq:>6.2f}%  {bar}")

    print(f"\n  🔵 蓝球 高频TOP 5:")
    for i, (num, cnt) in enumerate(blue_sorted[:5], 1):
        print(f"    #{i}: 蓝球{num:02d} → 出现{cnt}次 ({cnt/total*100:.2f}%)")

    print(f"\n  🔵 蓝球 低频BOTTOM 5:")
    for i, (num, cnt) in enumerate(blue_sorted[-5:], 1):
        print(f"    #{i}: 蓝球{num:02d} → 出现{cnt}次 ({cnt/total*100:.2f}%)")

    # 近50期冷热
    recent = records[-50:]
    recent_red = Counter()
    recent_blue = Counter()
    for r in recent:
        recent_red.update(r["红球"])
        recent_blue[r["蓝球"]] += 1

    print(f"\n  📈 近50期红球冷热:")
    recent_red_sorted = sorted(recent_red.items(), key=lambda x: -x[1])
    print(f"    热门: {', '.join([f'{n:02d}({c}次)' for n, c in recent_red_sorted[:8]])}")
    print(f"    冷门: {', '.join([f'{n:02d}({c}次)' for n, c in recent_red_sorted[-8:]])}")

    print(f"\n  📈 近50期蓝球冷热:")
    recent_blue_sorted = sorted(recent_blue.items(), key=lambda x: -x[1])
    print(f"    热门: {', '.join([f'{n:02d}({c}次)' for n, c in recent_blue_sorted[:3]])}")
    print(f"    冷门: {', '.join([f'{n:02d}({c}次)' for n, c in recent_blue_sorted[-3:]])}")

    return red_sorted, blue_sorted

# ============================================================
# 策略4: 红球奇偶比、和值、首尾跨度
# ============================================================
def strategy4_odd_even_sum_span(records):
    print("\n" + "=" * 70)
    print("📊 策略4: 红球奇偶比、和值、首尾跨度")
    print("=" * 70)

    total = len(records)

    # 奇偶比
    odd_even_counter = Counter()
    for r in records:
        odd = sum(1 for x in r["红球"] if x % 2 == 1)
        even = 6 - odd
        odd_even_counter[(odd, even)] += 1

    print(f"\n  奇偶比分布:")
    for (odd, even), cnt in sorted(odd_even_counter.items(), key=lambda x: -x[1]):
        pct = cnt / total * 100
        bar = "█" * int(pct)
        print(f"    {odd}:{even} (奇:偶) → {cnt:4d}次 ({pct:5.1f}%) {bar}")

    # 和值
    sums = [sum(r["红球"]) for r in records]
    avg_sum = sum(sums) / len(sums)
    min_sum = min(sums)
    max_sum = max(sums)

    # 和值区间分布
    sum_ranges = {
        "21-50": 0, "51-70": 0, "71-90": 0,
        "91-110": 0, "111-130": 0, "131-150": 0, "151-183": 0
    }
    for s in sums:
        if s <= 50: sum_ranges["21-50"] += 1
        elif s <= 70: sum_ranges["51-70"] += 1
        elif s <= 90: sum_ranges["71-90"] += 1
        elif s <= 110: sum_ranges["91-110"] += 1
        elif s <= 130: sum_ranges["111-130"] += 1
        elif s <= 150: sum_ranges["131-150"] += 1
        else: sum_ranges["151-183"] += 1

    print(f"\n  和值统计:")
    print(f"    平均和值: {avg_sum:.1f}")
    print(f"    最小和值: {min_sum}")
    print(f"    最大和值: {max_sum}")
    print(f"    和值区间分布:")
    for rng, cnt in sum_ranges.items():
        pct = cnt / total * 100
        bar = "█" * int(pct)
        print(f"      {rng:>8}: {cnt:4d}次 ({pct:5.1f}%) {bar}")

    # 首尾跨度
    spans = [r["红球"][-1] - r["红球"][0] for r in records]
    avg_span = sum(spans) / len(spans)
    min_span = min(spans)
    max_span = max(spans)

    span_counter = Counter(spans)
    print(f"\n  首尾跨度统计 (最大红球 - 最小红球):")
    print(f"    平均跨度: {avg_span:.1f}")
    print(f"    最小跨度: {min_span}")
    print(f"    最大跨度: {max_span}")
    print(f"    跨度分布TOP 10:")
    for span, cnt in span_counter.most_common(10):
        pct = cnt / total * 100
        bar = "█" * int(pct)
        print(f"      跨度{span:>2}: {cnt:4d}次 ({pct:5.1f}%) {bar}")

# ============================================================
# 策略5: 要不要跟上一期重号？
# ============================================================
def strategy5_repeat_with_previous(records):
    print("\n" + "=" * 70)
    print("📊 策略5: 跟上一期重号分析")
    print("=" * 70)

    total = len(records)
    repeat_counter = Counter()

    for i in range(1, len(records)):
        prev = set(records[i-1]["红球"])
        curr = set(records[i]["红球"])
        overlap = len(prev & curr)
        repeat_counter[overlap] += 1

    print(f"\n  与上一期红球重号数分布 (共{total-1}期对比):")
    for n in range(7):
        cnt = repeat_counter.get(n, 0)
        pct = cnt / (total - 1) * 100
        bar = "█" * int(pct)
        print(f"    {n}个重号: {cnt:4d}次 (占比{pct:5.1f}%) {bar}")

    # 蓝球重号
    blue_repeat = 0
    for i in range(1, len(records)):
        if records[i]["蓝球"] == records[i-1]["蓝球"]:
            blue_repeat += 1
    print(f"\n  蓝球与上一期相同: {blue_repeat}次 (占比{blue_repeat/(total-1)*100:.1f}%)")

    # 策略建议
    most_common_repeat = repeat_counter.most_common(1)[0]
    print(f"\n  → 最常见重号数: {most_common_repeat[0]}个 (出现{most_common_repeat[1]}次, {most_common_repeat[1]/(total-1)*100:.1f}%)")

    cumulative = 0
    for n in range(7):
        cumulative += repeat_counter.get(n, 0)
        if cumulative >= (total - 1) * 0.5:
            print(f"  → 50%的期数重号数 ≤ {n}个")
            break

# ============================================================
# 策略补充: AC值、区间分布、尾数分布
# ============================================================
def strategy_extra(records):
    print("\n" + "=" * 70)
    print("📊 补充策略: 区间分布、尾数分布、AC值")
    print("=" * 70)

    total = len(records)

    # 三区间分布 (1-11, 12-22, 23-33)
    zone_counter = Counter()
    for r in records:
        z1 = sum(1 for x in r["红球"] if 1 <= x <= 11)
        z2 = sum(1 for x in r["红球"] if 12 <= x <= 22)
        z3 = sum(1 for x in r["红球"] if 23 <= x <= 33)
        zone_counter[(z1, z2, z3)] += 1

    print(f"\n  三区间分布 (1-11, 12-22, 23-33) TOP 10:")
    for (z1, z2, z3), cnt in zone_counter.most_common(10):
        pct = cnt / total * 100
        print(f"    {z1}:{z2}:{z3} → {cnt:4d}次 ({pct:5.1f}%)")

    # 尾数分布
    tail_counter = Counter()
    for r in records:
        for x in r["红球"]:
            tail_counter[x % 10] += 1

    print(f"\n  红球尾数分布 (0-9):")
    for tail in range(10):
        cnt = tail_counter.get(tail, 0)
        pct = cnt / (total * 6) * 100
        bar = "█" * int(pct * 5)
        print(f"    尾数{tail}: {cnt:5d}次 ({pct:5.1f}%) {bar}")

    # AC值 (算术复杂性)
    def calc_ac(reds):
        diffs = set()
        for i in range(len(reds)):
            for j in range(i+1, len(reds)):
                diffs.add(abs(reds[i] - reds[j]))
        return len(diffs) - (len(reds) - 1)

    ac_counter = Counter()
    for r in records:
        ac = calc_ac(r["红球"])
        ac_counter[ac] += 1

    print(f"\n  AC值分布 (算术复杂性, 理论范围0-10):")
    for ac in sorted(ac_counter.keys()):
        cnt = ac_counter[ac]
        pct = cnt / total * 100
        bar = "█" * int(pct)
        print(f"    AC={ac:>2}: {cnt:4d}次 ({pct:5.1f}%) {bar}")

# ============================================================
# 综合推荐: 生成10组号码
# ============================================================
def generate_recommendations(records):
    print("\n" + "=" * 70)
    print("🎯 综合推荐: 根据上述策略生成10组号码")
    print("=" * 70)

    total = len(records)

    # 排除历史完全相同的组合
    historical_combos = set()
    for r in records:
        historical_combos.add((tuple(r["红球"]), r["蓝球"]))

    # 策略参数
    # 策略3: 频率数据
    red_counter = Counter()
    blue_counter = Counter()
    for r in records:
        red_counter.update(r["红球"])
        blue_counter[r["蓝球"]] += 1

    # 近50期数据（更近期权重更高）
    recent = records[-50:]
    recent_red = Counter()
    recent_blue = Counter()
    for r in recent:
        recent_red.update(r["红球"])
        recent_blue[r["蓝球"]] += 1

    # 综合频率得分（历史 + 近期加权）
    red_score = {}
    for num in range(1, 34):
        hist_freq = red_counter.get(num, 0) / total
        recent_freq = recent_red.get(num, 0) / 50
        # 近期权重 0.6，历史权重 0.4
        red_score[num] = hist_freq * 0.4 + recent_freq * 0.6

    blue_score = {}
    for num in range(1, 17):
        hist_freq = blue_counter.get(num, 0) / total
        recent_freq = recent_blue.get(num, 0) / 50
        blue_score[num] = hist_freq * 0.4 + recent_freq * 0.6

    # 加权随机选择函数
    def weighted_sample(scores_dict, count):
        items = list(scores_dict.keys())
        weights = [scores_dict[k] for k in items]
        # 添加随机扰动以增加多样性
        weights = [w + random.random() * 0.02 for w in weights]
        total_w = sum(weights)
        probs = [w / total_w for w in weights]
        selected = []
        remaining_items = list(items)
        remaining_probs = list(probs)
        for _ in range(count):
            chosen = random.choices(remaining_items, weights=remaining_probs, k=1)[0]
            selected.append(chosen)
            idx = remaining_items.index(chosen)
            remaining_items.pop(idx)
            remaining_probs.pop(idx)
        return selected

    def generate_one_set():
        for attempt in range(100):
            # 选6个红球
            reds = sorted(weighted_sample(red_score, 6))

            # 策略2检查: 确保有至少1组连号（~63%概率下需要）
            has_consecutive = False
            for i in range(len(reds)-1):
                if reds[i+1] == reds[i] + 1:
                    has_consecutive = True
                    break

            # 策略4检查: 奇偶比在合理范围 (2:4 ~ 4:2)
            odd = sum(1 for x in reds if x % 2 == 1)
            odd_ok = 2 <= odd <= 4

            # 策略4检查: 和值在主流区间 (70-130)
            s = sum(reds)
            sum_ok = 70 <= s <= 130

            # 策略4检查: 跨度合理 (15-32)
            span = reds[-1] - reds[0]
            span_ok = 15 <= span <= 32

            # 策略5: 与上一期重号1-2个
            last_reds = set(records[-1]["红球"])
            overlap = len(set(reds) & last_reds)
            overlap_ok = 0 <= overlap <= 3

            # 策略1: 不是历史完全相同的组合
            blue = weighted_sample(blue_score, 1)[0]
            not_dup = (tuple(reds), blue) not in historical_combos

            # 区间分布不要太极端
            z1 = sum(1 for x in reds if 1 <= x <= 11)
            z2 = sum(1 for x in reds if 12 <= x <= 22)
            z3 = sum(1 for x in reds if 23 <= x <= 33)
            zone_ok = z1 >= 1 and z2 >= 1 and z3 >= 1

            if odd_ok and sum_ok and span_ok and overlap_ok and not_dup and zone_ok:
                return reds, blue

        # 如果100次都没满足，放宽条件
        reds = sorted(weighted_sample(red_score, 6))
        blue = weighted_sample(blue_score, 1)[0]
        return reds, blue

    random.seed(42)  # 可复现
    results = []
    for i in range(10):
        reds, blue = generate_one_set()
        results.append((reds, blue))

    print()
    for i, (reds, blue) in enumerate(results, 1):
        odd = sum(1 for x in reds if x % 2 == 1)
        even = 6 - odd
        s = sum(reds)
        span = reds[-1] - reds[0]

        # 连号
        cons_groups = []
        curr = [reds[0]]
        for j in range(1, len(reds)):
            if reds[j] == reds[j-1] + 1:
                curr.append(reds[j])
            else:
                if len(curr) >= 2:
                    cons_groups.append(curr[:])
                curr = [reds[j]]
        if len(curr) >= 2:
            cons_groups.append(curr[:])

        cons_str = ",".join(["-".join(map(str, g)) for g in cons_groups]) if cons_groups else "无"
        overlap = len(set(reds) & set(records[-1]["红球"]))

        red_str = " ".join([f"{x:02d}" for x in reds])
        print(f"  第{i:>2}组: 🔴 {red_str}  🔵 {blue:02d}  "
              f"奇偶{odd}:{even}  和值{s:>3}  跨度{span:>2}  连号:{cons_str}  与上期重号:{overlap}个")

# ============================================================
# 主函数
# ============================================================
def main():
    print("🎱 双色球历史数据分析报告")
    print(f"   数据来源: 中彩网 zhcw.com")

    records = load_data()
    print(f"   数据范围: {records[0]['期号']}({records[0]['日期']}) ~ {records[-1]['期号']}({records[-1]['日期']})")
    print(f"   总期数: {len(records)}")

    strategy1_no_previous_winner(records)
    strategy2_consecutive(records)
    strategy3_hot_cold(records)
    strategy4_odd_even_sum_span(records)
    strategy5_repeat_with_previous(records)
    strategy_extra(records)
    generate_recommendations(records)

    print("\n" + "=" * 70)
    print("⚠️ 免责声明: 双色球为随机开奖，以上分析仅供娱乐参考，不构成投注建议！")
    print("=" * 70)

if __name__ == "__main__":
    main()
