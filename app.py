import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import csv
import os
from datetime import datetime

# 頁面配置
st.set_page_config(
    page_title="台股即時股價與技術指標",
    page_icon="📈",
    layout="wide"
)

# 標題
st.title("📈 台股即時股價查詢與技術指標 (RSI / 布林通道)")
st.caption("輸入台股代碼，快速查詢最新股價、前一日漲跌幅與 1 日至 1 年的 RSI 與布林通道走勢。")

# 後台日誌紀錄功能 (記錄查詢代碼與時間)
def write_usage_log(symbol: str):
    log_file = "usage_log.csv"
    if st.session_state.get("last_logged_symbol") != symbol:
        file_exists = os.path.exists(log_file)
        now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open(log_file, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["查詢時間", "股票代碼"])
            writer.writerow([now_time, symbol])
            
        st.session_state["last_logged_symbol"] = symbol

# 技術指標計算函式 (RSI & 布林通道)
def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    
    # 1. 布林通道 (20日均線, 2倍標準差)
    df['BB_Mid'] = df['Close'].rolling(window=20).mean()
    df['BB_Std'] = df['Close'].rolling(window=20).std()
    df['BB_Upper'] = df['BB_Mid'] + (df['BB_Std'] * 2)
    df['BB_Lower'] = df['BB_Mid'] - (df['BB_Std'] * 2)
    
    # 2. RSI 指標 (14日 Wilder Smoothing)
    delta = df['Close'].diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)
    avg_gain = gain.ewm(com=13, adjust=False).mean()
    avg_loss = loss.ewm(com=13, adjust=False).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    return df

# 1. 股票查詢區塊
col_input, _ = st.columns([1, 2])
with col_input:
    stock_id = st.text_input("請輸入台股代碼（例如：2330、2317、0050、6488）：", value="2330").strip()

@st.cache_data(ttl=300)
def get_stock_data(symbol: str):
    """
    自動嘗試 上市 (.TW) 或 上櫃 (.TWO) 股票代號
    """
    for ext in [".TW", ".TWO"]:
        full_symbol = f"{symbol}{ext}"
        ticker = yf.Ticker(full_symbol)
        df = ticker.history(period="1y")
        if not df.empty:
            df = calculate_indicators(df)
            return full_symbol, df
    return None, None

@st.cache_data(ttl=300)
def get_chart_data(full_symbol: str, period: str, interval: str):
    ticker = yf.Ticker(full_symbol)
    df = ticker.history(period=period, interval=interval)
    if not df.empty:
        df = calculate_indicators(df)
    return df

