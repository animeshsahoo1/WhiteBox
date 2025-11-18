# Kaggle cell: fixed plotting for short windows (uses mdates and small bar widths)
import os, sys, json, io, base64, subprocess
from typing import List, Dict, Optional
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from IPython.display import display, Image

# Optional dependencies for download_ohlcv and compute_indicators_talib
# Not required for TechnicalTools class
yfinance_available = False
talib_available = False

try:
    import yfinance as yf
    yfinance_available = True
except Exception:
    yf = None
    print("⚠️ Warning: yfinance not installed. download_ohlcv() will not be available.")

try:
    import talib
    talib_available = True
except Exception:
    talib = None
    print("⚠️ Warning: TA-Lib not installed. compute_indicators_talib() will not be available.")

# ---------- helpers ----------
def scalarize(v):
    if isinstance(v, (pd.Series, pd.DataFrame, np.ndarray, list, tuple)):
        a = np.asarray(v)
        return np.nan if a.size == 0 else a.ravel()[0]
    return v

def float_or_nan(x):
    try:
        if pd.isna(x):
            return np.nan
    except Exception:
        pass
    try:
        return float(x)
    except Exception:
        try:
            a = np.asarray(x)
            return np.nan if a.size == 0 else float(a.ravel()[0])
        except Exception:
            return np.nan

def fig_to_base64(fig, fname=None, dpi=180):
    if fname:
        fig.savefig(fname, dpi=dpi, bbox_inches="tight", pad_inches=0.06)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", pad_inches=0.06)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return b64

def show_b64(b64, width=900):
    display(Image(data=base64.b64decode(b64), width=width))

# ---------- download + normalization ----------
def download_ohlcv(ticker: str = "AAPL", period: str = "7d", interval: str = "1m") -> pd.DataFrame:
    if not yfinance_available:
        raise ImportError("yfinance is required for download_ohlcv(). Install with: pip install yfinance")
    
    df = yf.download(tickers=ticker, period=period, interval=interval,
                     progress=False, threads=False, auto_adjust=False)
    if df.empty:
        raise RuntimeError(f"No data downloaded for {ticker} {period} {interval}")
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    # Flatten MultiIndex columns if present
    if getattr(df.columns, "nlevels", 1) > 1:
        df.columns = [c[0] if isinstance(c, tuple) and len(c) > 0 else c for c in df.columns]
    df.columns = [str(c).strip() for c in df.columns]
    for c in ["Open", "High", "Low", "Close", "Volume", "Adj Close"]:
        if c not in df.columns:
            df[c] = np.nan
    # fallback: use Adj Close if Close missing/empty
    if ("Close" not in df.columns or df["Close"].isnull().all()) and ("Adj Close" in df.columns and not df["Adj Close"].isnull().all()):
        df["Close"] = df["Adj Close"]
    return df

# ---------- coercion + talib ----------
def coerce_numeric_df(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c].apply(scalarize), errors="coerce")
    return df

def to_1d_float(series: pd.Series) -> np.ndarray:
    arr = np.asarray([scalarize(x) for x in series.values])
    if arr.ndim > 1:
        arr = arr.ravel()
    try:
        return arr.astype(float)
    except Exception:
        return np.array([float_or_nan(x) for x in arr], dtype=float)

