"""双色球预测自动化系统 — 主循环入口"""
import json
import time
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path

from config import (
    STATE_PATH, CSV_PATH, JSON_PATH,
    DRAW_WEEKDAYS, DRAW_CHECK_START, DRAW_CHECK_END,
    DRAW_DAY_INTERVAL, NORMAL_INTERVAL,
)
from logger import log
from data_manager import fetch_new_draws, append_to_csv, append_to_json, load_data, get_latest_issue
from analyzer import generate_predictions
from prize_checker import check_all_predictions, has_winning, get_winning_results
from email_sender import send_comparison_report

# ── 优雅退出 ──
_running = True


def _signal_handler(sig, frame):
    global _running
    log.info("收到退出信号，正在停止...")
    _running = False


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


# ── 状态管理 ──

def load_state() -> dict:
    """加载运行状态"""
    if STATE_PATH.exists():
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                state = json.load(f)
            log.info(f"状态已加载: 预测目标={state.get('predict_for_issue')}, "
                     f"最后检查={state.get('last_checked_issue')}, "
                     f"状态={state.get('status')}")
            return state
        except Exception as e:
            log.error(f"状态文件加载失败: {e}, 将重新初始化")
    return _init_state()


def save_state(state: dict) -> None:
    """保存运行状态"""
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        log.debug(f"状态已保存: 预测目标={state.get('predict_for_issue')}")
    except Exception as e:
        log.error(f"状态保存失败: {e}")


def _init_state() -> dict:
    """初始化状态（首次运行或状态丢失时）"""
    latest_issue = get_latest_issue()
    state = {
        "current_predictions": [],
        "predict_for_issue": _next_issue(latest_issue) if latest_issue else "",
        "last_checked_issue": latest_issue,
        "last_check_time": datetime.now().isoformat(),
        "status": "predicted",  # 需要先生成预测
    }
    log.info(f"状态已初始化: 最后期号={latest_issue}, 下一期={state['predict_for_issue']}")
    return state


def _next_issue(current_issue: str) -> str:
    """推算下一期期号

    期号格式: YYYYNNN, 其中 NNN 在每年内从001递增
    简单做法: NNN+1 (跨年时可能不准, 但对比时会以实际数据为准)
    """
    if not current_issue or len(current_issue) < 7:
        return ""
    year = current_issue[:4]
    num = int(current_issue[4:])
    return f"{year}{num + 1:03d}"


# ── 智能调度 ──

def _get_check_interval() -> int:
    """根据当前时间决定检查间隔（秒）"""
    now = datetime.now()
    weekday = now.weekday()  # 0=周一
    hour = now.hour

    # 开奖日 21:00-23:00 高频检查
    if weekday in DRAW_WEEKDAYS and DRAW_CHECK_START <= hour < DRAW_CHECK_END:
        log.debug(f"开奖日高峰时段, 间隔 {DRAW_DAY_INTERVAL}s")
        return DRAW_DAY_INTERVAL

    return NORMAL_INTERVAL


# ── 核心流程 ──

def ensure_predictions(state: dict) -> dict:
    """确保当前有预测号码，如无则生成"""
    if state["current_predictions"]:
        return state

    log.info("当前无预测号码，开始生成...")
    records = load_data()
    if not records:
        log.warning("无历史数据，无法生成预测")
        return state

    predictions = generate_predictions(records, count=10)
    if predictions:
        state["current_predictions"] = predictions
        state["predict_for_issue"] = _next_issue(get_latest_issue())
        state["status"] = "waiting_draw"
        save_state(state)
        log.info(f"已生成 {len(predictions)} 组预测, 目标期号: {state['predict_for_issue']}")
    else:
        log.error("预测生成失败")

    return state