if stock_id:
    full_symbol, df_1y = get_stock_data(stock_id)

    if df_1y is None or df_1y.empty:
        st.error(f"❌ 找不到股票代碼 「{stock_id}」，請確認輸入是否正確（上市如 2330，上櫃如 6488）。")
    else:
        # 寫入後台日誌紀錄
        write_usage_log(full_symbol)

        # 最新數據與指標
        latest_data = df_1y.iloc[-1]
        prev_data = df_1y.iloc[-2] if len(df_1y) > 1 else latest_data

        latest_price = float(latest_data['Close'])
        prev_price = float(prev_data['Close'])
        price_change = latest_price - prev_price
        pct_change = (price_change / prev_price) * 100

        high_price = float(latest_data['High'])
        low_price = float(latest_data['Low'])
        volume = int(latest_data['Volume'])

        # 技術指標數值提取
        rsi_val = float(latest_data['RSI']) if pd.notna(latest_data['RSI']) else 0.0
        bb_upper = float(latest_data['BB_Upper']) if pd.notna(latest_data['BB_Upper']) else 0.0
        bb_mid = float(latest_data['BB_Mid']) if pd.notna(latest_data['BB_Mid']) else 0.0
        bb_lower = float(latest_data['BB_Lower']) if pd.notna(latest_data['BB_Lower']) else 0.0

        st.subheader(f"🔍 股票代碼：{full_symbol}")

        # 第一部分：即時行情指標卡片
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(
            label="最新價格",
            value=f"{latest_price:.2f} TWD",
            delta=f"{price_change:+.2f} ({pct_change:+.2f}%)",
            delta_color="normal"
        )
        m2.metric(label="前一日收盤價", value=f"{prev_price:.2f} TWD")
        m3.metric(label="當日最高 / 最低", value=f"{high_price:.2f} / {low_price:.2f}")
        m4.metric(label="當日成交量", value=f"{volume:,} 股")

        # 技術指標卡片 (RSI 與 布林通道)
        st.markdown("##### 📐 最新技術指標數值")
        t1, t2, t3, t4 = st.columns(4)
        
        rsi_status = " (超買區域 ⚠️)" if rsi_val >= 70 else (" (超賣區域 🟢)" if rsi_val <= 30 else " (常態區)")
        t1.metric(label="RSI (14日)", value=f"{rsi_val:.2f}", delta=rsi_status, delta_color="off")
        t2.metric(label="布林上軌 (Upper)", value=f"${bb_upper:.2f}")
        t3.metric(label="布林中軌 (20MA)", value=f"${bb_mid:.2f}")
        t4.metric(label="布林下軌 (Lower)", value=f"${bb_lower:.2f}")

        st.markdown("---")

        # 第二部分：歷史股價 K 線圖（含布林通道與 RSI 折線圖）
        st.markdown("### 📊 歷史股價 K 線圖（疊加布林通道與 RSI 指標）")
        time_ranges = {
            "1日 (盤中)": ("1d", "1m"),
            "5日": ("5d", "15m"),
            "1個月": ("1mo", "1d"),
            "3個月": ("3mo", "1d"),
            "6個月": ("6mo", "1d"),
            "1年": ("1y", "1d")
        }

        selected_range = st.radio(
            "選擇時間區間：",
            options=list(time_ranges.keys()),
            index=5,
            horizontal=True
        )

        period, interval = time_ranges[selected_range]
        df_chart = get_chart_data(full_symbol, period, interval)

        if not df_chart.empty:
            # 1. 主圖表：K 線圖 + 布林通道
            fig_main = go.Figure()
            
            # K線
            fig_main.add_trace(go.Candlestick(
                x=df_chart.index,
                open=df_chart['Open'],
                high=df_chart['High'],
                low=df_chart['Low'],
                close=df_chart['Close'],
                name="K線",
                increasing_line_color='red',   # 台股習慣：上漲為紅
                decreasing_line_color='green'  # 台股習慣：下跌為綠
            ))

            # 布林通道上/中/下軌
            if 'BB_Upper' in df_chart.columns:
                fig_main.add_trace(go.Scatter(
                    x=df_chart.index, y=df_chart['BB_Upper'],
                    mode='lines', name='布林上軌',
                    line=dict(color='rgba(245, 158, 11, 0.7)', width=1.5, dash='dot')
                ))
                fig_main.add_trace(go.Scatter(
                    x=df_chart.index, y=df_chart['BB_Mid'],
                    mode='lines', name='布林中軌 (20MA)',
                    line=dict(color='rgba(59, 130, 246, 0.8)', width=1.5)
                ))
                fig_main.add_trace(go.Scatter(
                    x=df_chart.index, y=df_chart['BB_Lower'],
                    mode='lines', name='布林下軌',
                    line=dict(color='rgba(245, 158, 11, 0.7)', width=1.5, dash='dot')
                ))

            fig_main.update_layout(
                title=f"{full_symbol} - {selected_range} 走勢圖 (含布林通道)",
                xaxis=dict(gridcolor='#334155', rangeslider=dict(visible=False), fixedrange=True),
                yaxis=dict(gridcolor='#334155', title='股價 (TWD)', fixedrange=True),
                template="plotly_white",
                height=450,
                margin=dict(l=20, r=20, t=50, b=20)
            )

            st.plotly_chart(fig_main, use_container_width=True, config={'displayModeBar': False})

            # 2. 子圖表：RSI (14) 指標走勢
            fig_rsi = go.Figure()
            if 'RSI' in df_chart.columns:
                fig_rsi.add_trace(go.Scatter(
                    x=df_chart.index, y=df_chart['RSI'],
                    mode='lines', name='RSI (14)',
                    line=dict(color='#a855f7', width=2)
                ))
                # 70/30 超買超賣警戒線
                fig_rsi.add_hline(y=70, line_dash="dash", line_color="#ef4444", annotation_text="超買 (70)")
                fig_rsi.add_hline(y=30, line_dash="dash", line_color="#10b981", annotation_text="超賣 (30)")

            fig_rsi.update_layout(
                title="RSI (14) 相對強弱走勢圖",
                xaxis=dict(gridcolor='#334155', fixedrange=True),
                yaxis=dict(gridcolor='#334155', title='RSI 數值', range=[0, 100], fixedrange=True),
                template="plotly_white",
                height=250,
                margin=dict(l=20, r=20, t=40, b=20)
            )

            st.plotly_chart(fig_rsi, use_container_width=True, config={'displayModeBar': False})
        else:
            st.warning("⚠️ 該時間區間暫無數據可供顯示。")
