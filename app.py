# app.py — الصفحة الرئيسية الذكية (PHC) مع تنسيق Sidebar أخضر فاتح + نص داكن
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
from collections.abc import Mapping
import time

# ============ إعداد الصفحة والستايل ============
st.set_page_config(page_title="AMANY - لوحة التحكم", layout="wide", page_icon="🏠")

st.markdown(
    """
<style>
:root { 
  --green: #39ff14;
  --bg-dark: #0b1020;
  --bg-page: #4169E1;
  --card: #152240;
  --border: #5a7ff0;
  --white: #ffffff;
}
.stApp { background-color: var(--bg-page); }

/* ======== Sidebar theme (أخضر فاتح + نص داكن) ======== */
[data-testid="stSidebar"] {
  background: #b9f5c6 !important;            /* خلفية أخضر فاتح */
  border-right: 1px solid #2b5a8a !important;/* حد كحلي خفيف */
}
[data-testid="stSidebar"] * {
  color: #0a2540 !important;                 /* كحلي غامق لكل النصوص */
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] h4,
[data-testid="stSidebar"] h5,
[data-testid="stSidebar"] h6 {
  color: #0a2540 !important;
  font-weight: 800 !important;
}
[data-testid="stSidebar"] label {
  color: #0a2540 !important;
  font-weight: 700 !important;
}
[data-testid="stSidebar"] .stRadio div,
[data-testid="stSidebar"] .stCheckbox div {
  color: #0a2540 !important;
}
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] .stDateInput input,
[data-testid="stSidebar"] [data-baseweb="select"] input,
[data-testid="stSidebar"] [data-baseweb="select"] div[role="listbox"],
[data-testid="stSidebar"] [data-baseweb="select"] div[role="combobox"] {
  background: #e9ffef !important;            /* أخضر أفتح داخل الحقول */
  color: #0a2540 !important;                  /* نص كحلي غامق */
  border: 1px solid #185181 !important;       /* حد كحلي واضح */
  border-radius: 8px !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] svg {
  color: #0a2540 !important;                  /* سهم القائمة */
}
[data-testid="stSidebar"] button {
  background: #0a2540 !important;             /* زر كحلي */
  color: #ffffff !important;
  border: 1px solid #06223a !important;
  border-radius: 8px !important;
}
[data-testid="stSidebar"] button:hover {
  background: #071a2d !important;
}
[data-testid="stSidebar"] hr {
  border: none !important;
  border-top: 1px solid #2b5a8a !important;
  margin: 10px 0 !important;
}

/* ======== بقية التنسيق العام ======== */
h1,h2,h3,h4,h5,h6 { color: var(--green) !important; }
.amany-header { background: #2c4ba0; padding: 12px 10px; text-align: center; margin-bottom: 8px; border-radius: 10px; border: 1px solid var(--border); }
.amany-header-title { font-size: 44px; font-weight: 900; letter-spacing: 8px; margin: 0; color: var(--green); }
.amany-header-fullname { color: var(--white); font-size: 18px; margin-top: 6px; letter-spacing: 2px; text-transform: uppercase; }
.amany-header-sub { color: var(--white); font-size: 18px; margin-top: 6px; }
.clock-bar { text-align:center; margin: 6px 0 12px 0; }
.clock-time { font-size: 36px; font-weight: 900; color: var(--green); letter-spacing: 2px; }
.subtitle { color: var(--green) !important; font-weight: bold; text-align: center; margin: 12px 0; border-bottom: 2px solid var(--border); padding-bottom: 6px; }
.kpi-card { border-radius: 15px; background: var(--card); padding: 12px 10px; margin-bottom: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); text-align: center; min-height: 120px; border: 1px solid var(--border); display: flex; flex-direction: column; justify-content: center; }
.kpi-title { color: var(--green) !important; font-size: 16px; font-weight: 700; margin-bottom: 4px; letter-spacing: 0.5px; }
.kpi-value { color: var(--green) !important; font-size: 28px; font-weight: 900; }
</style>
""",
    unsafe_allow_html=True,
)