def compute_indicators_talib(df: pd.DataFrame) -> Dict[str, pd.Series]:
    if not talib_available:
        raise ImportError("TA-Lib is required for compute_indicators_talib(). Install with: pip install ta-lib-binary")
    
    d = df.copy()
    coerce_numeric_df(d, ["Open", "High", "Low", "Close", "Volume"])
    close = d["Close"].astype(float)
    high = d["High"].astype(float)
    low = d["Low"].astype(float)
    vol = d["Volume"].astype(float)
    out = {}
    out["sma_20"] = pd.Series(talib.SMA(to_1d_float(close), timeperiod=20), index=d.index)
    out["sma_50"] = pd.Series(talib.SMA(to_1d_float(close), timeperiod=50), index=d.index)
    out["ema_20"] = pd.Series(talib.EMA(to_1d_float(close), timeperiod=20), index=d.index)
    out["ema_50"] = pd.Series(talib.EMA(to_1d_float(close), timeperiod=50), index=d.index)
    upper, middle, lower = talib.BBANDS(to_1d_float(close), timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
    out["bb_upper"], out["bb_middle"], out["bb_lower"] = pd.Series(upper, index=d.index), pd.Series(middle, index=d.index), pd.Series(lower, index=d.index)
    out["rsi_14"] = pd.Series(talib.RSI(to_1d_float(close), timeperiod=14), index=d.index)
    macd, macdsignal, macdhist = talib.MACD(to_1d_float(close), fastperiod=12, slowperiod=26, signalperiod=9)
    out["macd"], out["macd_signal"], out["macd_hist"] = pd.Series(macd, index=d.index), pd.Series(macdsignal, index=d.index), pd.Series(macdhist, index=d.index)
    slowk, slowd = talib.STOCH(to_1d_float(high), to_1d_float(low), to_1d_float(close), fastk_period=14, slowk_period=3, slowd_period=3)
    out["stoch_k"], out["stoch_d"] = pd.Series(slowk, index=d.index), pd.Series(slowd, index=d.index)
    out["atr_14"] = pd.Series(talib.ATR(to_1d_float(high), to_1d_float(low), to_1d_float(close), timeperiod=14), index=d.index)
    out["adx_14"] = pd.Series(talib.ADX(to_1d_float(high), to_1d_float(low), to_1d_float(close), timeperiod=14), index=d.index)
    out["roc_10"] = pd.Series(talib.ROC(to_1d_float(close), timeperiod=10), index=d.index)
    out["obv"] = pd.Series(talib.OBV(to_1d_float(close), to_1d_float(vol)), index=d.index)
    out["willr_14"] = pd.Series(talib.WILLR(to_1d_float(high), to_1d_float(low), to_1d_float(close), timeperiod=14), index=d.index)
    return out

# ---------- Auto-detection helpers ----------
def detect_data_interval(timestamps: pd.DatetimeIndex) -> float:
    """
    Auto-detect the data interval in seconds from timestamps.
    
    Args:
        timestamps: DatetimeIndex of the data
    
    Returns:
        Interval in seconds (e.g., 5 for 5-second data, 60 for 1-minute data)
    """
    if len(timestamps) < 2:
        return 60  # default to 1 minute if not enough data
    
    # Calculate differences between consecutive timestamps
    diffs = timestamps.to_series().diff().dropna()
    
    # Get median difference to handle potential gaps
    median_diff = diffs.median()
    
    # Convert to seconds
    interval_seconds = median_diff.total_seconds()
    
    return max(interval_seconds, 1)  # minimum 1 second

# ---------- plotting helpers using mdates ----------
def plot_price_with_overlays_window(df_window: pd.DataFrame, inds_window: Dict[str, pd.Series], outpath: str, interval_seconds: int = None):
    """
    Plot price with overlays for a window.
    Auto-detects data interval if not specified.
    
    Args:
        df_window: DataFrame with OHLCV data
        inds_window: Dictionary of indicator series
        outpath: Output path for saving the plot
        interval_seconds: Interval in seconds (auto-detected if None)
                         Examples: 5 (5-second candles), 60 (1-minute), 300 (5-minute)
    """
    fig, ax = plt.subplots(2,1, figsize=(12,7), gridspec_kw={"height_ratios":[3,1]}, sharex=True)
    ax0, ax1 = ax
    dates = pd.to_datetime(df_window.index)
    num_dates = mdates.date2num(dates.to_pydatetime())
    if len(num_dates) == 0:
        return fig_to_base64(fig, outpath)

    # Auto-detect interval if not specified
    if interval_seconds is None:
        interval_seconds = detect_data_interval(dates)
        print(f"🕐 Auto-detected data interval: {interval_seconds} seconds")

    # Calculate bar width based on interval in seconds
    second = 1.0 / (24 * 60 * 60)  # one second in matplotlib day units
    bar_width = max(second * interval_seconds * 0.6, 1e-6)
    min_height = second * interval_seconds * 0.01  # minimum bar height

    # wicks & bodies with numeric x
    ax0.vlines(num_dates, df_window["Low"].values, df_window["High"].values, linewidth=0.8, color="black", zorder=1)
    for xd, (_, row) in zip(num_dates, df_window.iterrows()):
        o = float_or_nan(row.get("Open", np.nan)); c = float_or_nan(row.get("Close", np.nan))
        if np.isnan(o) or np.isnan(c):
            continue
        color = "#1f77b4" if c >= o else "#d62728"
        lower = min(o, c); height = abs(c - o)
        rect = plt.Rectangle((xd - bar_width/2, lower), bar_width, height if height > 0 else min_height,
                             facecolor=color, edgecolor=color, alpha=0.9, zorder=2)
        ax0.add_patch(rect)

    # overlays reindexed to df_window.index
    for k in ("sma_20","sma_50","ema_20","ema_50","bb_upper","bb_middle","bb_lower"):
        if k in inds_window:
            series = inds_window[k].reindex(df_window.index)
            ax0.plot(num_dates, series.values, label=k.replace("_"," ").upper(), linewidth=1, zorder=3)

    ax0.set_ylabel("Price"); ax0.legend(loc="upper left", fontsize=8); ax0.grid(alpha=0.2)

    # volume bars (small width)
    vol = pd.to_numeric(df_window["Volume"].fillna(0), errors="coerce").values
    ax1.bar(num_dates, vol, width=bar_width, align="center", alpha=0.6)
    ax1.set_ylabel("Volume")

    # format x-axis
    ax1.xaxis_date()
    locator = mdates.AutoDateLocator()
    formatter = mdates.ConciseDateFormatter(locator)
    ax1.xaxis.set_major_locator(locator)
    ax1.xaxis.set_major_formatter(formatter)
    plt.setp(ax1.get_xticklabels(), rotation=45, ha="right")
    plt.tight_layout()
    return fig_to_base64(fig, outpath)

def plot_single_window(df_window: pd.DataFrame, series_window: pd.Series, title: str, outpath: str, ylim=None):
    # use numeric x for consistency
    dates = pd.to_datetime(df_window.index)
    num_dates = mdates.date2num(dates.to_pydatetime())
    fig, ax = plt.subplots(figsize=(10,2.8))
    ax.plot(num_dates, series_window.reindex(df_window.index).values, label=title)
    if ylim is not None:
        ax.set_ylim(*ylim)
    ax.legend(loc="upper left"); ax.grid(alpha=0.2)
    ax.xaxis_date()
    locator = mdates.AutoDateLocator()
    formatter = mdates.ConciseDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    plt.tight_layout()
    return fig_to_base64(fig, outpath)


# =====================================================================
# EXAMPLE/TEST CODE - Only runs if executed directly
# =====================================================================
def _run_example():
    """Example usage of download and plotting functions (requires yfinance and talib)."""
    # ---------- user params ----------
    TICKER = "AAPL"
    PERIOD = "7d"
    INTERVAL = "1m"
    MINUTES = 10
    OUT_PREFIX = ""
    SHOW_INLINE = True

    if OUT_PREFIX and not os.path.exists(OUT_PREFIX):
        os.makedirs(OUT_PREFIX, exist_ok=True)

    # ---------- flow ----------
    print(f"Downloading {TICKER} {PERIOD} {INTERVAL} ...")
    df = download_ohlcv(TICKER, period=PERIOD, interval=INTERVAL)
    print("Downloaded rows:", len(df))
    display(df.head())
    
    inds = compute_indicators_talib(df)

    # window selection
    last_ts = df.index.max()
    start_ts = last_ts - pd.Timedelta(minutes=int(MINUTES))
    df_win = df.loc[df.index >= start_ts].copy()
    if df_win.empty:
        print(f"Warning: no rows after {start_ts}. Falling back to last {MINUTES} rows.")
        df_win = df.tail(MINUTES).copy()
    print("Window rows:", len(df_win), "from", df_win.index.min(), "to", df_win.index.max())

    # align indicators to window
    inds_win = {}
    for k,v in inds.items():
        try:
            inds_win[k] = v.reindex(df_win.index)
        except Exception:
            inds_win[k] = v.reindex(df_win.index, method="nearest", tolerance=pd.Timedelta(seconds=59))

    # ---------- plotting & save ----------
    outputs = {}

    price_path = f"{OUT_PREFIX}{TICKER}_price_overlays_window.png"
    outputs["price_overlay_b64"] = plot_price_with_overlays_window(df_win, inds_win, price_path)
    outputs["price_overlay_path"] = os.path.abspath(price_path)
    if SHOW_INLINE:
        show_b64(outputs["price_overlay_b64"])

    # MACD: use numeric dates + small bar width for histogram
    if "macd" in inds_win:
        macd_p = f"{OUT_PREFIX}{TICKER}_macd_window.png"
        fig, ax = plt.subplots(2,1, figsize=(10,5), gridspec_kw={"height_ratios":[2,1]}, sharex=True)
        dts = pd.to_datetime(df_win.index)
        num_dates = mdates.date2num(dts.to_pydatetime())
        minute = 1.0 / (24 * 60)
        bar_width = max(minute * 0.8, 1e-6)

        macd_vals = inds_win.get("macd").values
        sig_vals = inds_win.get("macd_signal").values
        hist_vals = inds_win.get("macd_hist").values

        ax[0].plot(num_dates, macd_vals, label="MACD", linewidth=1.2, zorder=4)
        ax[0].plot(num_dates, sig_vals, label="Signal", linewidth=1.0, zorder=5)
        # draw histogram with small width in days
        ax[0].bar(num_dates, hist_vals, width=bar_width, align="center", alpha=0.7, zorder=2)
        ax[0].axhline(0, linestyle="--", linewidth=0.6, color="black")
        ax[0].legend(loc="upper left"); ax[0].grid(alpha=0.2)

        if "rsi_14" in inds_win:
            ax[1].plot(num_dates, inds_win["rsi_14"].values, label="RSI(14)")
            ax[1].axhline(70, linestyle="--"); ax[1].axhline(30, linestyle="--")
            ax[1].set_ylim(0,100); ax[1].legend(loc="upper left")

        ax[1].xaxis_date()
        locator = mdates.AutoDateLocator(); formatter = mdates.ConciseDateFormatter(locator)
        ax[1].xaxis.set_major_locator(locator); ax[1].xaxis.set_major_formatter(formatter)
        plt.setp(ax[1].get_xticklabels(), rotation=45, ha="right")
        plt.tight_layout()
        outputs["macd_b64"] = fig_to_base64(fig, macd_p)
        outputs["macd_path"] = os.path.abspath(macd_p)
        if SHOW_INLINE:
            show_b64(outputs["macd_b64"])

    # RSI
    if "rsi_14" in inds_win:
        p = f"{OUT_PREFIX}{TICKER}_rsi_window.png"
        outputs["rsi_b64"] = plot_single_window(df_win, inds_win["rsi_14"], "RSI(14)", p, ylim=(0,100))
        outputs["rsi_path"] = os.path.abspath(p)
        if SHOW_INLINE:
            show_b64(outputs["rsi_b64"])

    # Stochastic (%K)
    if "stoch_k" in inds_win:
        p = f"{OUT_PREFIX}{TICKER}_stoch_window.png"
        outputs["stoch_b64"] = plot_single_window(df_win, inds_win["stoch_k"], "%K", p, ylim=(0,100))
        outputs["stoch_path"] = os.path.abspath(p)
        if SHOW_INLINE:
            show_b64(outputs["stoch_b64"])

    # save CSV snapshot & JSON
    csv_path = f"{OUT_PREFIX}{TICKER}_record_window.csv"
    df_win.reset_index().to_csv(csv_path, index=False)
    outputs["csv"] = os.path.abspath(csv_path)

    summary = {}
    for k,s in inds.items():
        try:
            summary[k + "_tail"] = pd.Series(s).dropna().astype(float).round(4).tolist()[-20:]
        except Exception:
            summary[k + "_tail"] = []
    outputs["indicators_summary"] = summary
    outputs["n_points_full"] = len(df)
    outputs["n_points_window"] = len(df_win)
    outputs["ticker"] = TICKER
    outputs["period"] = PERIOD
    outputs["interval"] = INTERVAL
    json_path = f"{OUT_PREFIX}{TICKER}_summary_window.json"
    with open(json_path, "w") as fh:
        json.dump(outputs, fh, default=str, indent=2)

    print("Saved:", json_path)
    print("Outputs keys:", list(outputs.keys()))


# =====================================================================
# TECHNICAL TOOLS CLASS FOR PATHWAY INTEGRATION
# =====================================================================

class TechnicalTools:
    """
    Tools for generating technical analysis charts and plots.
    Works with Pathway data structures (lists, tuples, dicts) without requiring pandas conversion.
    """
    
    def __init__(self):
        """Initialize the technical tools."""
        pass
    
    # ============ CHART GENERATION TOOLS (for LangGraph agents) ============
    
    class generate_kline_image:
        """Tool to generate candlestick chart from OHLCV data."""
        
        @staticmethod
        def invoke(params: dict) -> dict:
            """
            Generate a candlestick chart image.
            
            Args:
                params: Dictionary with 'kline_data' containing:
                    - Datetime: List of datetime strings
                    - Open: List of open prices
                    - High: List of high prices
                    - Low: List of low prices
                    - Close: List of close prices
            
            Returns:
                Dictionary with 'pattern_image' as base64 encoded PNG
            """
            try:
                kline_data = params.get('kline_data', {})
                
                # Extract data
                datetimes = kline_data.get('Datetime', [])
                opens = kline_data.get('Open', [])
                highs = kline_data.get('High', [])
                lows = kline_data.get('Low', [])
                closes = kline_data.get('Close', [])
                
                if not datetimes or len(datetimes) == 0:
                    return {"pattern_image": ""}
                
                # Convert datetime strings to datetime objects
                dates = pd.to_datetime(datetimes)
                num_dates = mdates.date2num(dates.to_pydatetime())
                
                # Create figure
                fig, ax = plt.subplots(figsize=(12, 6))
                
                # Calculate bar width (adaptive based on data frequency)
                if len(num_dates) > 1:
                    avg_interval = np.mean(np.diff(num_dates))
                    bar_width = avg_interval * 0.6
                else:
                    # Default: 1 second (change this for your use case)
                    # For 1 second candles: 1.0 / (24 * 60 * 60)
                    # For 5 second candles: 5.0 / (24 * 60 * 60)
                    # For 1 minute candles: 1.0 / (24 * 60)
                    bar_width = 1.0 / (24 * 60 * 60)  # 1 second default
                
                # Draw candlesticks
                for i, (xd, o, h, l, c) in enumerate(zip(num_dates, opens, highs, lows, closes)):
                    # Wick
                    ax.vlines(xd, l, h, linewidth=0.8, color='black', zorder=1)
                    
                    # Body
                    color = '#00ff00' if c >= o else '#ff0000'  # green up, red down
                    lower = min(o, c)
                    height = abs(c - o) if abs(c - o) > 0 else bar_width * 0.01
                    
                    rect = plt.Rectangle((xd - bar_width/2, lower), bar_width, height,
                                        facecolor=color, edgecolor=color, alpha=0.8, zorder=2)
                    ax.add_patch(rect)
                
                # Formatting
                ax.set_ylabel('Price', fontsize=12)
                ax.set_title('Candlestick Pattern Chart', fontsize=14, fontweight='bold')
                ax.grid(alpha=0.3, linestyle='--')
                
                # X-axis formatting
                ax.xaxis_date()
                locator = mdates.AutoDateLocator()
                formatter = mdates.ConciseDateFormatter(locator)
                ax.xaxis.set_major_locator(locator)
                ax.xaxis.set_major_formatter(formatter)
                plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
                
                plt.tight_layout()
                
                # Convert to base64
                b64_image = fig_to_base64(fig)
                
                return {"pattern_image": b64_image}
                
            except Exception as e:
                print(f"Error generating candlestick image: {e}")
                import traceback
                traceback.print_exc()
                return {"pattern_image": ""}
    
    class generate_trend_image:
        """Tool to generate trend chart with support/resistance levels."""
        
        @staticmethod
        def invoke(params: dict) -> dict:
            """
            Generate a trend chart with support and resistance levels.
            
            Args:
                params: Dictionary with 'kline_data' containing OHLCV data
            
            Returns:
                Dictionary with 'trend_image' as base64 encoded PNG
            """
            try:
                kline_data = params.get('kline_data', {})
                
                # Extract data
                datetimes = kline_data.get('Datetime', [])
                highs = kline_data.get('High', [])
                lows = kline_data.get('Low', [])
                closes = kline_data.get('Close', [])
                
                if not datetimes or len(datetimes) == 0:
                    return {"trend_image": ""}
                
                # Convert datetime strings to datetime objects
                dates = pd.to_datetime(datetimes)
                num_dates = mdates.date2num(dates.to_pydatetime())
                
                # Create figure
                fig, ax = plt.subplots(figsize=(12, 6))
                
                # Plot closing price
                ax.plot(num_dates, closes, label='Close Price', color='#1f77b4', linewidth=2, zorder=3)
                
                # Calculate and plot support/resistance levels
                if len(closes) >= 5:
                    # Simple support/resistance: use min/max of recent period
                    resistance = max(highs)
                    support = min(lows)
                    
                    ax.axhline(resistance, color='red', linestyle='--', linewidth=1.5, 
                              label=f'Resistance: {resistance:.2f}', alpha=0.7, zorder=2)
                    ax.axhline(support, color='green', linestyle='--', linewidth=1.5,
                              label=f'Support: {support:.2f}', alpha=0.7, zorder=2)
                    
                    # Add a middle line (average)
                    middle = (resistance + support) / 2
                    ax.axhline(middle, color='orange', linestyle=':', linewidth=1,
                              label=f'Mid: {middle:.2f}', alpha=0.5, zorder=1)
                
                # Formatting
                ax.set_ylabel('Price', fontsize=12)
                ax.set_title('Trend Analysis with Support/Resistance', fontsize=14, fontweight='bold')
                ax.legend(loc='best', fontsize=10)
                ax.grid(alpha=0.3, linestyle='--')
                
                # X-axis formatting
                ax.xaxis_date()
                locator = mdates.AutoDateLocator()
                formatter = mdates.ConciseDateFormatter(locator)
                ax.xaxis.set_major_locator(locator)
                ax.xaxis.set_major_formatter(formatter)
                plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
                
                plt.tight_layout()
                
                # Convert to base64
                b64_image = fig_to_base64(fig)
                
                return {"trend_image": b64_image}
                
            except Exception as e:
                print(f"Error generating trend image: {e}")
                import traceback
                traceback.print_exc()
                return {"trend_image": ""}
    
    # ============ INDICATOR PLOTS (for comprehensive analysis) ============
    
    @staticmethod
    def generate_all_indicator_plots(
        datetimes: list,
        closes: list,
        rsi: list = None,
        macd: list = None,
        macd_signal: list = None,
        macd_hist: list = None,
        stoch_k: list = None,
        stoch_d: list = None,
        roc: list = None,
        willr: list = None,
        save_dir: str = None,
        interval_seconds: float = None
    ) -> dict:
        """
        Generate all indicator plots for comprehensive market analysis.
        Works directly with Pathway data (lists) - no pandas conversion needed.
        Auto-detects data interval for proper bar widths.
        
        Args:
            datetimes: List of datetime strings
            closes: List of closing prices
            rsi: List of RSI values
            macd: List of MACD line values
            macd_signal: List of MACD signal values
            macd_hist: List of MACD histogram values
            stoch_k: List of Stochastic %K values
            stoch_d: List of Stochastic %D values
            roc: List of Rate of Change values
            willr: List of Williams %R values
            save_dir: Optional directory to save PNG files
            interval_seconds: Data interval in seconds (auto-detected if None)
                            Examples: 5 (5-sec), 60 (1-min), 300 (5-min)
        
        Returns:
            Dictionary with base64 encoded images for each indicator
        """
        results = {}
        
        if not datetimes or len(datetimes) == 0:
            return results
        
        try:
            # Convert datetimes to numeric for matplotlib
            dates = pd.to_datetime(datetimes)
            num_dates = mdates.date2num(dates.to_pydatetime())
            
            # Auto-detect interval if not specified
            if interval_seconds is None:
                interval_seconds = detect_data_interval(dates)
                print(f"🕐 Auto-detected data interval for plots: {interval_seconds} seconds")
            
            # Calculate bar width for histograms
            second = 1.0 / (24 * 60 * 60)
            bar_width = max(second * interval_seconds * 0.6, 1e-6)
            
            # Helper function to create subplot
            def create_indicator_plot(title, data, ylabel, ylim=None, hlines=None):
                """Create a single indicator plot."""
                if data is None or len(data) == 0:
                    return None
                
                fig, ax = plt.subplots(figsize=(12, 4))
                ax.plot(num_dates[:len(data)], data, label=title, linewidth=2, color='#1f77b4')
                
                # Add horizontal reference lines if specified
                if hlines:
                    for value, color, style, label in hlines:
                        ax.axhline(value, color=color, linestyle=style, linewidth=1, 
                                  label=label, alpha=0.7)
                
                if ylim:
                    ax.set_ylim(ylim)
                
                ax.set_ylabel(ylabel, fontsize=11)
                ax.set_title(title, fontsize=13, fontweight='bold')
                ax.legend(loc='best', fontsize=9)
                ax.grid(alpha=0.3, linestyle='--')
                
                # X-axis formatting
                ax.xaxis_date()
                locator = mdates.AutoDateLocator()
                formatter = mdates.ConciseDateFormatter(locator)
                ax.xaxis.set_major_locator(locator)
                ax.xaxis.set_major_formatter(formatter)
                plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
                
                plt.tight_layout()
                return fig
            
            # 1. RSI Plot
            if rsi is not None and len(rsi) > 0:
                fig = create_indicator_plot(
                    'Relative Strength Index (RSI)',
                    rsi,
                    'RSI',
                    ylim=(0, 100),
                    hlines=[
                        (70, 'red', '--', 'Overbought (70)'),
                        (30, 'green', '--', 'Oversold (30)'),
                        (50, 'gray', ':', 'Neutral (50)')
                    ]
                )
                if fig:
                    fname = f"{save_dir}/rsi_plot.png" if save_dir else None
                    results['rsi_plot'] = fig_to_base64(fig, fname)
            
            # 2. MACD Plot
            if macd is not None and len(macd) > 0:
                fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6), 
                                               gridspec_kw={'height_ratios': [2, 1]}, sharex=True)
                
                # MACD and Signal lines
                data_len = min(len(num_dates), len(macd))
                ax1.plot(num_dates[:data_len], macd[:data_len], label='MACD', 
                        linewidth=2, color='#1f77b4')
                
                if macd_signal and len(macd_signal) > 0:
                    sig_len = min(len(num_dates), len(macd_signal))
                    ax1.plot(num_dates[:sig_len], macd_signal[:sig_len], label='Signal', 
                            linewidth=2, color='#ff7f0e')
                
                ax1.axhline(0, color='black', linestyle='-', linewidth=0.5, alpha=0.5)
                ax1.set_ylabel('MACD', fontsize=11)
                ax1.set_title('MACD (Moving Average Convergence Divergence)', 
                             fontsize=13, fontweight='bold')
                ax1.legend(loc='best', fontsize=9)
                ax1.grid(alpha=0.3, linestyle='--')
                
                # MACD Histogram
                if macd_hist and len(macd_hist) > 0:
                    hist_len = min(len(num_dates), len(macd_hist))
                    colors = ['green' if h >= 0 else 'red' for h in macd_hist[:hist_len]]
                    ax2.bar(num_dates[:hist_len], macd_hist[:hist_len], width=bar_width,
                           color=colors, alpha=0.7, label='Histogram')
                
                ax2.axhline(0, color='black', linestyle='-', linewidth=0.5, alpha=0.5)
                ax2.set_ylabel('Histogram', fontsize=11)
                ax2.legend(loc='best', fontsize=9)
                ax2.grid(alpha=0.3, linestyle='--')
                
                # X-axis formatting
                ax2.xaxis_date()
                locator = mdates.AutoDateLocator()
                formatter = mdates.ConciseDateFormatter(locator)
                ax2.xaxis.set_major_locator(locator)
                ax2.xaxis.set_major_formatter(formatter)
                plt.setp(ax2.get_xticklabels(), rotation=45, ha='right')
                
                plt.tight_layout()
                fname = f"{save_dir}/macd_plot.png" if save_dir else None
                results['macd_plot'] = fig_to_base64(fig, fname)
            
            # 3. Stochastic Oscillator
            if stoch_k is not None and len(stoch_k) > 0:
                fig, ax = plt.subplots(figsize=(12, 4))
                
                k_len = min(len(num_dates), len(stoch_k))
                ax.plot(num_dates[:k_len], stoch_k[:k_len], label='%K', 
                       linewidth=2, color='#1f77b4')
                
                if stoch_d and len(stoch_d) > 0:
                    d_len = min(len(num_dates), len(stoch_d))
                    ax.plot(num_dates[:d_len], stoch_d[:d_len], label='%D', 
                           linewidth=2, color='#ff7f0e')
                
                ax.axhline(80, color='red', linestyle='--', linewidth=1, 
                          label='Overbought (80)', alpha=0.7)
                ax.axhline(20, color='green', linestyle='--', linewidth=1,
                          label='Oversold (20)', alpha=0.7)
                
                ax.set_ylim(0, 100)
                ax.set_ylabel('Stochastic', fontsize=11)
                ax.set_title('Stochastic Oscillator (%K, %D)', fontsize=13, fontweight='bold')
                ax.legend(loc='best', fontsize=9)
                ax.grid(alpha=0.3, linestyle='--')
                
                # X-axis formatting
                ax.xaxis_date()
                locator = mdates.AutoDateLocator()
                formatter = mdates.ConciseDateFormatter(locator)
                ax.xaxis.set_major_locator(locator)
                ax.xaxis.set_major_formatter(formatter)
                plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
                
                plt.tight_layout()
                fname = f"{save_dir}/stochastic_plot.png" if save_dir else None
                results['stochastic_plot'] = fig_to_base64(fig, fname)
            
            # 4. Rate of Change (ROC)
            if roc is not None and len(roc) > 0:
                fig = create_indicator_plot(
                    'Rate of Change (ROC)',
                    roc,
                    'ROC (%)',
                    hlines=[(0, 'black', '-', 'Zero Line')]
                )
                if fig:
                    fname = f"{save_dir}/roc_plot.png" if save_dir else None
                    results['roc_plot'] = fig_to_base64(fig, fname)
            
            # 5. Williams %R
            if willr is not None and len(willr) > 0:
                fig = create_indicator_plot(
                    'Williams %R',
                    willr,
                    'Williams %R',
                    ylim=(-100, 0),
                    hlines=[
                        (-20, 'red', '--', 'Overbought (-20)'),
                        (-80, 'green', '--', 'Oversold (-80)')
                    ]
                )
                if fig:
                    fname = f"{save_dir}/willr_plot.png" if save_dir else None
                    results['willr_plot'] = fig_to_base64(fig, fname)
            
            # 6. Price chart with close
            if closes and len(closes) > 0:
                fig = create_indicator_plot(
                    'Closing Price',
                    closes,
                    'Price',
                    hlines=None
                )
                if fig:
                    fname = f"{save_dir}/price_plot.png" if save_dir else None
                    results['price_plot'] = fig_to_base64(fig, fname)
            
            return results
            
        except Exception as e:
            print(f"Error generating indicator plots: {e}")
            import traceback
            traceback.print_exc()
            return results
    
    # ============ USER-FACING ANALYSIS TOOLS ============
    
    @staticmethod
    def analyze_indicators_for_period(
        symbol: str,
        kline_data: dict,
        indicators: dict,
        time_description: str = "recent period",
        save_dir: str = None
    ) -> dict:
        """
        User-facing tool to analyze specific indicators for a time interval.
        Generates plots and summary for user queries like:
        - "Analyze RSI and MACD for AAPL for the last 15 minutes"
        - "Show me Stochastic indicator for Tesla stock"
        
        Args:
            symbol: Stock symbol
            kline_data: Dictionary with Datetime, Open, High, Low, Close
            indicators: Dictionary with indicator values (rsi, macd, etc.)
            time_description: Human-readable time description
            save_dir: Directory to save plots
        
        Returns:
            Dictionary with analysis summary and plot images
        """
        try:
            # Extract data
            datetimes = kline_data.get('Datetime', [])
            closes = kline_data.get('Close', [])
            
            # Generate plots
            plots = TechnicalTools.generate_all_indicator_plots(
                datetimes=datetimes,
                closes=closes,
                rsi=indicators.get('rsi'),
                macd=indicators.get('macd'),
                macd_signal=indicators.get('macd_signal'),
                macd_hist=indicators.get('macd_hist'),
                stoch_k=indicators.get('stoch_k'),
                stoch_d=indicators.get('stoch_d'),
                roc=indicators.get('roc'),
                willr=indicators.get('willr'),
                save_dir=save_dir
            )
            
            # Generate summary
            summary = f"# Technical Analysis: {symbol}\n\n"
            summary += f"**Period:** {time_description}\n"
            summary += f"**Data Points:** {len(datetimes)}\n\n"
            
            # Latest values
            summary += "## Latest Indicator Values\n\n"
            
            if indicators.get('rsi') and len(indicators['rsi']) > 0:
                latest_rsi = indicators['rsi'][-1]
                summary += f"- **RSI:** {latest_rsi:.2f}"
                if latest_rsi > 70:
                    summary += " (Overbought ⚠️)\n"
                elif latest_rsi < 30:
                    summary += " (Oversold 📉)\n"
                else:
                    summary += " (Neutral)\n"
            
            if indicators.get('macd') and len(indicators['macd']) > 0:
                latest_macd = indicators['macd'][-1]
                latest_signal = indicators.get('macd_signal', [0])[-1] if indicators.get('macd_signal') else 0
                summary += f"- **MACD:** {latest_macd:.2f} | Signal: {latest_signal:.2f}"
                if latest_macd > latest_signal:
                    summary += " (Bullish 📈)\n"
                else:
                    summary += " (Bearish 📉)\n"
            
            if indicators.get('stoch_k') and len(indicators['stoch_k']) > 0:
                latest_k = indicators['stoch_k'][-1]
                summary += f"- **Stochastic %K:** {latest_k:.2f}"
                if latest_k > 80:
                    summary += " (Overbought ⚠️)\n"
                elif latest_k < 20:
                    summary += " (Oversold 📉)\n"
                else:
                    summary += " (Neutral)\n"
            
            if indicators.get('roc') and len(indicators['roc']) > 0:
                latest_roc = indicators['roc'][-1]
                summary += f"- **ROC:** {latest_roc:.2f}%"
                if latest_roc > 0:
                    summary += " (Positive momentum 📈)\n"
                else:
                    summary += " (Negative momentum 📉)\n"
            
            if indicators.get('willr') and len(indicators['willr']) > 0:
                latest_willr = indicators['willr'][-1]
                summary += f"- **Williams %R:** {latest_willr:.2f}"
                if latest_willr > -20:
                    summary += " (Overbought ⚠️)\n"
                elif latest_willr < -80:
                    summary += " (Oversold 📉)\n"
                else:
                    summary += " (Neutral)\n"
            
            return {
                'summary': summary,
                'plots': plots,
                'symbol': symbol,
                'data_points': len(datetimes)
            }
            
        except Exception as e:
            print(f"Error in analyze_indicators_for_period: {e}")
            import traceback
            traceback.print_exc()
            return {
                'summary': f"Error analyzing {symbol}: {e}",
                'plots': {},
                'symbol': symbol,
                'data_points': 0
            }


