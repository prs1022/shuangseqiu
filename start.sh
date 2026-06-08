#!/bin/bash
# 双色球预测系统 — 后台启动/停止/状态脚本

cd "$(dirname "$0")"

PID_FILE="./ssq.pid"
LOG_FILE="./logs/ssq.log"

_usage() {
    echo "用法: $0 {start|stop|restart|status}"
    exit 1
}

_start() {
    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE")
        if kill -0 "$OLD_PID" 2>/dev/null; then
            echo "⚠️  程序已在运行中 (PID: $OLD_PID)"
            exit 1
        else
            rm -f "$PID_FILE"
        fi
    fi

    echo "🚀 启动双色球预测系统..."
    nohup python main.py >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    sleep 1

    if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "✅ 启动成功 (PID: $(cat "$PID_FILE"))"
        echo "📋 日志: tail -f $LOG_FILE"
    else
        echo "❌ 启动失败，请检查日志: $LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi
}

_stop() {
    if [ ! -f "$PID_FILE" ]; then
        echo "⚠️  程序未在运行"
        exit 0
    fi

    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "🛑 停止程序 (PID: $PID)..."
        kill "$PID"
        # 等待进程退出（最多10秒）
        for i in $(seq 1 10); do
            if ! kill -0 "$PID" 2>/dev/null; then
                break
            fi
            sleep 1
        done
        # 仍未退出则强制终止
        if kill -0 "$PID" 2>/dev/null; then
            echo "⚡ 强制终止..."
            kill -9 "$PID"
        fi
        rm -f "$PID_FILE"
        echo "✅ 已停止"
    else
        echo "⚠️  进程已不存在，清理 PID 文件"
        rm -f "$PID_FILE"
    fi
}

_status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "✅ 运行中 (PID: $PID)"
        else
            echo "❌ 已停止 (PID 文件残留，进程不存在)"
        fi
    else
        echo "❌ 未运行"
    fi
}

case "${1:-}" in
    start)   _start   ;;
    stop)    _stop    ;;
    restart) _stop; _start ;;
    status)  _status  ;;
    *)       _usage   ;;
esac
