import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# 頁面配置
st.set_page_config(
    page_title="台股即時股價與互動圖表",
    page_icon="📈",
    layout="wide"
)

# 標題
st.title("📈 台股即時股價查詢與互動走勢圖")
st.caption("輸入台股代號，快速查詢最新股價、前一日漲跌幅及 1 日至 1 年的歷史走勢。")

# 側邊欄或頂部輸入框
col_input, _ = st.columns([1, 2])
with col_input:
    stock_id = st.text_input("請輸入台股代碼（例如：2330、2317、0050、6488）：", value="2330").strip()

# 抓取資料函式（快取 5 分鐘避免頻繁請求）
@st.cache_data(ttl=300)
def get_stock_data(symbol: str):
    """
    自動嘗試 上市 (.TW) 或 上櫃 (.TWO) 股票代號
    """
    for ext in [".TW", ".TWO"]:
        full_symbol = f"{symbol}{ext}"
        ticker = yf.Ticker(full_symbol)
        # 嘗試取得 1 年歷史資料驗證是否存在
        df = ticker.history(period="1y")
        if not df.empty:
            return ticker, full_symbol, df
    return None, None, None

if stock_id:
    ticker, full_symbol, df_1y = get_stock_data(stock_id)

    if df_1y is None or df_1y.empty:
        st.error(f"❌ 找不到股票代碼 「{stock_id}」，請確認輸入是否正確（上市如 2330，上櫃如 6488）。")
    else:
        # 取得最新一筆與前一筆數據計算漲跌幅
        latest_data = df_1y.iloc[-1]
        prev_data = df_1y.iloc[-2] if len(df_1y) > 1 else latest_data

        latest_price = latest_data['Close']
        prev_price = prev_data['Close']
        price_change = latest_price - prev_price
        pct_change = (price_change / prev_price) * 100

        # 計算當日最高/最低
        high_price = latest_data['High']
        low_price = latest_data['Low']
        volume = int(latest_data['Volume'])

        st.subheader(f"🔍 股票代碼：{full_symbol}")

        # 顯示重點指標卡片 (Metrics)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(
            label="最新價格",
            value=f"{latest_price:.2f} TWD",
            delta=f"{price_change:+.2f} ({pct_change:+.2f}%)",
            delta_color="normal" # Streamlit 預設綠升紅降，可自訂台股慣用樣式
        )
        m2.metric(label="前一日收盤價", value=f"{prev_price:.2f} TWD")
        m3.metric(label="當日最高 / 最低", value=f"{high_price:.2f} / {low_price:.2f}")
        m4.metric(label="當日成交量", value=f"{volume:,} 股")

        st.markdown("---")

        # 時間區間選擇器
        st.markdown("### 📊 歷史股價互動 K 線圖")
        time_ranges = {
            "1日 (盤中/高頻)": ("1d", "1m"),
            "5日": ("5d", "15m"),
            "1個月": ("1mo", "1d"),
            "3個月": ("3mo", "1d"),
            "6個月": ("6mo", "1d"),
            "1年": ("1y", "1d")
        }

        selected_range = st.radio(
            "選擇時間區間：",
            options=list(time_ranges.keys()),
            index=5, # 預設選 1 年
            horizontal=True
        )

        period, interval = time_ranges[selected_range]

        # 抓取所選區間資料
        df_chart = ticker.history(period=period, interval=interval)

        if not df_chart.empty:
            # 建立 Plotly K 線圖
            fig = go.Figure()

            # K線圖 (Candlestick)
            fig.add_trace(go.Candlestick(
                x=df_chart.index,
                open=df_chart['Open'],
                high=df_chart['High'],
                low=df_chart['Low'],
                close=df_chart['Close'],
                name="K線",
                increasing_line_color='red',   # 台股習慣：上漲為紅
                decreasing_line_color='green'  # 台股習慣：下跌為綠
            ))

            # 圖表版面配置
            fig.update_layout(
                title=f"{full_symbol} - {selected_range} 股價走勢圖",
                yaxis_title="股價 (TWD)",
                xaxis_title="時間",
                template="plotly_white",
                xaxis_rangeslider_visible=False, # 隱藏下方預設縮放條
                height=550,
                margin=dict(l=20, r=20, t=50, b=20)
            )

            # 於網頁顯示互動圖表
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("⚠️ 該時間區間暫無數據可供顯示。")