# =====================================================================
# PATHWAY INTEGRATION UTILITIES
# =====================================================================

def create_user_facing_analysis_tools():
    """
    Create LangChain-compatible tools for user-facing analysis.
    These can be used by conversational agents to respond to user queries.
    """
    try:
        from langchain.tools import Tool
    except ImportError:
        try:
            from langchain_core.tools import Tool
        except ImportError:
            print("Warning: LangChain not installed. Skipping tool creation.")
            return []
    
    def analyze_rsi_tool(params_str: str) -> str:
        """
        Analyze RSI indicator for a stock.
        Input format: "symbol,start_time,end_time" or just "symbol"
        Example: "AAPL,2024-01-01 10:00,2024-01-01 11:00"
        """
        try:
            # This is a placeholder - in real implementation, would query Pathway table
            parts = params_str.split(',')
            symbol = parts[0].strip()
            
            return f"""RSI Analysis for {symbol}:
This tool would query the Pathway streaming table and generate RSI plots.
To implement: Connect to your Pathway table and call TechnicalTools.analyze_indicators_for_period()
with the appropriate time range."""
            
        except Exception as e:
            return f"Error: {e}"
    
    def analyze_macd_tool(params_str: str) -> str:
        """
        Analyze MACD indicator for a stock.
        Input format: "symbol,start_time,end_time" or just "symbol"
        """
        try:
            parts = params_str.split(',')
            symbol = parts[0].strip()
            
            return f"""MACD Analysis for {symbol}:
This tool would query the Pathway streaming table and generate MACD plots.
To implement: Connect to your Pathway table and call TechnicalTools.analyze_indicators_for_period()
with the appropriate time range."""
            
        except Exception as e:
            return f"Error: {e}"
    
    def analyze_all_indicators_tool(params_str: str) -> str:
        """
        Comprehensive analysis of all indicators for a stock.
        Input format: "symbol,minutes_back" 
        Example: "AAPL,15" for last 15 minutes
        """
        try:
            parts = params_str.split(',')
            symbol = parts[0].strip()
            minutes = int(parts[1].strip()) if len(parts) > 1 else 10
            
            return f"""Comprehensive Technical Analysis for {symbol} (Last {minutes} minutes):
This tool would query the Pathway streaming table and generate all indicator plots.
To implement: Connect to your Pathway table and call TechnicalTools.analyze_indicators_for_period()
with the appropriate time range.

Indicators included:
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Stochastic Oscillator
- Rate of Change (ROC)
- Williams %R
- Price Charts
- Candlestick Patterns
- Support/Resistance Levels"""
            
        except Exception as e:
            return f"Error: {e}"
    
    # Create LangChain tools
    tools = [
        Tool(
            name="analyze_rsi",
            func=analyze_rsi_tool,
            description="Analyze RSI (Relative Strength Index) for a stock symbol. "
                       "Input: 'SYMBOL' or 'SYMBOL,start_time,end_time'. "
                       "Returns RSI analysis with overbought/oversold signals."
        ),
        Tool(
            name="analyze_macd",
            func=analyze_macd_tool,
            description="Analyze MACD (Moving Average Convergence Divergence) for a stock. "
                       "Input: 'SYMBOL' or 'SYMBOL,start_time,end_time'. "
                       "Returns MACD analysis with bullish/bearish signals."
        ),
        Tool(
            name="analyze_all_indicators",
            func=analyze_all_indicators_tool,
            description="Comprehensive analysis of ALL technical indicators for a stock. "
                       "Input: 'SYMBOL,minutes_back' (e.g., 'AAPL,15' for last 15 minutes). "
                       "Returns complete technical analysis with all charts and signals."
        )
    ]
    
    return tools


