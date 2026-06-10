"""邮件发送 — 每期开奖后发送对比报告（含下期预测）"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

from config import SMTP_SERVER, SMTP_PORT, SENDER_EMAIL, SENDER_AUTH_CODE, RECEIVER_EMAIL
from logger import log
from prize_checker import has_winning, get_winning_results, PRIZE_NAMES


def _ball_html(num: int, color: str, hit: bool = False) -> str:
    """生成单个球的 HTML（命中用绿色背景，未命中用原色）"""
    bg = "#27ae60" if hit else color  # 绿色=命中, 原色=未命中
    return (
        f'<span style="background:{bg};color:#fff;padding:2px 8px;'
        f'border-radius:50%;margin:0 2px;font-size:13px;">{num:02d}</span>'
    )


def _build_html(results: list[dict], draw_info: dict,
                next_predictions: list[dict] = None,
                next_issue: str = "",
                balance: float = None,
                cost: int = None,
                winnings: int = None,
                initial_balance: float = 10000) -> str:
    """构建对比报告 HTML 邮件内容"""
    issue = draw_info["issue"]
    date = draw_info["date"]
    blue_str = f"{draw_info['blue']:02d}"

    # 开奖号码
    red_balls_html = " ".join(
        f'<span style="background:#e74c3c;color:#fff;padding:2px 8px;'
        f'border-radius:50%;margin:0 2px;font-size:14px;">{x:02d}</span>'
        for x in draw_info["reds"]
    )
    blue_ball_html = (
        f'<span style="background:#3498db;color:#fff;padding:2px 8px;'
        f'border-radius:50%;margin:0 2px;font-size:14px;">{blue_str}</span>'
    )

    winning = has_winning(results)
    status_icon = "🎉" if winning else "📋"

    # 标题
    html = f"""
    <html><body style="font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
    <h2 style="color: #333;">{status_icon} 双色球第 {issue} 期对比报告</h2>
    """

    # ── 余额区段（邮件顶部） ──
    if balance is not None:
        # 计算盈亏
        profit = balance - initial_balance  # 与初始额度对比
        if profit >= 0:
            profit_str = f"+{profit:,.0f}"
            profit_color = "#27ae60"
        else:
            profit_str = f"{profit:,.0f}"
            profit_color = "#e74c3c"

        # 本期盈亏
        if cost is not None and winnings is not None:
            draw_profit = winnings - cost
            if draw_profit >= 0:
                draw_profit_str = f"+{draw_profit:,}"
            else:
                draw_profit_str = f"{draw_profit:,}"
        else:
            draw_profit_str = ""

        html += f"""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 10px; margin: 15px 0; color: #fff;">
            <p style="margin:0 0 5px 0; font-size:14px; opacity:0.9;">💰 虚拟余额</p>
            <p style="margin:0; font-size:32px; font-weight:bold;">¥{balance:,.0f}</p>
            <p style="margin:5px 0 0 0; font-size:13px; opacity:0.85;">
                累计盈亏: <span style="color:{profit_color}; font-weight:bold;">{profit_str}元</span>
                {"| 本期: " + draw_profit_str + "元" if draw_profit_str else ""}
            </p>
        </div>
        """

    # 开奖号码
    html += f"""
    <div style="background: #f0f7ff; padding: 15px; border-radius: 8px; margin: 15px 0;">
        <p style="margin:5px 0; font-size:16px;"><strong>开奖日期:</strong> {date}</p>
        <p style="margin:5px 0; font-size:20px;">
            <strong>开奖号码:</strong>
            <span style="color:#e74c3c; font-weight:bold;">{red_balls_html}</span>
            <span style="color:#3498db; font-weight:bold;">{blue_ball_html}</span>
        </p>
    </div>
    """

    if winning:
        win_results = get_winning_results(results)
        win_summary = "、".join(
            f"第{r['index']}组({r['prize_name']})" for r in win_results
        )
        html += f"""
        <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #ffc107;">
            <p style="margin:0; color: #856404; font-size: 16px; font-weight: bold;">🎉 恭喜中奖！{win_summary}</p>
        </div>
        """

    # 详细对比表 — 6列: 组号 | 策略 | 预测红球(命中高亮) | 蓝球(命中高亮) | 预测原因 | 结果
    html += """
    <h3 style="color: #333;">📊 预测对比详情</h3>
    <table style="width:100%; border-collapse:collapse; margin:10px 0; font-size:13px;">
        <tr style="background:#2c3e50; color:#fff;">
            <th style="padding:8px; text-align:center; width:40px;">组号</th>
            <th style="padding:8px; text-align:center; width:90px;">策略</th>
            <th style="padding:8px; text-align:center;">预测红球</th>
            <th style="padding:8px; text-align:center; width:55px;">蓝球</th>
            <th style="padding:8px; text-align:center; max-width:250px;">预测原因</th>
            <th style="padding:8px; text-align:center; width:60px;">结果</th>
        </tr>
    """

    for r in results:
        # 红球：命中=绿色，未命中=红色
        pred_reds_html = " ".join(
            _ball_html(x, "#e74c3c", hit=(x in r["hit_reds"]))
            for x in r["reds"]
        )

        # 蓝球：命中=绿色，未命中=蓝色
        pred_blue_html = _ball_html(r["blue"], "#3498db", hit=r["blue_hit"])

        # 中奖行高亮
        row_bg = "#fff9e6" if r["prize_level"] else "#fff"
        prize_style = 'color:#e74c3c;font-weight:bold;' if r["prize_level"] else 'color:#999;'

        # 原因（换行显示）
        reason = r.get("reason", "")
        reason_style = "word-break:break-all; font-size:12px; color:#555; line-height:1.4;"

        # 策略名
        strategy = r.get("strategy_name", "")
        strategy_style = "font-size:12px; color:#2c3e50;"

        html += f"""
        <tr style="background:{row_bg};">
            <td style="padding:6px; text-align:center;">{r['index']}</td>
            <td style="padding:6px; text-align:center; {strategy_style}">{strategy}</td>
            <td style="padding:6px; text-align:center;">{pred_reds_html}</td>
            <td style="padding:6px; text-align:center;">{pred_blue_html}</td>
            <td style="padding:6px; text-align:left; {reason_style}">{reason}</td>
            <td style="padding:6px; text-align:center; {prize_style}">{r['prize_name']}</td>
        </tr>
        """

    html += "</table>"

    # 统计
    total_preds = len(results)
    avg_red_hits = sum(r["red_hits"] for r in results) / total_preds if total_preds else 0
    blue_hits = sum(1 for r in results if r["blue_hit"])

    html += f"""
    <div style="background:#f8f9fa; padding:15px; border-radius:8px; margin:15px 0; font-size:14px; color:#666;">
        <p style="margin:3px 0;">📈 统计: 平均红球命中 {avg_red_hits:.1f} 个 | 蓝球命中 {blue_hits}/{total_preds} 组 |
        中奖组数 {len(get_winning_results(results))}/{total_preds}</p>
    </div>
    """

    # ── 下期预测区段 ──
    if next_predictions:
        html += f"""
        <hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
        <h3 style="color: #333;">🔮 下期预测号码（第 {next_issue} 期）</h3>
        <table style="width:100%; border-collapse:collapse; margin:10px 0; font-size:13px;">
            <tr style="background:#2c3e50; color:#fff;">
                <th style="padding:8px; text-align:center; width:40px;">组号</th>
                <th style="padding:8px; text-align:center; width:90px;">策略</th>
                <th style="padding:8px; text-align:center;">预测红球</th>
                <th style="padding:8px; text-align:center; width:55px;">蓝球</th>
                <th style="padding:8px; text-align:center; max-width:250px;">预测原因</th>
            </tr>
        """

        for i, p in enumerate(next_predictions, 1):
            reds_html = " ".join(
                f'<span style="background:#e74c3c;color:#fff;padding:2px 8px;'
                f'border-radius:50%;margin:0 2px;font-size:13px;">{x:02d}</span>'
                for x in p["reds"]
            )
            blue_html = (
                f'<span style="background:#3498db;color:#fff;padding:2px 8px;'
                f'border-radius:50%;margin:0 2px;font-size:13px;">{p["blue"]:02d}</span>'
            )
            reason = p.get("reason", "")
            strategy = p.get("strategy_name", "")

            html += f"""
            <tr style="background:#fff;">
                <td style="padding:6px; text-align:center;">{i}</td>
                <td style="padding:6px; text-align:center; font-size:12px; color:#2c3e50;">{strategy}</td>
                <td style="padding:6px; text-align:center;">{reds_html}</td>
                <td style="padding:6px; text-align:center;">{blue_html}</td>
                <td style="padding:6px; text-align:left; word-break:break-all; font-size:12px; color:#555; line-height:1.4;">{reason}</td>
            </tr>
            """

        html += "</table>"

    html += f"""
    <hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
    <p style="font-size:12px; color:#999;">⚠️ 本邮件由双色球预测系统自动发送，仅供参考，不构成投注建议。</p>
    <p style="font-size:12px; color:#999;">发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </body></html>
    """

    return html


def send_comparison_report(results: list[dict], draw_info: dict,
                           next_predictions: list[dict] = None,
                           next_issue: str = "",
                           balance: float = None,
                           cost: int = None,
                           winnings: int = None,
                           initial_balance: float = 10000) -> bool:
    """
    发送每期对比报告邮件

    参数:
        results: check_all_predictions 的返回值
        draw_info: {"issue": str, "date": str, "reds": [int], "blue": int}
        next_predictions: 下期预测号码列表（含 reason/strategy_name）
        next_issue: 下期期号
        balance: 当前虚拟余额
        cost: 本期购注花费
        winnings: 本期中奖金额
        initial_balance: 初始虚拟额度（用于计算累计盈亏）

    返回:
        True=发送成功, False=发送失败
    """
    winning = has_winning(results)
    issue = draw_info["issue"]

    subject = f"{'🎉中奖!' if winning else '📋'}双色球第{issue}期对比报告"
    if winning:
        win_results = get_winning_results(results)
        prize_names = "、".join(r["prize_name"] for r in win_results)
        subject += f" — {prize_names}"

    html_content = _build_html(results, draw_info,
                               next_predictions=next_predictions,
                               next_issue=next_issue,
                               balance=balance,
                               cost=cost,
                               winnings=winnings,
                               initial_balance=initial_balance)

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SENDER_EMAIL
        msg["To"] = RECEIVER_EMAIL
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, SENDER_AUTH_CODE)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())

        log.info(f"邮件已发送: {subject}")
        return True

    except Exception as e:
        log.error(f"邮件发送失败: {e}")
        return False