def check_and_compare(state: dict) -> dict:
    """检查新开奖数据并对比预测结果"""
    # 1. 获取新数据
    new_draws = fetch_new_draws()
    if not new_draws:
        return state

    # 2. 增量追加数据
    append_to_csv(new_draws)
    append_to_json(new_draws)

    # 3. 遍历每期新开奖（按期号从早到晚）
    new_draws.sort(key=lambda x: x["issue"])

    for draw in new_draws:
        issue = draw["issue"]
        reds = [int(x) for x in draw.get("frontWinningNum", "").split()]
        blue = int(draw.get("backWinningNum", "0"))
        date = draw.get("openTime", "")

        log.info(f"═══ 第 {issue} 期开奖 ═══")
        log.info(f"开奖号码: {' '.join(f'{x:02d}' for x in reds)} + {blue:02d}")

        # 如果这期正好是预测目标期号，进行对比
        if issue == state.get("predict_for_issue"):
            result = {
                "reds": reds,
                "blue": blue,
            }

            predictions = state["current_predictions"]
            if predictions:
                # 4. 对比预测与开奖
                comparison = check_all_predictions(predictions, result)

                # 记录对比结果
                log.info(f"── 预测对比结果 ──")
                for c in comparison:
                    red_str = " ".join(f"{x:02d}" for x in c["reds"])
                    hit_str = " ".join(f"{x:02d}" for x in c["hit_reds"]) if c["hit_reds"] else "无"
                    log.info(
                        f"  第{c['index']}组: 预测红[{red_str}] 蓝[{c['blue']:02d}] | "
                        f"红球命中{c['red_hits']}个[{hit_str}] 蓝球{'✅' if c['blue_hit'] else '❌'} | "
                        f"{c['prize_name']}"
                    )

                if has_winning(comparison):
                    win_results = get_winning_results(comparison)
                    win_summary = "、".join(
                        f"第{r['index']}组({r['prize_name']})" for r in win_results
                    )
                    log.info(f"🎉 恭喜中奖！{win_summary}")
                else:
                    log.info("本期未中奖")

                # 5. 发送邮件报告
                draw_info = {
                    "issue": issue,
                    "date": date,
                    "reds": reds,
                    "blue": blue,
                }
                email_ok = send_comparison_report(comparison, draw_info)
                if not email_ok:
                    log.warning("邮件发送失败，下次将继续尝试（但不重复发送本期报告）")
            else:
                log.warning(f"期号 {issue} 开奖但无对应预测（可能状态丢失）")

            state["status"] = "compared"
        else:
            log.info(f"期号 {issue} 非预测目标期（预测期: {state.get('predict_for_issue')}），仅记录数据")

        state["last_checked_issue"] = issue
        state["last_check_time"] = datetime.now().isoformat()

    # 4. 如果有新的开奖已对比，生成下期预测
    if state.get("status") == "compared" or (new_draws and state.get("predict_for_issue", "") <= new_draws[-1]["issue"]):
        log.info("开始生成下期预测...")
        # 重新加载数据（已追加新开奖）
        records = load_data()
        predictions = generate_predictions(records, count=10)
        if predictions:
            latest = get_latest_issue()
            state["current_predictions"] = predictions
            state["predict_for_issue"] = _next_issue(latest)
            state["status"] = "waiting_draw"
            log.info(f"下期预测已生成, 目标期号: {state['predict_for_issue']}")
        else:
            log.error("下期预测生成失败")

    save_state(state)
    return state


# ── 主入口 ──

def main():
    log.info("=" * 50)
    log.info("双色球预测自动化系统启动")
    log.info("=" * 50)

    # 1. 加载状态
    state = load_state()

    # 2. 确保有预测
    state = ensure_predictions(state)

    # 3. 启动时做一次检查
    log.info("启动时执行首次检查...")
    state = check_and_compare(state)

    # 4. 主循环
    log.info("进入主循环，定时检查新开奖数据...")
    while _running:
        interval = _get_check_interval()
        log.info(f"下次检查: {interval // 60} 分钟后")

        # 分段 sleep，便于响应退出信号
        slept = 0
        while slept < interval and _running:
            chunk = min(60, interval - slept)
            time.sleep(chunk)
            slept += chunk

        if not _running:
            break

        try:
            state = check_and_compare(state)
        except Exception as e:
            log.error(f"检查过程异常: {e}", exc_info=True)

    log.info("双色球预测自动化系统已停止")
    save_state(state)


if __name__ == "__main__":
    main()