# =====================================================================
# USER-FACING YFINANCE ANALYSIS TOOL (For LLM Agents)
# =====================================================================

def analyze_stock_indicators_yfinance(
    ticker: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    period: str = "7d",
    interval: str = "1m",
    indicators: Optional[List[str]] = None,
    save_dir: Optional[str] = None
) -> Dict:
    """
    User-facing tool to analyze stock indicators using yfinance data.
    Can be called by an LLM agent when user requests technical analysis.
    
    Args:
        ticker: Stock symbol (e.g., "AAPL", "TSLA")
        start_time: Start time for analysis window (optional, e.g., "2024-01-01 10:00")
        end_time: End time for analysis window (optional, e.g., "2024-01-01 11:00")
        period: Download period if start/end not specified (e.g., "7d", "1mo", "3mo")
        interval: Data interval (e.g., "1m", "5m", "15m", "1h", "1d")
        indicators: List of indicators to analyze (None = all indicators)
                   Options: ["rsi", "macd", "stochastic", "roc", "willr", "sma", "ema", "bb", "atr", "adx", "obv"]
        save_dir: Directory to save plots (optional)
    
    Returns:
        Dictionary with:
        - summary: Text summary of analysis
        - plots: Dictionary of base64 encoded plot images
        - indicators: Dictionary of calculated indicator values
        - metadata: Information about the analysis
    
    Example usage in LLM agent:
        # User: "Analyze RSI and MACD for Apple stock from 10 AM to 11 AM today"
        result = analyze_stock_indicators_yfinance(
            ticker="AAPL",
            start_time="2024-01-15 10:00",
            end_time="2024-01-15 11:00",
            interval="1m",
            indicators=["rsi", "macd"]
        )
    """
    try:
        # Step 1: Download data
        if not yfinance_available:
            return {
                "error": "yfinance is not installed. Please install it: pip install yfinance",
                "summary": "Error: yfinance not available",
                "plots": {},
                "indicators": {}
            }
        
        print(f"📊 Downloading {ticker} data (period={period}, interval={interval})...")
        df = download_ohlcv(ticker=ticker, period=period, interval=interval)
        
        if df.empty:
            return {
                "error": f"No data downloaded for {ticker}",
                "summary": f"Error: No data available for {ticker}",
                "plots": {},
                "indicators": {}
            }
        
        # Step 2: Filter by time window if specified
        if start_time or end_time:
            if start_time:
                start_dt = pd.to_datetime(start_time)
                df = df[df.index >= start_dt]
            if end_time:
                end_dt = pd.to_datetime(end_time)
                df = df[df.index <= end_dt]
            
            if df.empty:
                return {
                    "error": f"No data in specified time range for {ticker}",
                    "summary": f"Error: No data between {start_time} and {end_time}",
                    "plots": {},
                    "indicators": {}
                }
        
        print(f"✅ Downloaded {len(df)} data points from {df.index.min()} to {df.index.max()}")
        
        # Step 3: Calculate indicators using TA-Lib
        print(f"🔢 Calculating indicators...")
        try:
            inds = compute_indicators_talib(df)
            print(f"✅ Calculated {len(inds)} indicators")
        except Exception as e:
            return {
                "error": f"Error calculating indicators: {e}",
                "summary": f"Error calculating indicators: {e}",
                "plots": {},
                "indicators": {}
            }
        
        # Step 4: Filter indicators if specific ones requested
        if indicators:
            indicator_mapping = {
                "rsi": ["rsi_14"],
                "macd": ["macd", "macd_signal", "macd_hist"],
                "stochastic": ["stoch_k", "stoch_d"],
                "roc": ["roc_10"],
                "willr": ["willr_14"],
                "sma": ["sma_20", "sma_50"],
                "ema": ["ema_20", "ema_50"],
                "bb": ["bb_upper", "bb_middle", "bb_lower"],
                "atr": ["atr_14"],
                "adx": ["adx_14"],
                "obv": ["obv"]
            }
            
            filtered_inds = {}
            for ind_name in indicators:
                ind_keys = indicator_mapping.get(ind_name.lower(), [])
                for key in ind_keys:
                    if key in inds:
                        filtered_inds[key] = inds[key]
            inds = filtered_inds if filtered_inds else inds
        
        # Step 5: Generate plots
        print(f"📈 Generating plots...")
        plots = {}
        
        # Convert data for plotting
        datetimes = df.index.strftime("%Y-%m-%d %H:%M:%S").tolist()
        closes = df["Close"].tolist()
        
        # Determine which plots to generate based on available indicators
        plot_indicators = {
            'rsi': inds.get('rsi_14'),
            'macd': inds.get('macd'),
            'macd_signal': inds.get('macd_signal'),
            'macd_hist': inds.get('macd_hist'),
            'stoch_k': inds.get('stoch_k'),
            'stoch_d': inds.get('stoch_d'),
            'roc': inds.get('roc_10'),
            'willr': inds.get('willr_14')
        }
        
        # Convert Series to lists
        for key in plot_indicators:
            if plot_indicators[key] is not None:
                plot_indicators[key] = plot_indicators[key].tolist()
        
        # Generate all indicator plots
        if save_dir:
            os.makedirs(save_dir, exist_ok=True)
        
        plots = TechnicalTools.generate_all_indicator_plots(
            datetimes=datetimes,
            closes=closes,
            rsi=plot_indicators['rsi'],
            macd=plot_indicators['macd'],
            macd_signal=plot_indicators['macd_signal'],
            macd_hist=plot_indicators['macd_hist'],
            stoch_k=plot_indicators['stoch_k'],
            stoch_d=plot_indicators['stoch_d'],
            roc=plot_indicators['roc'],
            willr=plot_indicators['willr'],
            save_dir=save_dir
        )
        
        # Generate candlestick chart
        kline_tool = TechnicalTools.generate_kline_image()
        kline_result = kline_tool.invoke({
            'kline_data': {
                'Datetime': datetimes,
                'Open': df["Open"].tolist(),
                'High': df["High"].tolist(),
                'Low': df["Low"].tolist(),
                'Close': closes
            }
        })
        if kline_result.get('pattern_image'):
            plots['candlestick'] = kline_result['pattern_image']
        
        # Generate trend chart
        trend_tool = TechnicalTools.generate_trend_image()
        trend_result = trend_tool.invoke({
            'kline_data': {
                'Datetime': datetimes,
                'High': df["High"].tolist(),
                'Low': df["Low"].tolist(),
                'Close': closes
            }
        })
        if trend_result.get('trend_image'):
            plots['trend'] = trend_result['trend_image']
        
        print(f"✅ Generated {len(plots)} plots")
        
        # Step 6: Generate text summary
        summary = f"# Technical Analysis: {ticker}\n\n"
        summary += f"**Period:** {df.index.min()} to {df.index.max()}\n"
        summary += f"**Interval:** {interval}\n"
        summary += f"**Data Points:** {len(df)}\n\n"
        
        # Price summary
        latest_close = df["Close"].iloc[-1]
        first_close = df["Close"].iloc[0]
        price_change = latest_close - first_close
        price_change_pct = (price_change / first_close) * 100
        
        summary += f"## Price Summary\n\n"
        summary += f"- **Latest Close:** ${latest_close:.2f}\n"
        summary += f"- **Period Change:** ${price_change:.2f} ({price_change_pct:+.2f}%)\n"
        summary += f"- **High:** ${df['High'].max():.2f}\n"
        summary += f"- **Low:** ${df['Low'].min():.2f}\n\n"
        
        # Indicator summary
        summary += f"## Latest Indicator Values\n\n"
        
        if 'rsi_14' in inds and not inds['rsi_14'].isna().all():
            latest_rsi = inds['rsi_14'].iloc[-1]
            summary += f"### RSI (14)\n"
            summary += f"- **Value:** {latest_rsi:.2f}\n"
            if latest_rsi > 70:
                summary += f"- **Signal:** ⚠️ Overbought (>70)\n"
            elif latest_rsi < 30:
                summary += f"- **Signal:** 📉 Oversold (<30)\n"
            else:
                summary += f"- **Signal:** ✅ Neutral (30-70)\n"
            summary += "\n"
        
        if 'macd' in inds and not inds['macd'].isna().all():
            latest_macd = inds['macd'].iloc[-1]
            latest_signal = inds.get('macd_signal', pd.Series([0])).iloc[-1]
            latest_hist = inds.get('macd_hist', pd.Series([0])).iloc[-1]
            summary += f"### MACD\n"
            summary += f"- **MACD Line:** {latest_macd:.4f}\n"
            summary += f"- **Signal Line:** {latest_signal:.4f}\n"
            summary += f"- **Histogram:** {latest_hist:.4f}\n"
            if latest_macd > latest_signal:
                summary += f"- **Signal:** 📈 Bullish (MACD above signal)\n"
            else:
                summary += f"- **Signal:** 📉 Bearish (MACD below signal)\n"
            summary += "\n"
        
        if 'stoch_k' in inds and not inds['stoch_k'].isna().all():
            latest_k = inds['stoch_k'].iloc[-1]
            latest_d = inds.get('stoch_d', pd.Series([0])).iloc[-1]
            summary += f"### Stochastic Oscillator\n"
            summary += f"- **%K:** {latest_k:.2f}\n"
            summary += f"- **%D:** {latest_d:.2f}\n"
            if latest_k > 80:
                summary += f"- **Signal:** ⚠️ Overbought (>80)\n"
            elif latest_k < 20:
                summary += f"- **Signal:** 📉 Oversold (<20)\n"
            else:
                summary += f"- **Signal:** ✅ Neutral (20-80)\n"
            summary += "\n"
        
        if 'roc_10' in inds and not inds['roc_10'].isna().all():
            latest_roc = inds['roc_10'].iloc[-1]
            summary += f"### Rate of Change (10)\n"
            summary += f"- **Value:** {latest_roc:.2f}%\n"
            if latest_roc > 0:
                summary += f"- **Signal:** 📈 Positive momentum\n"
            else:
                summary += f"- **Signal:** 📉 Negative momentum\n"
            summary += "\n"
        
        if 'willr_14' in inds and not inds['willr_14'].isna().all():
            latest_willr = inds['willr_14'].iloc[-1]
            summary += f"### Williams %R (14)\n"
            summary += f"- **Value:** {latest_willr:.2f}\n"
            if latest_willr > -20:
                summary += f"- **Signal:** ⚠️ Overbought (>-20)\n"
            elif latest_willr < -80:
                summary += f"- **Signal:** 📉 Oversold (<-80)\n"
            else:
                summary += f"- **Signal:** ✅ Neutral (-20 to -80)\n"
            summary += "\n"
        
        # Moving averages
        if 'sma_20' in inds and 'sma_50' in inds:
            sma_20 = inds['sma_20'].iloc[-1]
            sma_50 = inds['sma_50'].iloc[-1]
            summary += f"### Moving Averages\n"
            summary += f"- **SMA(20):** ${sma_20:.2f}\n"
            summary += f"- **SMA(50):** ${sma_50:.2f}\n"
            if sma_20 > sma_50:
                summary += f"- **Signal:** 📈 Golden Cross pattern (bullish)\n"
            else:
                summary += f"- **Signal:** 📉 Death Cross pattern (bearish)\n"
            summary += "\n"
        
        # Return complete analysis
        return {
            "summary": summary,
            "plots": plots,
            "indicators": {k: v.tolist() if hasattr(v, 'tolist') else v for k, v in inds.items()},
            "metadata": {
                "ticker": ticker,
                "start_time": str(df.index.min()),
                "end_time": str(df.index.max()),
                "interval": interval,
                "data_points": len(df),
                "plots_generated": len(plots),
                "indicators_calculated": list(inds.keys())
            }
        }
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ Error in analyze_stock_indicators_yfinance: {e}")
        print(error_trace)
        return {
            "error": str(e),
            "error_trace": error_trace,
            "summary": f"Error analyzing {ticker}: {e}",
            "plots": {},
            "indicators": {}
        }


