"""数据管理 — 增量获取、存储、加载"""
import csv
import json
import re
from typing import Optional

import requests

from config import API_URL, API_HEADERS, CSV_PATH, JSON_PATH, DATA_DIR
from logger import log


def get_latest_issue() -> str:
    """从 CSV 读取最新期号"""
    if not CSV_PATH.exists():
        return ""
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        last_row = None
        for row in reader:
            last_row = row
        return last_row["期号"] if last_row else ""


def fetch_new_draws() -> list[dict]:
    """调 API 获取最新数据，返回 CSV 行格式的 dict 列表（仅新增期）"""
    latest = get_latest_issue()
    log.info(f"当前最新期号: {latest or '无'}, 开始检查新数据...")

    params = {
        "callback": "jQuery",
        "transactionType": "10001001",
        "lotteryId": "1",
        "issueCount": "10",
        "startIssue": "",
        "endIssue": "",
        "type": "0",
        "pageNum": "1",
        "pageSize": "10",
        "systemType": "1",
    }

    try:
        resp = requests.get(API_URL, params=params, headers=API_HEADERS, timeout=30)
        text = resp.text
        match = re.search(r"jQuery\((.*)\)", text, re.DOTALL)
        if not match:
            log.warning(f"API 返回格式异常: {text[:200]}")
            return []
        data = json.loads(match.group(1))
        if data.get("resCode") and data["resCode"] != "000000":
            log.warning(f"API 返回错误: {data.get('message', '未知错误')}")
            return []
    except Exception as e:
        log.error(f"API 请求失败: {e}")
        return []

    draws = data.get("data", [])
    if not draws:
        log.info("API 未返回数据")
        return []

    # 按 issue 排序（从早到晚）并筛选新期号
    draws.sort(key=lambda x: x["issue"])
    new_draws = []
    for d in draws:
        if not latest or d["issue"] > latest:
            new_draws.append(d)

    if new_draws:
        log.info(f"发现 {len(new_draws)} 期新数据: {new_draws[0]['issue']} ~ {new_draws[-1]['issue']}")
    else:
        log.info("暂无新开奖数据")

    return new_draws


def _api_draw_to_csv_row(draw: dict) -> dict:
    """将 API 返回的单条数据转为 CSV 行格式"""
    reds = draw.get("frontWinningNum", "").split()
    blue = draw.get("backWinningNum", "")
    wd = draw.get("winnerDetails", [])

    def get_winner(etc: str):
        for w in wd:
            if str(w.get("awardEtc")) == str(etc):
                base = w.get("baseBetWinner", {})
                if base:
                    return base.get("awardNum", ""), base.get("awardMoney", "")
        return "", ""

    j1n, j1m = get_winner(1)
    j2n, j2m = get_winner(2)
    j3n, j3m = get_winner(3)
    j4n, j4m = get_winner(4)
    j5n, j5m = get_winner(5)
    j6n, j6m = get_winner(6)

    return {
        "期号": draw.get("issue", ""),
        "开奖日期": draw.get("openTime", ""),
        "红球1": reds[0] if len(reds) > 0 else "",
        "红球2": reds[1] if len(reds) > 1 else "",
        "红球3": reds[2] if len(reds) > 2 else "",
        "红球4": reds[3] if len(reds) > 3 else "",
        "红球5": reds[4] if len(reds) > 4 else "",
        "红球6": reds[5] if len(reds) > 5 else "",
        "蓝球": blue,
        "销售金额": draw.get("saleMoney", ""),
        "奖池金额": draw.get("prizePoolMoney", ""),
        "一等奖注数": j1n,
        "一等奖奖金": j1m,
        "二等奖注数": j2n,
        "二等奖奖金": j2m,
        "三等奖注数": j3n,
        "三等奖奖金": j3m,
        "四等奖注数": j4n,
        "四等奖奖金": j4m,
        "五等奖注数": j5n,
        "五等奖奖金": j5m,
        "六等奖注数": j6n,
        "六等奖奖金": j6m,
    }


def append_to_csv(new_draws: list[dict]) -> None:
    """增量追加到 CSV 文件"""
    if not new_draws:
        return

    fieldnames = [
        "期号", "开奖日期", "红球1", "红球2", "红球3", "红球4", "红球5", "红球6",
        "蓝球", "销售金额", "奖池金额",
        "一等奖注数", "一等奖奖金", "二等奖注数", "二等奖奖金",
        "三等奖注数", "三等奖奖金", "四等奖注数", "四等奖奖金",
        "五等奖注数", "五等奖奖金", "六等奖注数", "六等奖奖金",
    ]

    rows = [_api_draw_to_csv_row(d) for d in new_draws]

    with open(CSV_PATH, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        for row in rows:
            writer.writerow(row)

    log.info(f"CSV 已追加 {len(rows)} 条记录")


def append_to_json(new_draws: list[dict]) -> None:
    """增量追加到 JSON 文件"""
    if not new_draws:
        return

    # 读取现有数据
    if JSON_PATH.exists():
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)
    else:
        existing = []

    # 追加新数据（按 issue 排序）
    existing_issues = {r["issue"] for r in existing}
    for d in new_draws:
        if d["issue"] not in existing_issues:
            existing.append(d)

    existing.sort(key=lambda x: x["issue"])

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    log.info(f"JSON 已追加 {len(new_draws)} 条记录, 总计 {len(existing)} 条")


def load_data() -> list[dict]:
    """加载全量 CSV 数据，返回结构化列表"""
    records = []
    if not CSV_PATH.exists():
        log.warning(f"CSV 文件不存在: {CSV_PATH}")
        return records

    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            reds = [int(row[f"红球{i}"]) for i in range(1, 7)]
            blue = int(row["蓝球"])
            records.append({
                "期号": row["期号"],
                "日期": row["开奖日期"],
                "红球": reds,
                "蓝球": blue,
            })

    return records
