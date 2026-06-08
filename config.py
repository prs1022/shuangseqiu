"""项目配置 — 从 .env 加载环境变量"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

# ── 邮件配置 ──
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.qq.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_AUTH_CODE = os.getenv("SENDER_AUTH_CODE", "")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL", "")

# ── 路径配置 ──
DATA_DIR = BASE_DIR / "data"
CSV_PATH = DATA_DIR / "ssq_history.csv"
JSON_PATH = DATA_DIR / "ssq_history.json"
STATE_PATH = BASE_DIR / "state.json"
LOG_DIR = BASE_DIR / "logs"
LOG_PATH = LOG_DIR / "ssq.log"

# ── API 配置 ──
API_URL = "https://jc.zhcw.com/port/client_json.php"
API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://www.zhcw.com/kjxx/ssq/",
}

# ── 调度配置 ──
# 开奖日: 周二(1)/周四(3)/周日(6)
DRAW_WEEKDAYS = [1, 3, 6]
# 开奖日高峰检查时段
DRAW_CHECK_START = 21  # 21:00
DRAW_CHECK_END = 23    # 23:00
# 检查间隔（秒）
DRAW_DAY_INTERVAL = 600     # 开奖日21-23点: 10分钟
NORMAL_INTERVAL = 1800      # 平时: 30分钟