# ============ معرف ملف PHC ============
PHC_SPREADSHEET_ID = (
    st.secrets.get("sheets", {}).get("phc_spreadsheet_id", "")
    or st.text_input("PHC Spreadsheet ID", value="1ptbPIJ9Z0k92SFcXNqAeC61SXNpamCm-dXPb97cPT_4")
)

# ============ Backoff ============
def with_backoff(func, *args, **kwargs):
    for d in [0.5, 1, 2, 4, 8]:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if "429" in str(e) or "Quota" in str(e):
                time.sleep(d)
                continue
            raise
    raise RuntimeError("Backoff exceeded")

# ============ فتح الملف ============
@st.cache_resource(ttl=7200)
def get_spreadsheet(spreadsheet_id: str):
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    return with_backoff(client.open_by_key, spreadsheet_id)

# ============ قراءات ============
@st.cache_data(ttl=900)
def list_facility_sheets(spreadsheet_id: str):
    sh = get_spreadsheet(spreadsheet_id)
    titles = [ws.title for ws in with_backoff(sh.worksheets)]
    blacklist = {"config", "config!", "readme", "financial", "kpi", "test"}
    return [t for t in titles if t.strip().lower() not in blacklist]

@st.cache_data(ttl=900)
def get_all_values(spreadsheet_id: str, worksheet_name: str):
    sh = get_spreadsheet(spreadsheet_id)
    ws = with_backoff(sh.worksheet, worksheet_name.strip())
    return with_backoff(ws.get_all_values)

@st.cache_data(ttl=900)
def get_df_from_sheet(spreadsheet_id: str, worksheet_name: str) -> pd.DataFrame:
    vals = get_all_values(spreadsheet_id, worksheet_name)
    if not vals:
        return pd.DataFrame()
    header = [str(h).strip() for h in vals[0]]
    cols = pd.Series(header, dtype=str)
    for dup in cols[cols.duplicated()].unique():
        idxs = list(cols[cols == dup].index)
        for i, idx in enumerate(idxs):
            cols.iloc[idx] = dup if i == 0 else f"{dup}.{i}"
    return pd.DataFrame(vals[1:], columns=cols)

# ============ أدوات ============
CHART_COLORS = ["#39ff14", "#FF8C00", "#FF69B4", "#FFD700", "#00FFFF", "#DA70D6"]

def style_dataframe(df: pd.DataFrame):
    if df.empty:
        return df
    for col in df.columns:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="ignore")
    numeric_cols = df.select_dtypes(include=np.number).columns
    fmt = {col: "{:,.0f}" for col in numeric_cols}
    return df.style.format(fmt).set_properties(**{"font-size": "16px", "border": "1px solid #5a7ff0"})

def robust_parse_date(series: pd.Series) -> pd.Series:
    s = series.astype(object)
    def map_to_ts(v):
        try:
            if isinstance(v, Mapping):
                y = v.get("year") or v.get("Year")
                m = v.get("month") or v.get("Month")
                d = v.get("day") or v.get("Day") or 1
                if y and m:
                    return pd.Timestamp(int(y), int(m), int(d))
            return v
        except Exception:
            return v
    s = s.map(map_to_ts)
    dt = pd.to_datetime(s, errors="coerce", dayfirst=True, infer_datetime_format=True)
    mask_na = dt.isna()
    if mask_na.any():
        s2 = pd.Series(s[mask_na]).astype(str).str.strip()
        m1 = pd.to_datetime(s2, format="%m/%Y", errors="coerce")
        m2 = pd.to_datetime(s2, format="%m-%Y", errors="coerce")
        m3 = pd.to_datetime(s2, format="%Y-%m", errors="coerce")
        merged = m1.fillna(m2).fillna(m3)
        dt.loc[mask_na] = merged
    mask_na = dt.isna()
    if mask_na.any():
        def as_serial(v):
            try: return pd.to_datetime(float(v), unit="d", origin="1899-12-30")
            except Exception: return pd.NaT
        dt.loc[mask_na] = pd.Series(s[mask_na]).map(as_serial)
    return dt