def create_yfinance_analysis_langchain_tool():
    """
    Create a LangChain tool for the yfinance analysis function.
    This can be used by conversational agents.
    """
    try:
        from langchain.tools import Tool
    except ImportError:
        try:
            from langchain_core.tools import Tool
        except ImportError:
            print("Warning: LangChain not installed. Cannot create LangChain tool.")
            return None
    
    def tool_wrapper(input_str: str) -> str:
        """
        Wrapper for LangChain tool.
        Expected input format: "TICKER|START_TIME|END_TIME|INTERVAL|INDICATORS"
        Example: "AAPL|2024-01-15 10:00|2024-01-15 11:00|1m|rsi,macd"
        Or simple: "AAPL" (uses defaults)
        """
        try:
            parts = input_str.split('|')
            ticker = parts[0].strip()
            start_time = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
            end_time = parts[2].strip() if len(parts) > 2 and parts[2].strip() else None
            interval = parts[3].strip() if len(parts) > 3 and parts[3].strip() else "1m"
            indicators = [i.strip() for i in parts[4].split(',')] if len(parts) > 4 and parts[4].strip() else None
            
            result = analyze_stock_indicators_yfinance(
                ticker=ticker,
                start_time=start_time,
                end_time=end_time,
                interval=interval,
                indicators=indicators
            )
            
            # Return summary and metadata (plots are too large for text)
            output = result.get('summary', 'No summary available')
            if 'metadata' in result:
                output += f"\n\n**Metadata:**\n"
                output += f"- Plots generated: {result['metadata'].get('plots_generated', 0)}\n"
                output += f"- Indicators: {', '.join(result['metadata'].get('indicators_calculated', []))}\n"
            
            if 'error' in result:
                output = f"Error: {result['error']}\n\n{output}"
            
            return output
            
        except Exception as e:
            return f"Error parsing input: {e}\n\nExpected format: TICKER|START_TIME|END_TIME|INTERVAL|INDICATORS\nExample: AAPL|2024-01-15 10:00|2024-01-15 11:00|1m|rsi,macd"
    
    tool = Tool(
        name="analyze_stock_technical_indicators",
        func=tool_wrapper,
        description=(
            "Analyze technical indicators for a stock using yfinance data. "
            "Input format: 'TICKER|START_TIME|END_TIME|INTERVAL|INDICATORS' "
            "(e.g., 'AAPL|2024-01-15 10:00|2024-01-15 11:00|1m|rsi,macd'). "
            "START_TIME and END_TIME are optional (omit for recent data). "
            "INTERVAL options: 1m, 5m, 15m, 1h, 1d. "
            "INDICATORS options: rsi, macd, stochastic, roc, willr, sma, ema, bb (omit for all). "
            "Returns comprehensive technical analysis with indicator values and signals."
        )
    )
    
    return tool


