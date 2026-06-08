"""邮件发送 — 每期开奖后发送对比报告"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

from config import SMTP_SERVER, SMTP_PORT, SENDER_EMAIL, SENDER_AUTH_CODE, RECEIVER_EMAIL
from logger import log
from prize_checker import has_winning, get_winning_results, PRIZE_NAMES


def _build_html(results: list[dict], draw_info: dict) -> str:
    """构建对比报告 HTML 邮件内容"""
    issue = draw_info["issue"]
    date = draw_info["date"]
    blue_str = f"{draw_info['blue']:02d}"

    # 预构建红球 HTML 片段（避免 f-string 内含反斜杠）
    red_balls_html = " ".join(
        '<span style="background:#e74c3c;color:#fff;padding:2px 8px;'
        f'border-radius:50%;margin:0 2px;">{x:02d}</span>'
        for x in draw_info["reds"]
    )
    blue_ball_html = (
        '<span style="background:#3498db;color:#fff;padding:2px 8px;'
        f'border-radius:50%;margin:0 2px;">{blue_str}</span>'
    )

    winning = has_winning(results)
    status_icon = "🎉" if winning else "📋"

    # 标题
    html = f"""
    <html><body style="font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; max-width: 700px; margin: 0 auto; padding: 20px;">
    <h2 style="color: #333;">{status_icon} 双色球第 {issue} 期对比报告</h2>
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

    # 详细对比表
    html += """
    <h3 style="color: #333;">📊 预测对比详情</h3>
    <table style="width:100%; border-collapse:collapse; margin:10px 0;">
        <tr style="background:#2c3e50; color:#fff;">
            <th style="padding:8px; text-align:center;">组号</th>
            <th style="padding:8px; text-align:center;">预测红球</th>
            <th style="padding:8px; text-align:center;">预测蓝球</th>
            <th style="padding:8px; text-align:center;">红球命中</th>
            <th style="padding:8px; text-align:center;">蓝球</th>
            <th style="padding:8px; text-align:center;">结果</th>
        </tr>
    """

    for r in results:
        pred_reds = " ".join(f"{x:02d}" for x in r["reds"])
        hit_reds = " ".join(f"{x:02d}" for x in r["hit_reds"]) if r["hit_reds"] else "-"
        blue_emoji = "✅" if r["blue_hit"] else "❌"
        prize = r["prize_name"]

        # 中奖行高亮
        row_bg = "#fff9e6" if r["prize_level"] else "#fff"
        prize_style = f'color:#e74c3c;font-weight:bold;' if r["prize_level"] else 'color:#999;'

        html += f"""
        <tr style="background:{row_bg};">
            <td style="padding:6px; text-align:center;">{r['index']}</td>
            <td style="padding:6px; text-align:center; color:#e74c3c;">{pred_reds}</td>
            <td style="padding:6px; text-align:center; color:#3498db;">{r['blue']:02d}</td>
            <td style="padding:6px; text-align:center;">{r['red_hits']}个 {hit_reds}</td>
            <td style="padding:6px; text-align:center;">{blue_emoji}</td>
            <td style="padding:6px; text-align:center; {prize_style}">{prize}</td>
        </tr>
        """

    html += "</table>"

    # 策略摘要
    total_preds = len(results)
    avg_red_hits = sum(r["red_hits"] for r in results) / total_preds if total_preds else 0
    blue_hits = sum(1 for r in results if r["blue_hit"])

    html += f"""
    <div style="background:#f8f9fa; padding:15px; border-radius:8px; margin:15px 0; font-size:14px; color:#666;">
        <p style="margin:3px 0;">📈 统计: 平均红球命中 {avg_red_hits:.1f} 个 | 蓝球命中 {blue_hits}/{total_preds} 组 |
        中奖组数 {len(get_winning_results(results))}/{total_preds}</p>
    </div>
    <hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
    <p style="font-size:12px; color:#999;">⚠️ 本邮件由双色球预测系统自动发送，仅供参考，不构成投注建议。</p>
    <p style="font-size:12px; color:#999;">发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </body></html>
    """

    return html


def send_comparison_report(results: list[dict], draw_info: dict) -> bool:
    """
    发送每期对比报告邮件

    参数:
        results: check_all_predictions 的返回值
        draw_info: {"issue": str, "date": str, "reds": [int], "blue": int}

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

    html_content = _build_html(results, draw_info)

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
