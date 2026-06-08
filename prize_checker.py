"""中奖判定 — 双色球6个奖等规则"""


# ── 中奖等级规则 ──
# 一等奖: 6红+1蓝
# 二等奖: 6红+0蓝
# 三等奖: 5红+1蓝
# 四等奖: 5红+0蓝 或 4红+1蓝
# 五等奖: 4红+0蓝 或 3红+1蓝
# 六等奖: 2红+1蓝 或 1红+1蓝 或 0红+1蓝

PRIZE_NAMES = {
    1: "一等奖",
    2: "二等奖",
    3: "三等奖",
    4: "四等奖",
    5: "五等奖",
    6: "六等奖",
}


def check_prize(prediction: dict, result: dict) -> dict:
    """
    判定单组预测的中奖情况

    参数:
        prediction: {"reds": [6个int], "blue": int}
        result:     {"reds": [6个int], "blue": int}

    返回:
        {
            "red_hits": int,        # 红球命中数
            "blue_hit": bool,       # 蓝球是否命中
            "prize_level": int|None, # 中奖等级 (1-6), 未中奖为 None
            "prize_name": str,      # 中奖名称, 未中奖为 "未中奖"
            "hit_reds": list[int],  # 命中的红球号码
        }
    """
    pred_reds = set(prediction["reds"])
    pred_blue = prediction["blue"]
    result_reds = set(result["reds"])
    result_blue = result["blue"]

    hit_reds = sorted(pred_reds & result_reds)
    red_hits = len(hit_reds)
    blue_hit = pred_blue == result_blue

    prize_level = _determine_prize(red_hits, blue_hit)

    return {
        "red_hits": red_hits,
        "blue_hit": blue_hit,
        "prize_level": prize_level,
        "prize_name": PRIZE_NAMES.get(prize_level, "未中奖") if prize_level else "未中奖",
        "hit_reds": hit_reds,
    }


def _determine_prize(red_hits: int, blue_hit: bool) -> int | None:
    """根据红球命中数和蓝球命中判断奖等"""
    if red_hits == 6 and blue_hit:
        return 1
    elif red_hits == 6 and not blue_hit:
        return 2
    elif red_hits == 5 and blue_hit:
        return 3
    elif (red_hits == 5 and not blue_hit) or (red_hits == 4 and blue_hit):
        return 4
    elif (red_hits == 4 and not blue_hit) or (red_hits == 3 and blue_hit):
        return 5
    elif blue_hit and red_hits <= 2:
        return 6
    return None


def check_all_predictions(predictions: list[dict], result: dict) -> list[dict]:
    """
    批量判定所有预测的中奖情况

    参数:
        predictions: [{"reds": [...], "blue": int}, ...]
        result:      {"reds": [...], "blue": int}

    返回:
        [{"index": int, "reds": list, "blue": int, **check_result}, ...]
    """
    results = []
    for i, pred in enumerate(predictions, 1):
        check = check_prize(pred, result)
        results.append({
            "index": i,
            "reds": pred["reds"],
            "blue": pred["blue"],
            **check,
        })
    return results


def has_winning(results: list[dict]) -> bool:
    """是否有任何一组中奖"""
    return any(r["prize_level"] is not None for r in results)


def get_winning_results(results: list[dict]) -> list[dict]:
    """筛选出中奖的预测"""
    return [r for r in results if r["prize_level"] is not None]