def query_pathway_table_for_analysis(
    pathway_table,
    symbol: str,
    lookback_minutes: int = 15,
    save_dir: str = None
) -> dict:
    """
    Query a Pathway table to get data for a specific symbol and time range,
    then generate comprehensive analysis.
    
    This is a helper function that can be integrated into your Pathway pipeline
    to provide on-demand analysis for user queries.
    
    Args:
        pathway_table: Pathway table with market data
        symbol: Stock symbol to analyze
        lookback_minutes: How many minutes back to analyze
        save_dir: Optional directory to save plot images
    
    Returns:
        Dictionary with analysis results and plots
    
    Example usage in Pathway UDF:
        @pw.udf
        def analyze_on_demand(symbol: str, minutes: int) -> pw.Json:
            # Get latest data from pathway table
            result = query_pathway_table_for_analysis(
                pathway_table=market_table,
                symbol=symbol,
                lookback_minutes=minutes
            )
            return pw.Json(result)
    """
    # This is a template - actual implementation depends on your Pathway table structure
    # You would need to:
    # 1. Filter the table by symbol
    # 2. Get data for the specified time range
    # 3. Extract OHLCV and indicator data
    # 4. Call TechnicalTools.analyze_indicators_for_period()
    
    return {
        "status": "Template function",
        "message": "Implement this by querying your specific Pathway table structure",
        "symbol": symbol,
        "lookback_minutes": lookback_minutes
    }


