import streamlit as st
import yfinance as yf
import pandas as pd
import os
import datetime

st.set_page_config(layout="wide")
st.title("?? Interactive Portfolio Tracker")

DATA_FILE = "portfolio_data.csv"

# --- DATA STORAGE SETUP ---
def load_data():
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        if 'Purchase Price ($)' in df.columns:
            df.rename(columns={'Purchase Price ($)': 'Purchase Price'}, inplace=True)
        if 'Purchase Date' not in df.columns:
            df['Purchase Date'] = datetime.date.today().strftime('%Y-%m-%d')
        if 'Transaction Fee' not in df.columns:
            df['Transaction Fee'] = 0.0
        if 'Type' not in df.columns:
            df['Type'] = 'Buy'
        return df
    else:
        return pd.DataFrame(columns=['Ticker', 'Type', 'Shares', 'Purchase Price', 'Transaction Fee', 'Purchase Date'])

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

if 'portfolio' not in st.session_state:
    st.session_state.portfolio = load_data()

# --- SIDEBAR: Settings & Inputs ---
st.sidebar.header("?? Settings")
base_currency = st.sidebar.selectbox("Display Portfolio In:", ["USD", "GBP", "EUR", "JPY", "CHF", "CNY", "SGD", "HKD", "INR"])

currency_symbols = {"USD": "$", "GBP": "£", "EUR": "€", "JPY": "¥", "CHF": "CHF ", "CNY": "CN¥", "SGD": "S$", "HKD": "HK$", "INR": "?"}
sym = currency_symbols.get(base_currency, f"{base_currency} ")

st.sidebar.markdown("---")
st.sidebar.header("1. Add a Transaction")
st.sidebar.caption("For global stocks, use the Yahoo Finance suffix.")

type_input = st.sidebar.selectbox("Transaction Type", ["Buy", "Sell"])
ticker_input = st.sidebar.text_input("Ticker Symbol (e.g., AAPL, 6758.T)").upper()
shares_input = st.sidebar.number_input("Number of Shares", min_value=0.01, step=0.1)

price_label = "Purchase Price" if type_input == "Buy" else "Sale Price"
purchase_price_input = st.sidebar.number_input(f"{price_label} (in {base_currency})", min_value=0.01, step=1.0)

fee_input = st.sidebar.number_input(f"Transaction Fee (in {base_currency})", min_value=0.0, step=1.0)
purchase_date_input = st.sidebar.date_input("Transaction Date", max_value=datetime.date.today())

if st.sidebar.button("Add Transaction"):
    if ticker_input:
        new_asset = pd.DataFrame([{
            'Ticker': ticker_input, 
            'Type': type_input,
            'Shares': shares_input, 
            'Purchase Price': purchase_price_input, 
            'Transaction Fee': fee_input,
            'Purchase Date': purchase_date_input.strftime('%Y-%m-%d')
        }])
        st.session_state.portfolio = pd.concat([st.session_state.portfolio, new_asset], ignore_index=True)
        save_data(st.session_state.portfolio)
        st.sidebar.success(f"Added {type_input} for {ticker_input}!")

st.sidebar.markdown("---")
st.sidebar.header("2. Bulk Upload CSV")
uploaded_file = st.sidebar.file_uploader("Upload your portfolio", type=["csv"])

if uploaded_file is not None:
    try:
        uploaded_df = pd.read_csv(uploaded_file)
        if 'Purchase Price ($)' in uploaded_df.columns:
            uploaded_df.rename(columns={'Purchase Price ($)': 'Purchase Price'}, inplace=True)
        if 'Purchase Date' not in uploaded_df.columns:
            uploaded_df['Purchase Date'] = datetime.date.today().strftime('%Y-%m-%d')
        if 'Transaction Fee' not in uploaded_df.columns:
            uploaded_df['Transaction Fee'] = 0.0
        if 'Type' not in uploaded_df.columns:
            uploaded_df['Type'] = 'Buy'
            
        required_cols = ['Ticker', 'Type', 'Shares', 'Purchase Price', 'Transaction Fee', 'Purchase Date']
        if all(col in uploaded_df.columns for col in required_cols):
            if st.sidebar.button("Merge Uploaded Data"):
                uploaded_df['Ticker'] = uploaded_df['Ticker'].astype(str).str.upper()
                st.session_state.portfolio = pd.concat([st.session_state.portfolio, uploaded_df[required_cols]], ignore_index=True)
                save_data(st.session_state.portfolio)
                st.sidebar.success("Merged successfully!")
                st.rerun()
        else:
            st.sidebar.error("CSV must contain: Ticker, Type, Shares, Purchase Price, Transaction Fee, Purchase Date")
    except Exception as e:
        st.sidebar.error(f"Error: {e}")

