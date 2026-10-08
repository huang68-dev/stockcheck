import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import csv
import os
from datetime import datetime

# 頁面配置
st.set_page_config(
    page_title="台股即時股價、持股統計與股息推估",
    page_icon="📈",
    layout="wide"
)

# 標題
st.title("📈 台股即時股價查詢與 1-10 年股息推估")
st.caption("輸入台股代碼檢索最新行情，輸入持股成本即可統計目前淨值與損益，並試算未來 1 至 10 年的含息成本與總資產變化。")

# 後台日誌紀錄功能
def write_usage_log(symbol: str, shares_cnt: int, cost_val: float):
    log_file = "usage_log.csv"
    current_entry = (symbol, shares_cnt, cost_val)
    
    # 利用 session_state 防止 Streamlit 重複執行時產生洗版紀錄
    if st.session_state.get("last_logged_entry") != current_entry:
        file_exists = os.path.exists(log_file)
        now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open(log_file, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            # 若檔案不存在則寫入欄位標頭
            if not file_exists:
                writer.writerow(["查詢時間", "股票代碼", "持有股數", "平均成本(TWD)"])
            writer.writerow([now_time, symbol, shares_cnt, cost_val])
            
        st.session_state["last_logged_entry"] = current_entry

# 1. 股票查詢區塊
col_input, _ = st.columns([1, 2])
with col_input:
    stock_id = st.text_input("請輸入台股代碼（例如：2330、2317、0050、00878、00919）：", value="2330").strip()

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
            return full_symbol, df
    return None, None

@st.cache_data(ttl=300)
def get_chart_data(full_symbol: str, period: str, interval: str):
    ticker = yf.Ticker(full_symbol)
    return ticker.history(period=period, interval=interval)

@st.cache_data(ttl=300)
def get_past_year_dividend(full_symbol: str):
    """
    抓取近 1 年 (365天) 歷史累計配息金額
    """
    try:
        ticker = yf.Ticker(full_symbol)
        divs = ticker.dividends
        if divs is not None and not divs.empty:
            now = pd.Timestamp.now()
            if divs.index.tz is not None:
                divs.index = divs.index.tz_localize(None)
            one_year_ago = now - pd.DateOffset(years=1)
            past_year_divs = divs[divs.index >= one_year_ago]
            return float(past_year_divs.sum())
    except Exception:
        pass
    return 0.0

if stock_id:
    full_symbol, df_1y = get_stock_data(stock_id)

    if df_1y is None or df_1y.empty:
        st.error(f"❌ 找不到股票代碼 「{stock_id}」，請確認輸入是否正確（上市如 2330，上櫃如 6488）。")
    else:
        # 最新數據
        latest_data = df_1y.iloc[-1]
        prev_data = df_1y.iloc[-2] if len(df_1y) > 1 else latest_data

        latest_price = float(latest_data['Close'])
        prev_price = float(prev_data['Close'])
        price_change = latest_price - prev_price
        pct_change = (price_change / prev_price) * 100

        high_price = float(latest_data['High'])
        low_price = float(latest_data['Low'])
        volume = int(latest_data['Volume'])

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

        st.markdown("---")

        # 第二部分：持股成本與目前淨值統計
        st.markdown("### 💰 個人持股成本與目前淨值統計")
        
        c1, c2 = st.columns(2)
        with c1:
            shares = st.number_input("請輸入持有股數 (股)：", min_value=1, value=1000, step=1000)
        with c2:
            avg_cost = st.number_input("請輸入平均買入成本 (每股 TWD)：", min_value=0.01, value=round(latest_price, 2), step=1.0)

        # 執行後台寫入紀錄
        write_usage_log(full_symbol, shares, avg_cost)

        # 統計計算
        total_cost = shares * avg_cost
        total_market_val = shares * latest_price
        unrealized_profit = total_market_val - total_cost
        roi = (unrealized_profit / total_cost) * 100 if total_cost > 0 else 0.0

        p1, p2, p3, p4 = st.columns(4)
        p1.metric(label="總投入成本", value=f"${total_cost:,.0f} TWD")
        p2.metric(label="目前總市值 (淨值)", value=f"${total_market_val:,.0f} TWD")
        
        profit_color = "🔴" if unrealized_profit > 0 else ("🟢" if unrealized_profit < 0 else "⚪")
        p3.metric(
            label="未實現損益",
            value=f"${unrealized_profit:,.0f} TWD",
            delta=f"{profit_color} {roi:+.2f}%",
            delta_color="off"
        )
        p4.metric(label="每股損益", value=f"${latest_price - avg_cost:+.2f} TWD")

        st.markdown("---")

        # 第三部分：1-10 年股息與淨值推估
        st.markdown("### 📅 1 - 10 年未來股息與淨值推估 (含息成本)")
        
        auto_dividend = get_past_year_dividend(full_symbol)
        
        div_col1, div_col2 = st.columns([1, 1])
        with div_col1:
            annual_div_per_share = st.number_input(
                "預估每股年配息金額 (TWD，預設自動抓取近1年累計配息)：",
                min_value=0.0,
                value=round(auto_dividend, 2) if auto_dividend > 0 else 0.0,
                step=0.1
            )
        with div_col2:
            est_yield = (annual_div_per_share / latest_price * 100) if latest_price > 0 else 0.0
            st.metric(label="預估年化現金殖利率", value=f"{est_yield:.2f} %")
            st.caption(f"每年預估可領取現金股利總額： **${shares * annual_div_per_share:,.0f} TWD**")

        reinvest_option = st.checkbox("開啟「股息再投資 (DRIP)」推估模式（每年領到的股息以目前股價買回新股）", value=False)

        years = list(range(1, 11))
        est_data = []

        if not reinvest_option:
            cum_div = 0.0
            for yr in years:
                annual_div_total = shares * annual_div_per_share
                cum_div += annual_div_total
                effective_cost_per_share = max(0.0, avg_cost - (annual_div_per_share * yr))
                total_asset_val = total_market_val + cum_div
                total_return_pct = ((total_asset_val - total_cost) / total_cost) * 100 if total_cost > 0 else 0.0
                
                est_data.append({
                    "年份": f"第 {yr} 年",
                    "持股數量": f"{shares:,} 股",
                    "當年預估股息": f"${annual_div_total:,.0f}",
                    "累積領取股息": f"${cum_div:,.0f}",
                    "每股含息成本": f"${effective_cost_per_share:.2f}",
                    "預估總資產淨值(股票+現金)": f"${total_asset_val:,.0f}",
                    "預估總報酬率": f"{total_return_pct:+.2f}%",
                    "_raw_effective_cost": effective_cost_per_share,
                    "_raw_total_val": total_asset_val
                })
        else:
            current_shares = float(shares)
            cum_div_earned = 0.0
            for yr in years:
                annual_div_total = current_shares * annual_div_per_share
                cum_div_earned += annual_div_total
                
                new_shares = annual_div_total / latest_price if latest_price > 0 else 0
                current_shares += new_shares
                
                total_asset_val = current_shares * latest_price
                effective_cost_per_share = (total_cost - cum_div_earned) / current_shares if current_shares > 0 else 0
                effective_cost_per_share = max(0.0, effective_cost_per_share)
                total_return_pct = ((total_asset_val - total_cost) / total_cost) * 100 if total_cost > 0 else 0.0

                est_data.append({
                    "年份": f"第 {yr} 年",
                    "持股數量": f"{int(current_shares):,} 股",
                    "當年預估股息": f"${annual_div_total:,.0f}",
                    "累積領取股息": f"${cum_div_earned:,.0f}",
                    "每股含息成本": f"${effective_cost_per_share:.2f}",
                    "預估總資產淨值(股票+現金)": f"${total_asset_val:,.0f}",
                    "預估總報酬率": f"{total_return_pct:+.2f}%",
                    "_raw_effective_cost": effective_cost_per_share,
                    "_raw_total_val": total_asset_val
                })

        df_est = pd.DataFrame(est_data)
        display_cols = ["年份", "持股數量", "當年預估股息", "累積領取股息", "每股含息成本", "預估總資產淨值(股票+現金)", "預估總報酬率"]
        st.dataframe(df_est[display_cols], use_container_width=True, hide_index=True)

        # 1-10 年推估折線圖（固定軸線，防止拖拉放大）
        fig_est = go.Figure()
        fig_est.add_trace(go.Scatter(
            x=[f"第 {y} 年" for y in years],
            y=[d["_raw_total_val"] for d in est_data],
            mode='lines+markers',
            name='預估總資產淨值 (TWD)',
            line=dict(color='#3b82f6', width=3)
        ))
        fig_est.add_trace(go.Scatter(
            x=[f"第 {y} 年" for y in years],
            y=[d["_raw_effective_cost"] for d in est_data],
            mode='lines+markers',
            name='每股含息持有成本 (TWD)',
            line=dict(color='#ef4444', width=3, dash='dash'),
            yaxis='y2'
        ))

        # fixedrange=True 鎖定縮放
        fig_est.update_layout(
            title="1 - 10 年資產總淨值成長與每股含息成本調降趨勢",
            xaxis=dict(title="年份", fixedrange=True),
            yaxis=dict(title="總資產淨值 (TWD)", gridcolor='#334155', fixedrange=True),
            yaxis2=dict(title="每股含息成本 (TWD)", overlaying='y', side='right', gridcolor='#334155', fixedrange=True),
            template="plotly_white",
            height=450,
            margin=dict(l=20, r=20, t=50, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_est, use_container_width=True, config={'displayModeBar': False})

        st.markdown("---")

        # 第四部分：歷史股價 K 線圖（固定軸線，防止拖拉放大）
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
            index=5,
            horizontal=True
        )

        period, interval = time_ranges[selected_range]
        df_chart = get_chart_data(full_symbol, period, interval)

        if not df_chart.empty:
            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=df_chart.index,
                open=df_chart['Open'],
                high=df_chart['High'],
                low=df_chart['Low'],
                close=df_chart['Close'],
                name="K線",
                increasing_line_color='red',
                decreasing_line_color='green'
            ))

            # fixedrange=True 鎖定縮放，關閉工具列
            fig.update_layout(
                title=f"{full_symbol} - {selected_range} 股價走勢圖",
                xaxis=dict(gridcolor='#334155', rangeslider=dict(visible=False), fixedrange=True),
                yaxis=dict(gridcolor='#334155', title='股價 (TWD)', fixedrange=True),
                template="plotly_white",
                height=550,
                margin=dict(l=20, r=20, t=50, b=20)
            )

            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        else:
            st.warning("⚠️ 該時間區間暫無數據可供顯示。")