# =====================================================================
# EXAMPLE: PERIODIC PLOTTING FUNCTION
# =====================================================================

def setup_periodic_indicator_plotting(
    pathway_windowed_table,
    output_base_dir: str = "./indicator_plots"
):
    """
    Setup periodic plotting of indicators from a Pathway windowed table.
    
    This function subscribes to window updates and generates plots every X minutes
    for the last Y minutes of data (as specified in the windowing configuration).
    
    Args:
        pathway_windowed_table: Pathway table with windowed market data
                               (output from windowby() with indicators)
        output_base_dir: Base directory for saving plots
    
    Usage:
        # After creating your windowed table with indicators
        windowed_table = market_table.windowby(...).reduce(...)
        
        # Setup periodic plotting
        setup_periodic_indicator_plotting(windowed_table, "./plots")
        
        # This will automatically save plots to:
        # ./plots/{SYMBOL}/rsi_plot.png
        # ./plots/{SYMBOL}/macd_plot.png
        # etc.
    """
    import pathway as pw
    from pathlib import Path
    
    output_dir = Path(output_base_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    @pw.udf
    def generate_periodic_plots(
        symbol: str,
        kline_data: pw.Json,
        indicators: pw.Json,
        window_start,
        window_end
    ) -> pw.Json:
        """Generate plots for each window update."""
        try:
            symbol_dir = output_dir / symbol
            symbol_dir.mkdir(parents=True, exist_ok=True)
            
            kline_dict = kline_data.as_dict()
            indicators_dict = indicators.as_dict()
            
            # Generate all plots
            plots = TechnicalTools.generate_all_indicator_plots(
                datetimes=kline_dict.get('Datetime', []),
                closes=kline_dict.get('Close', []),
                rsi=indicators_dict.get('rsi', []),
                macd=indicators_dict.get('macd', []),
                macd_signal=indicators_dict.get('macd_signal', []),
                macd_hist=indicators_dict.get('macd_hist', []),
                stoch_k=indicators_dict.get('stoch_k', []),
                stoch_d=indicators_dict.get('stoch_d', []),
                roc=indicators_dict.get('roc', []),
                willr=indicators_dict.get('willr', []),
                save_dir=str(symbol_dir)
            )
            
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            
            # Save summary
            summary_file = symbol_dir / f"summary_{timestamp}.txt"
            with open(summary_file, 'w') as f:
                f.write(f"Symbol: {symbol}\n")
                f.write(f"Window: {window_start} to {window_end}\n")
                f.write(f"Plots generated: {len(plots)}\n")
                f.write(f"Timestamp: {timestamp}\n")
            
            print(f"✅ Generated {len(plots)} plots for {symbol} at {timestamp}")
            
            return pw.Json({
                "success": True,
                "plots_generated": len(plots),
                "timestamp": timestamp
            })
            
        except Exception as e:
            print(f"❌ Error generating periodic plots: {e}")
            return pw.Json({"success": False, "error": str(e)})
    
    # Apply the UDF to generate plots
    plotting_table = pathway_windowed_table.select(
        pw.this.symbol,
        pw.this.window_start,
        pw.this.window_end,
        pw.this.kline_data,
        pw.this.indicators,
        plot_result=generate_periodic_plots(
            pw.this.symbol,
            pw.this.kline_data,
            pw.this.indicators,
            pw.this.window_start,
            pw.this.window_end
        )
    )
    
    return plotting_table


# =====================================================================
# USAGE EXAMPLES
# =====================================================================

def example_user_facing_tool():
    """
    Example of using the user-facing yfinance analysis tool.
    This demonstrates how an LLM agent would call the tool.
    """
    print("\n" + "="*80)
    print("EXAMPLE: User-Facing Stock Analysis Tool")
    print("="*80 + "\n")
    
    # Example 1: Simple analysis - last 7 days of data
    print("Example 1: Analyze AAPL with all indicators (last 7 days)")
    print("-" * 60)
    result = analyze_stock_indicators_yfinance(
        ticker="AAPL",
        period="7d",
        interval="1h"
    )
    print(result.get('summary', 'No summary'))
    print(f"\nPlots generated: {len(result.get('plots', {}))}")
    print(f"Indicators calculated: {list(result.get('indicators', {}).keys())}")
    
    # Example 2: Specific indicators only
    print("\n" + "="*80)
    print("Example 2: Analyze TSLA with RSI and MACD only")
    print("-" * 60)
    result = analyze_stock_indicators_yfinance(
        ticker="TSLA",
        period="5d",
        interval="15m",
        indicators=["rsi", "macd"]
    )
    print(result.get('summary', 'No summary'))
    
    # Example 3: Time range analysis
    print("\n" + "="*80)
    print("Example 3: Analyze specific time window")
    print("-" * 60)
    from datetime import datetime, timedelta
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=2)
    
    result = analyze_stock_indicators_yfinance(
        ticker="MSFT",
        start_time=start_time.strftime("%Y-%m-%d %H:%M"),
        end_time=end_time.strftime("%Y-%m-%d %H:%M"),
        interval="5m",
        indicators=["rsi", "macd", "stochastic"]
    )
    print(result.get('summary', 'No summary'))
    
    print("\n" + "="*80)
    print("Examples completed!")
    print("="*80 + "\n")