# --- MAIN PAGE ---
st.header("Your Transaction Ledger")
st.caption(f"? Tip: All live prices and dividends are automatically converted into **{base_currency}**.")

if not st.session_state.portfolio.empty:
    portfolio_data = st.session_state.portfolio.copy()
    
    current_prices = []
    collected_dividends = []
    exchange_rates = {base_currency: 1.0}
    
    for index, row in portfolio_data.iterrows():
        ticker = row['Ticker']
        p_date = pd.to_datetime(row['Purchase Date'])
        
        multiplier = 1 if row['Type'] == 'Buy' else -1
        effective_shares = row['Shares'] * multiplier
        
        try:
            stock = yf.Ticker(ticker)
            price_local = stock.history(period="1d")['Close'].iloc[-1]
            stock_currency = stock.info.get('currency', 'USD')
            
            if stock_currency != base_currency:
                fx_ticker = f"{stock_currency}{base_currency}=X"
                if stock_currency not in exchange_rates:
                    try:
                        fx_rate = yf.Ticker(fx_ticker).history(period="1d")['Close'].iloc[-1]
                        exchange_rates[stock_currency] = fx_rate
                    except Exception:
                        try:
                            to_usd = yf.Ticker(f"{stock_currency}USD=X").history(period="1d")['Close'].iloc[-1]
                            usd_to_base = yf.Ticker(f"USD{base_currency}=X").history(period="1d")['Close'].iloc[-1]
                            exchange_rates[stock_currency] = to_usd * usd_to_base
                        except:
                            exchange_rates[stock_currency] = 1.0 
                            
                price_converted = price_local * exchange_rates[stock_currency]
            else:
                price_converted = price_local
                
            current_prices.append(price_converted)
            
            try:
                divs = stock.dividends
                if not divs.empty:
                    divs.index = divs.index.tz_localize(None)
                    recent_divs = divs[divs.index >= p_date]
                    
                    div_per_share_local = recent_divs.sum()
                    total_div_local = div_per_share_local * effective_shares
                    total_div_converted = total_div_local * exchange_rates[stock_currency]
                else:
                    total_div_converted = 0.0
            except Exception:
                total_div_converted = 0.0
                
            collected_dividends.append(total_div_converted)
            
        except Exception:
            current_prices.append(0.0)
            collected_dividends.append(0.0)
            
    portfolio_data['Effective Shares'] = portfolio_data.apply(lambda r: r['Shares'] if r['Type'] == 'Buy' else -r['Shares'], axis=1)
    portfolio_data[f'Live Price ({base_currency})'] = current_prices
    portfolio_data[f'Dividends ({base_currency})'] = collected_dividends
    
    portfolio_data[f'Total Cost ({base_currency})'] = (portfolio_data['Effective Shares'] * portfolio_data['Purchase Price']) + portfolio_data['Transaction Fee']
    portfolio_data[f'Current Value ({base_currency})'] = portfolio_data['Effective Shares'] * portfolio_data[f'Live Price ({base_currency})']
    
    portfolio_data[f'Capital P&L ({base_currency})'] = portfolio_data[f'Current Value ({base_currency})'] - portfolio_data[f'Total Cost ({base_currency})']
    portfolio_data[f'Total Return ({base_currency})'] = portfolio_data[f'Capital P&L ({base_currency})'] + portfolio_data[f'Dividends ({base_currency})']
    
    portfolio_data['Return (%)'] = portfolio_data.apply(
        lambda r: (r[f'Total Return ({base_currency})'] / r[f'Total Cost ({base_currency})']) * 100 if abs(r[f'Total Cost ({base_currency})']) > 0 else 0, 
        axis=1
    )
    
    total_value_for_weight = portfolio_data[f'Current Value ({base_currency})'].sum()
    portfolio_data['% Weight'] = portfolio_data.apply(
        lambda r: (r[f'Current Value ({base_currency})'] / total_value_for_weight) * 100 if total_value_for_weight > 0 else 0.0,
        axis=1
    )
    
    cols = ['Ticker', 'Type', 'Shares', 'Purchase Price', 'Transaction Fee', 'Purchase Date', f'Live Price ({base_currency})', f'Dividends ({base_currency})', f'Total Cost ({base_currency})', f'Current Value ({base_currency})', f'Total Return ({base_currency})', 'Return (%)', '% Weight']
    portfolio_data = portfolio_data[cols]
    
    # FIX: Convert string dates to actual datetime objects so the table can render the calendar picker
    portfolio_data['Purchase Date'] = pd.to_datetime(portfolio_data['Purchase Date']).dt.date
    
    edited_df = st.data_editor(
        portfolio_data,
        use_container_width=True,
        num_rows="dynamic",
        hide_index=True,
        column_config={
            "Type": st.column_config.SelectboxColumn("Type", options=["Buy", "Sell"], required=True),
            "Purchase Price": st.column_config.NumberColumn("Price / Share", format=f"{sym}%.2f"),
            "Transaction Fee": st.column_config.NumberColumn(format=f"{sym}%.2f"),
            "Purchase Date": st.column_config.DateColumn("Date"),
            f'Live Price ({base_currency})': st.column_config.NumberColumn(format=f"{sym}%.2f", disabled=True),
            f'Dividends ({base_currency})': st.column_config.NumberColumn(format=f"{sym}%.2f", disabled=True),
            f'Total Cost ({base_currency})': st.column_config.NumberColumn("Net Cost", format=f"{sym}%.2f", disabled=True),
            f'Current Value ({base_currency})': st.column_config.NumberColumn(format=f"{sym}%.2f", disabled=True),
            f'Total Return ({base_currency})': st.column_config.NumberColumn(format=f"{sym}%.2f", disabled=True),
            "Return (%)": st.column_config.NumberColumn(format="%.2f%%", disabled=True),
            "% Weight": st.column_config.NumberColumn(format="%.2f%%", disabled=True),
        }
    )
    
    # FIX: Convert dates back to strings so we can compare them and save them safely
    edited_df['Purchase Date'] = pd.to_datetime(edited_df['Purchase Date']).dt.strftime('%Y-%m-%d')
    
    base_cols = ['Ticker', 'Type', 'Shares', 'Purchase Price', 'Transaction Fee', 'Purchase Date']
    if not edited_df[base_cols].equals(st.session_state.portfolio[base_cols]):
        st.session_state.portfolio = edited_df[base_cols]
        save_data(st.session_state.portfolio)
        st.rerun() 
    
    st.markdown("---")
    
    total_cost = portfolio_data[f'Total Cost ({base_currency})'].sum()
    total_divs = portfolio_data[f'Dividends ({base_currency})'].sum()
    total_return_dollars = portfolio_data[f'Total Return ({base_currency})'].sum()
    total_current_value = portfolio_data[f'Current Value ({base_currency})'].sum()
    total_return_percent = (total_return_dollars / total_cost) * 100 if total_cost > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(f"Net Capital Deployed", f"{sym}{total_cost:,.2f}")
    col2.metric(f"Current Value", f"{sym}{total_current_value:,.2f}")
    col3.metric(f"Dividends Collected", f"{sym}{total_divs:,.2f}")
    col4.metric(f"Total Return", f"{sym}{total_return_dollars:,.2f}", f"{total_return_percent:+.2f}%")
    
    st.markdown("---")
    
    st.subheader("?? 1-Year Performance Race")
    st.caption("This chart shows the percentage growth of your individual assets over the last 365 days.")
    
    unique_tickers = portfolio_data['Ticker'].unique().tolist()
    if unique_tickers:
        try:
            with st.spinner("Crunching historical market data..."):
                hist_data = yf.download(unique_tickers, period="1y")['Close']
                if isinstance(hist_data, pd.Series):
                    hist_data = hist_data.to_frame(name=unique_tickers[0])
                hist_data.index = hist_data.index.tz_localize(None)
                hist_data = hist_data.ffill()
                normalized_data = ((hist_data / hist_data.iloc[0]) - 1) * 100
                st.line_chart(normalized_data)
        except Exception as e:
            st.warning("Could not load historical chart data right now. Yahoo Finance might be taking a quick breather!")

    st.markdown("---")
    st.subheader("Asset Allocation")
    
    chart_data = portfolio_data[portfolio_data[f'Current Value ({base_currency})'] > 0]
    if not chart_data.empty:
        st.bar_chart(data=chart_data.set_index('Ticker')[f'Current Value ({base_currency})'])

    st.markdown("---")
    if st.button("Clear Entire Portfolio"):
        st.session_state.portfolio = pd.DataFrame(columns=['Ticker', 'Type', 'Shares', 'Purchase Price', 'Transaction Fee', 'Purchase Date'])
        save_data(st.session_state.portfolio)
        st.rerun()
else:
    st.info("Your portfolio is empty. Add assets on the left!")