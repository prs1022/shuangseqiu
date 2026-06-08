#!/usr/bin/env python3
"""下载双色球全部历史开奖数据"""
import requests
import json
import time
import csv
import os
import re

URL = "https://jc.zhcw.com/port/client_json.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://www.zhcw.com/kjxx/ssq/"
}

def fetch_page(page_num, page_size=100):
    params = {
        "callback": "jQuery",
        "transactionType": "10001001",
        "lotteryId": "1",
        "issueCount": "9999",
        "startIssue": "",
        "endIssue": "",
        "type": "0",
        "pageNum": str(page_num),
        "pageSize": str(page_size),
        "systemType": "1"
    }
    resp = requests.get(URL, params=params, headers=HEADERS, timeout=30)
    text = resp.text
    # Remove JSONP wrapper: jQuery({...})
    match = re.search(r'jQuery\((.*)\)', text, re.DOTALL)
    if not match:
        raise ValueError(f"Invalid JSONP response: {text[:200]}")
    return json.loads(match.group(1))

def main():
    print("正在获取数据总量...")
    first = fetch_page(1, 100)
    total = int(first['total'])
    pages = int(first['pages'])
    print(f"共 {total} 条记录，{pages} 页")

    all_data = list(first['data'])
    print(f"第 1 页已下载，共 {len(first['data'])} 条")

    for page in range(2, pages + 1):
        time.sleep(0.3)  # 避免请求过快
        result = fetch_page(page, 100)
        all_data.extend(result['data'])
        print(f"第 {page}/{pages} 页已下载，累计 {len(all_data)} 条")

    # 按期号排序（从早到晚）
    all_data.sort(key=lambda x: x['issue'])

    # 保存为 JSON
    os.makedirs("data", exist_ok=True)
    json_path = "data/ssq_history.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    print(f"\nJSON 已保存: {json_path} ({len(all_data)} 条)")

    # 保存为 CSV
    csv_path = "data/ssq_history.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "期号", "开奖日期", "红球1", "红球2", "红球3", "红球4", "红球5", "红球6",
            "蓝球", "销售金额", "奖池金额",
            "一等奖注数", "一等奖奖金",
            "二等奖注数", "二等奖奖金",
            "三等奖注数", "三等奖奖金",
            "四等奖注数", "四等奖奖金",
            "五等奖注数", "五等奖奖金",
            "六等奖注数", "六等奖奖金"
        ])
        for row in all_data:
            reds = row.get('frontWinningNum', '').split()
            blue = row.get('backWinningNum', '')
            wd = row.get('winnerDetails', [])

            def get_winner(etc):
                for w in wd:
                    if str(w.get('awardEtc')) == str(etc):
                        base = w.get('baseBetWinner', {})
                        if base:
                            return base.get('awardNum', ''), base.get('awardMoney', '')
                return '', ''

            j1n, j1m = get_winner(1)
            j2n, j2m = get_winner(2)
            j3n, j3m = get_winner(3)
            j4n, j4m = get_winner(4)
            j5n, j5m = get_winner(5)
            j6n, j6m = get_winner(6)

            writer.writerow([
                row.get('issue', ''),
                row.get('openTime', ''),
            ] + reds + [blue,
                row.get('saleMoney', ''),
                row.get('prizePoolMoney', ''),
                j1n, j1m, j2n, j2m, j3n, j3m, j4n, j4m, j5n, j5m, j6n, j6m
            ])
    print(f"CSV 已保存: {csv_path}")

    # 打印前3条和后3条验证
    print("\n=== 最早3期 ===")
    for r in all_data[:3]:
        print(f"  {r['issue']} | {r['openTime']} | 红:{r['frontWinningNum']} 蓝:{r['backWinningNum']}")
    print("\n=== 最近3期 ===")
    for r in all_data[-3:]:
        print(f"  {r['issue']} | {r['openTime']} | 红:{r['frontWinningNum']} 蓝:{r['backWinningNum']}")

if __name__ == "__main__":
    main()