def example_langchain_agent():
    """
    Example of using the tool with a LangChain agent.
    """
    print("\n" + "="*80)
    print("EXAMPLE: LangChain Agent with Stock Analysis Tool")
    print("="*80 + "\n")
    
    try:
        from langchain.agents import initialize_agent, AgentType
        from langchain_openai import ChatOpenAI
        
        # Create the tool
        tool = create_yfinance_analysis_langchain_tool()
        
        if tool is None:
            print("❌ Could not create LangChain tool (LangChain not installed)")
            return
        
        # Create agent with the tool
        llm = ChatOpenAI(temperature=0, model="gpt-4")
        agent = initialize_agent(
            tools=[tool],
            llm=llm,
            agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True
        )
        
        # Example queries
        queries = [
            "Analyze the RSI indicator for Apple stock",
            "Show me MACD analysis for Tesla",
            "What are the technical indicators saying about Microsoft stock?",
        ]
        
        for query in queries:
            print(f"\n{'='*60}")
            print(f"User Query: {query}")
            print('-'*60)
            response = agent.run(query)
            print(f"Agent Response:\n{response}")
        
        print("\n" + "="*80)
        print("LangChain agent examples completed!")
        print("="*80 + "\n")
        
    except ImportError as e:
        print(f"❌ Cannot run LangChain example: {e}")
        print("Install LangChain: pip install langchain langchain-openai")
    except Exception as e:
        print(f"❌ Error running LangChain example: {e}")


# Run examples only if executed directly
if __name__ == "__main__":
    print("="*80)
    print("TOOL CREATION MODULE - EXAMPLES")
    print("="*80)
    
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "user-tool":
            example_user_facing_tool()
        elif sys.argv[1] == "langchain":
            example_langchain_agent()
        elif sys.argv[1] == "original":
            print("\nRunning original example...")
            _run_example()
        else:
            print(f"Unknown example: {sys.argv[1]}")
            print("Options: user-tool, langchain, original")
    else:
        print("\nNo example specified. Available examples:")
        print("  python tool_creation.py user-tool   - Test user-facing analysis tool")
        print("  python tool_creation.py langchain   - Test LangChain agent integration")
        print("  python tool_creation.py original    - Run original example code")
        print("\nRunning original example by default...")
        _run_example()