def smart_insights(df: pd.DataFrame, date_col: str):
    numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
    if date_col in numeric_cols: numeric_cols.remove(date_col)
    if not numeric_cols: return {}
    df_sorted = df.sort_values(date_col)
    last_row = df_sorted.iloc[-1]
    window = df_sorted.tail(30) if len(df_sorted) > 30 else df_sorted
    avg = window[numeric_cols].mean()
    change_pct = ((last_row[numeric_cols] - avg) / avg.replace(0, np.nan) * 100).fillna(0)
    if change_pct.empty: return {}
    return {
        "best": (change_pct.idxmax(), change_pct.max()),
        "worst": (change_pct.idxmin(), change_pct.min()),
        "alerts": change_pct[abs(change_pct) >= 20].sort_values(ascending=False)
    }

def apply_chart_layout(fig, title_txt: str = "", height: int = 600):
    fig.update_layout(
        title=title_txt,
        height=height,
        paper_bgcolor="#0b1020",
        plot_bgcolor="#0b1020",
        font=dict(color="#ffffff", size=16),
        title_font=dict(size=22, color="#39ff14"),
        legend=dict(font=dict(size=14), bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(gridcolor="#233", zerolinecolor="#355", title_font=dict(size=18, color="#ffffff"), tickfont=dict(size=14, color="#ffffff")),
        yaxis=dict(gridcolor="#233", zerolinecolor="#355", title_font=dict(size=18, color="#ffffff"), tickfont=dict(size=14, color="#ffffff")),
        margin=dict(l=40, r=20, t=60, b=50),
    )
    return fig

def display_trend_analysis(df: pd.DataFrame, date_col: str, service_col: str):
    data = df[[date_col, service_col]].copy()
    data = data.dropna(subset=[date_col])
    if data.empty or len(data) < 2:
        st.info("لا توجد بيانات كافية لعرض خط الاتجاه.")
        return
    data["day_num"] = (data[date_col] - data[date_col].min()).dt.days
    y = pd.to_numeric(data[service_col], errors="coerce").fillna(0)
    if y.nunique() == 0:
        st.info("لا توجد تغييرات كافية لعرض الاتجاه.")
        return
    z = np.polyfit(data["day_num"], y, 1)
    p = np.poly1d(z)
    trend = p(data["day_num"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data[date_col], y=y, mode="lines+markers", name="Actual", line=dict(color=CHART_COLORS[0], width=3)))
    fig.add_trace(go.Scatter(x=data[date_col], y=trend, mode="lines", name="Trend", line=dict(color=CHART_COLORS[1], dash="dash", width=3)))
    apply_chart_layout(fig, f"Trend: {service_col}", height=620)
    st.plotly_chart(fig, use_container_width=True)

# ============ فلتر تاريخ موحد ============
def get_date_filter_keys(prefix: str):
    return f"{prefix}_range", f"{prefix}_start", f"{prefix}_end"

def apply_date_filter(df: pd.DataFrame, date_col: str, prefix: str):
    key_range, key_start, key_end = get_date_filter_keys(prefix)
    st.sidebar.header("فلتر التواريخ")
    time_range = st.sidebar.selectbox(
        "اختر النطاق الزمني للعرض:",
        ("آخر 7 أيام", "آخر 30 يومًا", "هذا الشهر", "كل الوقت", "نطاق مخصص"),
        key=key_range
    )
    today = datetime.now()
    if time_range == "آخر 7 أيام":
        return df[df[date_col] >= (today - timedelta(days=7))]
    elif time_range == "آخر 30 يومًا":
        return df[df[date_col] >= (today - timedelta(days=30))]
    elif time_range == "هذا الشهر":
        return df[df[date_col].dt.month == today.month]
    elif time_range == "نطاق مخصص":
        start_date = st.sidebar.date_input("من تاريخ", df[date_col].min().date(), key=key_start)
        end_date = st.sidebar.date_input("إلى تاريخ", df[date_col].max().date(), key=key_end)
        return df[(df[date_col].dt.date >= start_date) & (df[date_col].dt.date <= end_date)]
    else:
        return df

# ============ عرض منشأة ============
def display_facility_dashboard(df: pd.DataFrame, facility_name: str, range_prefix: str):
    if df.empty or len(df.columns) == 0:
        st.info("لا توجد بيانات لعرضها.")
        return
    date_col = df.columns[0]
    df = df.copy()
    df[date_col] = robust_parse_date(df[date_col])
    df = df.dropna(subset=[date_col])
    if df.empty or df[date_col].nunique() < 2:
        st.markdown(f"الورقة '{facility_name}' لا تحتوي تاريخًا صالحًا كافياً. عرض جدول منسّق.")
        st.dataframe(style_dataframe(df.copy()), use_container_width=True, height=520)
        return
    for col in df.columns:
        if col != date_col:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce").fillna(0)

    st.markdown(f'<div class="subtitle">لوحة المنشأة: {facility_name}</div>', unsafe_allow_html=True)

    df_filtered = apply_date_filter(df, date_col, prefix=range_prefix)
    if df_filtered.empty:
        st.warning("لا توجد بيانات في النطاق الزمني المحدد.")
        return

    # ملخص ذكي
    ins = smart_insights(df_filtered, date_col)
    if ins:
        st.markdown('<div class="subtitle">ملخص ذكي</div>', unsafe_allow_html=True)
        if ins.get("best"): st.success(f"أعلى تحسن: {ins['best'][0]} ({ins['best'][1]:+.1f}%)")
        if ins.get("worst"): st.error(f"أكبر تراجع: {ins['worst']} ({ins['worst'][1]:+.1f}%)")
        alerts = ins.get("alerts")
        if isinstance(alerts, pd.Series) and not alerts.empty:
            st.info("تنبيهات ±20%:")
            for k, v in alerts.items():
                arrow = "↑" if v > 0 else "↓"
                st.write(f"- {k}: {v:+.1f}% {arrow}")

    # الملخص الإجمالي
    st.markdown('<div class="subtitle">الملخص الإجمالي للخدمات</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    clinic_cols = [col for col in df_filtered.columns[1:7] if col in df_filtered.columns]
    dental_cols = [col for col in df_filtered.columns[8:15] if col in df_filtered.columns]

    with c1:
        st.subheader("تردد العيادات")
        clinic_totals = df_filtered[clinic_cols].sum(numeric_only=True)
        if len(clinic_totals):
            fig_pie = px.pie(values=clinic_totals.values, names=clinic_totals.index, hole=0.3, color_discrete_sequence=CHART_COLORS)
            fig_pie.update_traces(textposition="outside", textinfo="percent+value", textfont=dict(color="#ffffff", size=18, family="Arial, bold"),
                                  pull=[0.03]*len(clinic_totals), marker=dict(line=dict(color="#ffffff", width=2)))
            apply_chart_layout(fig_pie, "نسبة تردد العيادات", height=580)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("لا توجد أعمدة تردد العيادات (الأعمدة 2 إلى 7).")

    with c2:
        st.subheader("خدمات الأسنان")
        dental_totals = df_filtered[dental_cols].sum(numeric_only=True)
        if len(dental_totals):
            fig_bar = px.bar(y=dental_totals.index, x=dental_totals.values, orientation="h",
                             labels={"y": "الخدمة", "x": "الإجمالي"}, text_auto=True, color_discrete_sequence=CHART_COLORS)
            fig_bar.update_traces(textfont=dict(size=16, color="#ffffff"), marker_line_width=1.2, marker_line_color="#888")
            apply_chart_layout(fig_bar, "إجمالي خدمات الأسنان", height=580)
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("لا توجد أعمدة خدمات الأسنان (الأعمدة 9 إلى 15).")

    # مؤشرات الأداء (Top-N)
    st.markdown('<div class="subtitle">مؤشرات الأداء الرئيسية</div>', unsafe_allow_html=True)
    pharmacy_cols = [col for col in df_filtered.columns[15:17] if col in df_filtered.columns]
    all_chart_cols = clinic_cols + dental_cols + pharmacy_cols
    kpi_card_cols = [col for col in df_filtered.columns if col not in all_chart_cols and col != date_col]
    all_kpi_cols = pharmacy_cols + kpi_card_cols
    if all_kpi_cols:
        top_n = st.slider("عدد الكروت المعروضة (Top-N):", 4, max(4, len(all_kpi_cols)), value=min(8, len(all_kpi_cols)), key=f"topn_{range_prefix}")
        totals = pd.Series({k: pd.to_numeric(df_filtered[k], errors="coerce").sum() for k in all_kpi_cols}).sort_values(ascending=False).head(top_n)
        num_cols = min(len(totals), 4)
        grid = st.columns(num_cols if num_cols else 1)
        for i, (kpi, total) in enumerate(totals.items()):
            with grid[i % max(1, num_cols)]:
                st.markdown(f'<div class="kpi-card"><div class="kpi-title">{kpi}</div><div class="kpi-value">{int(total):,}</div></div>', unsafe_allow_html=True)

    # مقارنة/Trend داخل المنشأة
    st.markdown('<div class="subtitle">تحليل ومقارنة أداء الخدمات</div>', unsafe_allow_html=True)
    all_services = df_filtered.columns.drop(date_col)
    selected = st.multiselect("اختر خدمة أو أكثر لعرضها:", options=all_services, key=f"multi_{range_prefix}")
    chart_kind_local = st.radio("نوع الرسم:", ["Line", "Bar"], key=f"kind_{range_prefix}", horizontal=True)
    if selected:
        if len(selected) > 1:
            if chart_kind_local == "Line":
                fig_line = px.line(df_filtered, x=date_col, y=selected, markers=True, title="مقارنة أداء الخدمات المختارة", color_discrete_sequence=CHART_COLORS)
                apply_chart_layout(fig_line, height=620)
                st.plotly_chart(fig_line, use_container_width=True)
            else:
                fig_bar2 = px.bar(df_filtered, x=date_col, y=selected, barmode="group", title="مقارنة أداء الخدمات المختارة", color_discrete_sequence=CHART_COLORS)
                apply_chart_layout(fig_bar2, height=620)
                st.plotly_chart(fig_bar2, use_container_width=True)
        else:
            display_trend_analysis(df_filtered, date_col, selected[0])

    st.markdown('<div class="subtitle">عرض البيانات التفصيلية</div>', unsafe_allow_html=True)
    st.dataframe(style_dataframe(df_filtered.copy()), use_container_width=True, height=540)

# ============ مقارنة منشآت ============
def compare_facilities():
    st.subheader("مقارنة منشآت")
    try:
        ws_list = list_facility_sheets(PHC_SPREADSHEET_ID)
    except Exception as e:
        st.error(f"تعذر قراءة قائمة الأوراق: {e}")
        return
    if not ws_list:
        st.info("لا توجد منشآت متاحة.")
        return

    sel_facilities = st.multiselect("اختر منشآت:", ws_list, key="fac_multi")
    chart_kind = st.radio("نوع الرسم:", ["Line", "Bar"], horizontal=True, index=0, key="fac_kind")
    if not sel_facilities:
        return

    # إعداد وتحويل
    data_map = {}
    common_cols = None
    for w in sel_facilities:
        dfw = get_df_from_sheet(PHC_SPREADSHEET_ID, w).copy()
        if dfw.empty or len(dfw.columns) < 2:
            continue
        dcol = dfw.columns[0]
        dfw[dcol] = robust_parse_date(dfw[dcol])
        dfw = dfw.dropna(subset=[dcol]).sort_values(dcol)
        for c in dfw.columns:
            if c != dcol:
                dfw[c] = pd.to_numeric(dfw[c].astype(str).str.replace(",", ""), errors="coerce").fillna(0)
        data_map[w] = (dcol, dfw)
        cols = set([c for c in dfw.columns if c != dcol])
        common_cols = cols if common_cols is None else (common_cols & cols)

    if not data_map:
        st.info("لا توجد بيانات صالحة للمنشآت المختارة.")
        return
    if not common_cols:
        st.info("لا يوجد مؤشر مشترك بين كل المنشآت المختارة.")
        return

    kpi = st.selectbox("المؤشر:", sorted(list(common_cols)), key="fac_kpi")
    if not kpi:
        return

    # فلتر تاريخ موحّد للمقارنة (مصّحح)
    all_dates = []
    for _, (dc, dfw) in data_map.items():
        all_dates.append(dfw[[dc]].rename(columns={dc: "Date"}))
    union_dates = pd.concat(all_dates, ignore_index=True).dropna()
    if union_dates.empty:
        st.info("لا توجد تواريخ متاحة للمقارنة.")
        return

    min_dt = pd.to_datetime(union_dates["Date"].min()).normalize()
    max_dt = pd.to_datetime(union_dates["Date"].max()).normalize()

    df_range = pd.DataFrame({"Date": pd.date_range(min_dt, max_dt, freq="D")})
    df_range_filtered = apply_date_filter(df_range, "Date", prefix="cmp")
    if df_range_filtered.empty:
        start_sel, end_sel = min_dt, max_dt
    else:
        start_sel = pd.to_datetime(df_range_filtered["Date"].min()).normalize()
        end_sel   = pd.to_datetime(df_range_filtered["Date"].max()).normalize()

    fig = go.Figure()
    for w, (dcol, dfw) in data_map.items():
        seg = dfw[(dfw[dcol] >= start_sel) & (dfw[dcol] <= end_sel)].copy()
        if seg.empty or kpi not in seg.columns:
            continue
        seg[dcol] = pd.to_datetime(seg[dcol]).dt.normalize()
        if chart_kind == "Line":
            fig.add_trace(go.Scatter(x=seg[dcol], y=seg[kpi], mode="lines+markers", name=w, line=dict(width=3)))
        else:
            fig.add_trace(go.Bar(x=seg[dcol], y=seg[kpi], name=w, marker_line_width=1.2, marker_line_color="#888"))

    apply_chart_layout(fig, f"{kpi} عبر منشآت", height=650)
    days_span = (end_sel - start_sel).days
    if days_span > 90:
        fig.update_xaxes(tickformat="%Y-%m", dtick="M1")
    else:
        fig.update_xaxes(tickformat="%Y-%m-%d", dtick="D1")
    st.plotly_chart(fig, use_container_width=True)

# ============ الواجهة ============
def main():
    st.markdown(
        """
<div class="amany-header">
  <div class="amany-header-title">AMANY</div>
  <div class="amany-header-fullname">Advanced Medical Analytics Networking Yielding</div>
  <div class="amany-header-sub">منصة التحليل المتقدم للرعاية الصحية الأولية - فرع جنوب سيناء</div>
</div>
""",
        unsafe_allow_html=True,
    )
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.markdown(f'<div class="clock-bar"><span class="clock-time">{now_str}</span></div>', unsafe_allow_html=True)

    st.sidebar.title("عرض البيانات")
    app_mode = st.sidebar.radio("اختر العرض:", ("الإجماليات", "حسب المنشأة", "مقارنة منشآت"), key="mode")

    if app_mode == "الإجماليات":
        st.header("لوحة التحكم الرئيسية (الإجماليات)")
        df_phc = get_df_from_sheet(PHC_SPREADSHEET_ID, "PHC Dashboard")
        if not df_phc.empty:
            display_facility_dashboard(df_phc, "PHC Dashboard", range_prefix="main")
        else:
            st.info("لم يتم العثور على بيانات صالحة في PHC Dashboard.")
    elif app_mode == "حسب المنشأة":
        st.header("عرض حسب المنشأة")
        try:
            ws_list = list_facility_sheets(PHC_SPREADSHEET_ID)
        except Exception as e:
            st.error(f"تعذر قراءة قائمة الأوراق: {e}")
            return
        if not ws_list:
            st.info("لا توجد منشآت متاحة.")
            return
        selected_ws = st.selectbox("اختر منشأة:", ws_list, index=0, key="fac_sel")
        df_sel = get_df_from_sheet(PHC_SPREADSHEET_ID, selected_ws)
        if df_sel.empty:
            st.info("لا توجد بيانات في الورقة المحددة.")
            return
        display_facility_dashboard(df_sel, selected_ws, range_prefix="fac")
    else:
        compare_facilities()

if __name__ == "__main__":
    main()
