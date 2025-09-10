# ============================================================
# EDA Chancado — FUSIÓN (Streamlit Cloud + PPTX 16:9)
# ============================================================
import io, os, re
import numpy as np
import pandas as pd
import streamlit as st
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.ticker import StrMethodFormatter
from matplotlib.dates import DateFormatter, MonthLocator
from matplotlib import colors as mcolors
import statsmodels.api as sm
from statsmodels.formula.api import ols
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

st.set_page_config(page_title="EDA Chancado — FUSIÓN", layout="wide")

# ---------- Estilo ----------
PALETTE = ["#328BA1", "#0B5563", "#00AFAA", "#66C7C7", "#BFD8D2", "#003B5C", "#7FB7BE"]
custom_palette = PALETTE[:5]
sns.set_theme(style="whitegrid")

def fmt_thousands(x):
    try:
        return f"{int(round(x)):,}".replace(",", ".")
    except Exception:
        return ""

# ---------- Utilidades de limpieza ----------
def _normalize_colname(c: str) -> str:
    return (c.strip().lower()
            .replace("/", "_")
            .replace(" ", "_")
            .replace("__","_"))

EXPECTED = {
    "Fecha": ["fecha","date"],
    "mineral_procesado_real_t": ["mineral_procesado_real_t","mineral_real_t","ton_real","tons_real"],
    "rendimiento_real_tph": ["rendimiento_real_tph","tph_real","real_tph"],
    "tiempo_operativo_real_h/dia": ["tiempo_operativo_real_h_dia","tiempo_operativo_real_h/dia","horas_reales","h_real"],
    "mineral_procesado_plan_t": ["mineral_procesado_plan_t","mineral_plan_t","ton_plan","tons_plan"],
    "rendimiento_plan_tph": ["rendimiento_plan_tph","tph_plan","plan_tph"],
    "tiempo_operativo_plan_h/dia": ["tiempo_operativo_plan_h_dia","tiempo_operativo_plan_h/dia","horas_plan","h_plan"]
}

def _map_columns(df_cols):
    norm_map = {_normalize_colname(c): c for c in df_cols}
    mapping = {}
    for std, aliases in EXPECTED.items():
        found = None
        for a in aliases + [_normalize_colname(std)]:
            if a in norm_map:
                found = norm_map[a]; break
        mapping[std] = found
    missing = [k for k,v in mapping.items() if v is None]
    if missing:
        raise ValueError(f"Faltan columnas requeridas en el CSV: {missing}")
    return mapping

def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str)
              .str.replace("\u00a0","", regex=False)
              .str.replace(".", "", regex=False)
              .str.replace(",", "", regex=False)
              .str.strip(),
        errors="coerce"
    )

def _parse_fecha_mmddyyyy_with_report(s: pd.Series):
    raw = s.astype(str).str.strip()
    pat_exact = re.compile(r"^\d{2}-\d{2}\.\d{4}$")
    exact_count = int(raw.apply(lambda x: bool(pat_exact.match(x))).sum())

    s_norm = (raw
              .str.replace("\u00a0","", regex=False)
              .str.replace("/", "-", regex=False)
              .str.replace(".", "-", regex=False))

    fechas_strict = pd.to_datetime(s_norm, format="%m-%d-%Y", errors="coerce")
    strict_ok = fechas_strict.notna()
    fechas = fechas_strict.copy()

    if (~strict_ok).any():
        fechas_fallback = pd.to_datetime(s_norm[~strict_ok], errors="coerce", infer_datetime_format=True)
        fechas.loc[~strict_ok] = fechas_fallback

    report = {
        "total": len(s),
        "exact_mm-dd.yyyy": exact_count,
        "parsed": int(fechas.notna().sum()),
        "invalid": int(fechas.isna().sum())
    }
    st.caption(f"🗓️ Validación fechas: {report}")
    if report["invalid"] > 0:
        bad = list(fechas[fechas.isna()].index)[:5]
        for i in bad:
            st.caption(f"  • inválida: '{raw.iloc[i]}' → NaT")
    return fechas

def load_dataset_v2(df_in: pd.DataFrame) -> pd.DataFrame:
    mapping = _map_columns(df_in.columns)
    out = pd.DataFrame()
    out["Fecha"] = _parse_fecha_mmddyyyy_with_report(df_in[mapping["Fecha"]])
    for k in [k for k in EXPECTED.keys() if k!="Fecha"]:
        out[k] = _to_num(df_in[mapping[k]])
    out = out.dropna(subset=["Fecha"]).sort_values("Fecha").reset_index(drop=True)
    out["mes"] = out["Fecha"].dt.to_period("M").astype(str)
    out["mes_fecha"] = pd.to_datetime(out["Fecha"].dt.to_period("M").astype(str) + "-01", errors="coerce")
    return out

# ---------- Sidebar ----------
st.sidebar.title("EDA Chancado — FUSIÓN")
uploaded = st.sidebar.file_uploader("📂 Sube tu CSV", type=["csv","txt"])
sep_semicolon = st.sidebar.checkbox("Separador ';' (alternativo)", value=False)

# ---------- Carga ----------
df = None
if uploaded is not None:
    try:
        if sep_semicolon:
            raw = pd.read_csv(uploaded, sep=";")
        else:
            raw = pd.read_csv(uploaded)
        df = load_dataset_v2(raw)
        st.success(f"✔ Dataset: {len(df):,} filas — {df['Fecha'].min().date()} → {df['Fecha'].max().date()}")
    except Exception as e:
        st.error(f"Error al cargar/parsear: {e}")

st.markdown("---")

if df is None:
    st.info("Sube un CSV para iniciar el análisis.")
    st.stop()

# ================= KPIs & Percentiles =================
kpis = {
    "Mineral real (t)": df["mineral_procesado_real_t"].sum(),
    "Mineral plan (t)": df["mineral_procesado_plan_t"].sum(),
    "Δ Mineral (t)": df["mineral_procesado_real_t"].sum() - df["mineral_procesado_plan_t"].sum(),
    "TPH real prom": df["rendimiento_real_tph"].mean(),
    "TPH plan prom": df["rendimiento_plan_tph"].mean(),
    "Horas reales prom": df["tiempo_operativo_real_h/dia"].mean(),
    "Horas plan prom": df["tiempo_operativo_plan_h/dia"].mean(),
}
kpi_df = pd.DataFrame({"KPI": list(kpis.keys()), "Valor": list(kpis.values())})

c1, c2 = st.columns([1,1])
with c1:
    st.subheader("KPIs")
    st.dataframe(kpi_df.style.format({"Valor":"{:,.2f}"}), use_container_width=True)
with c2:
    st.subheader("Percentiles")
    qs = [0.05,0.25,0.50,0.75,0.95]
    percentiles_df = pd.DataFrame({
        "TPH real": df["rendimiento_real_tph"].quantile(qs).values,
        "Horas reales": df["tiempo_operativo_real_h/dia"].quantile(qs).values
    }, index=[f"P{int(q*100)}" for q in qs])
    st.dataframe(percentiles_df.style.format("{:,.2f}"), use_container_width=True)

st.markdown("---")

# ================= 1) Serie temporal =================
def fig_serie_temporal(d):
    fig, axes = plt.subplots(1, 2, figsize=(16, 5), sharex=False)
    # TPH
    sns.lineplot(data=d, x="Fecha", y="rendimiento_real_tph", ax=axes[0],
                 color=custom_palette[0], label="TPH real")
    axes[0].axhline(d["rendimiento_plan_tph"].median(), color="grey", linestyle="--", label="Plan (mediana)")
    axes[0].set_title("Evolución diaria TPH")
    axes[0].yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    axes[0].legend(loc="upper left"); axes[0].grid(True, alpha=0.25)

    # Horas
    sns.lineplot(data=d, x="Fecha", y="tiempo_operativo_real_h/dia", ax=axes[1],
                 color=custom_palette[2], label="Horas reales")
    axes[1].axhline(d["tiempo_operativo_plan_h/dia"].median(), color="grey", linestyle="--", label="Plan (mediana)")
    axes[1].set_title("Evolución diaria Horas")
    axes[1].yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    axes[1].legend(loc="upper left"); axes[1].grid(True, alpha=0.25)

    for ax in axes:
        ax.xaxis.set_major_locator(MonthLocator(interval=1))
        ax.xaxis.set_major_formatter(DateFormatter("%b-%y"))
        for label in ax.get_xticklabels():
            label.set_rotation(0)
    plt.tight_layout()
    return fig

st.subheader("Serie temporal — TPH y Horas")
st.pyplot(fig_serie_temporal(df), use_container_width=True)

# ================= 2) Boxplots mensuales =================
def fig_boxplots(d):
    fig, axes = plt.subplots(1, 2, figsize=(16, 5), sharex=True)
    sns.boxplot(data=d, x="mes", y="rendimiento_real_tph", ax=axes[0], palette=custom_palette)
    axes[0].set_title("Distribución mensual TPH")
    axes[0].yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    axes[0].tick_params(axis="x", rotation=45)
    sns.boxplot(data=d, x="mes", y="tiempo_operativo_real_h/dia", ax=axes[1], palette=custom_palette)
    axes[1].set_title("Distribución mensual Horas")
    axes[1].yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    axes[1].tick_params(axis="x", rotation=45)
    plt.tight_layout()
    return fig

st.subheader("Distribución mensual — TPH y Horas")
st.pyplot(fig_boxplots(df), use_container_width=True)

# ================= 3) CV mensual =================
cv = df.groupby("mes", as_index=False).agg({
    "rendimiento_real_tph": lambda x: np.std(x, ddof=1)/np.mean(x) if np.mean(x) > 0 else np.nan,
    "tiempo_operativo_real_h/dia": lambda x: np.std(x, ddof=1)/np.mean(x) if np.mean(x) > 0 else np.nan
})
def fig_cv(cv):
    fig, ax = plt.subplots(figsize=(12, 4.5))
    sns.lineplot(data=cv, x="mes", y="rendimiento_real_tph", marker="o", ax=ax,
                 label="CV TPH", color=custom_palette[0])
    sns.lineplot(data=cv, x="mes", y="tiempo_operativo_real_h/dia", marker="o", ax=ax,
                 label="CV Horas", color=custom_palette[2])
    ax.set_title("Coeficiente de variación mensual")
    ax.legend(loc="upper left")
    plt.xticks(rotation=45)
    plt.tight_layout()
    return fig

st.subheader("Variabilidad (CV)")
st.pyplot(fig_cv(cv), use_container_width=True)

# ================= 4) Brechas promedio vs plan =================
df["delta_tph"] = df["rendimiento_real_tph"] - df["rendimiento_plan_tph"]
df["delta_horas"] = df["tiempo_operativo_real_h/dia"] - df["tiempo_operativo_plan_h/dia"]
promedios = df[["delta_tph", "delta_horas"]].mean()

def fig_brechas(promedios):
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.5))
    sns.barplot(x=["Δ TPH"], y=[promedios["delta_tph"]], ax=axes[0], color=custom_palette[0])
    axes[0].set_title("Brecha promedio TPH vs Plan")
    axes[0].bar_label(axes[0].containers[0], fmt="%.0f", label_type="center", color="white")
    axes[0].yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    axes[0].grid(axis="y", alpha=0.25)

    sns.barplot(x=["Δ Horas"], y=[promedios["delta_horas"]], ax=axes[1], color=custom_palette[2])
    axes[1].set_title("Brecha promedio Horas vs Plan")
    axes[1].bar_label(axes[1].containers[0], fmt="%.0f", label_type="center", color="white")
    axes[1].yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    axes[1].grid(axis="y", alpha=0.25)
    plt.tight_layout()
    return fig

st.subheader("Brechas promedio vs plan")
st.pyplot(fig_brechas(promedios), use_container_width=True)

# ================= 5) ANOVA por mes =================
st.subheader("ANOVA por mes")
model_tph = ols("rendimiento_real_tph ~ C(mes)", data=df).fit()
anova_tph = sm.stats.anova_lm(model_tph, typ=2)
model_h = ols("Q('tiempo_operativo_real_h/dia') ~ C(mes)", data=df).fit()
anova_h = sm.stats.anova_lm(model_h, typ=2)
c1, c2 = st.columns(2)
with c1:
    st.markdown("**TPH**")
    st.dataframe(anova_tph.round(4), use_container_width=True)
with c2:
    st.markdown("**Horas/día**")
    st.dataframe(anova_h.round(4), use_container_width=True)

# ================= 6) Sensibilidad =================
st.subheader("Sensibilidad")

# 6a) Iso-%
mean_tph = float(df["rendimiento_real_tph"].mean())
mean_h   = float(df["tiempo_operativo_real_h/dia"].mean())
baseline_iso = mean_tph * mean_h if (mean_tph > 0 and mean_h > 0) else np.nan

delta_pct = np.array([0.01, 0.02, 0.03, 0.05, 0.07, 0.10])  # 1%..10%
grid = []
for dH in delta_pct:
    for dT in delta_pct:
        h_new   = min(mean_h * (1 + dH), 24.0)
        tph_new = mean_tph * (1 + dT)
        tons_new = h_new * tph_new
        grid.append({"delta_horas_pct": dH, "delta_tph_pct": dT,
                     "tons_pct": ((tons_new / baseline_iso - 1.0) * 100) if baseline_iso and baseline_iso > 0 else np.nan})
grid = pd.DataFrame(grid)
pv = grid.pivot(index="delta_tph_pct", columns="delta_horas_pct", values="tons_pct")
cmap = mcolors.LinearSegmentedColormap.from_list("afines_heat", ["#E0F7FA", "#00AFAA", "#0B5563"])
fig_iso, ax = plt.subplots(figsize=(10, 6))
sns.heatmap(pv, annot=True, fmt=".1f", cmap=cmap, cbar_kws={"label": "Δ Tons (%)"}, annot_kws={"fontsize": 11}, ax=ax)
ax.set_title("Iso-%: %ΔTPH vs %ΔHoras → %ΔTons"); ax.set_xlabel("% Δ Horas"); ax.set_ylabel("% Δ TPH")
xt = [f"{v*100:.0f}%" for v in pv.columns]; yt = [f"{v*100:.0f}%" for v in pv.index]
ax.set_xticks(np.arange(len(xt)) + 0.5, xt); ax.set_yticks(np.arange(len(yt)) + 0.5, yt)
ax.tick_params(axis="x", rotation=0); ax.tick_params(axis="y", rotation=0)
plt.tight_layout()
st.pyplot(fig_iso, use_container_width=True)

# 6b) Equiparada
pct = np.arange(-10, 21, 2)     # -10% .. +20%
dh  = np.arange(-2.0, 4.0+1e-9, 0.5)  # -2h .. +4h
sum_TPH = df["rendimiento_real_tph"].sum()
sum_TPH_H = (df["rendimiento_real_tph"] * df["tiempo_operativo_real_h/dia"]).sum()
dh_equiv_1pct = 0.01 * (sum_TPH_H / max(sum_TPH, 1e-9))
base_series = (df["rendimiento_real_tph"] * df["tiempo_operativo_real_h/dia"]).sum()
gain = np.zeros((len(dh), len(pct)))
for i, d in enumerate(dh):
    for j, p in enumerate(pct):
        out = ((df["rendimiento_real_tph"]*(1+p/100.0)) * (df["tiempo_operativo_real_h/dia"]+d)).sum()
        gain[i,j] = (out - base_series) / base_series * 100.0

fig_eq, ax = plt.subplots(figsize=(10,6))
sns.heatmap(gain, cmap="crest",
            xticklabels=[f"{x:.0f}%" for x in pct],
            yticklabels=[f"{y:+.1f}h" for y in dh],
            cbar_kws={"label": "Δ producción (%)"}, ax=ax)
ax.set_title("Equiparada: ΔTPH (%) × Δhoras (h/día) → Δ producción (%)")
ax.set_xlabel("Δ TPH (%)"); ax.set_ylabel("Δ horas (h/día)")
ax.set_xticklabels(ax.get_xticklabels(), fontsize=11, rotation=0)
ax.set_yticklabels(ax.get_yticklabels(), fontsize=11, rotation=0)
# línea guía
xs = np.linspace(pct.min(), pct.max(), 200)
ys = xs * dh_equiv_1pct / 100.0
for x, y in zip(xs, ys):
    if y < dh.min() or y > dh.max(): continue
    j = (np.abs(pct - x)).argmin(); i = (np.abs(dh - y)).argmin()
    ax.scatter([j+0.5], [i+0.5], s=6, color="#0B5563", marker="s")
ax.text(0.02, 1.04, f"Equivalencia: 1% TPH ≈ {dh_equiv_1pct:.2f} h/día",
        transform=ax.transAxes, ha="left", va="bottom", fontsize=10, color="#0B5563")
plt.tight_layout()
st.pyplot(fig_eq, use_container_width=True)

st.caption(f"≡ Equivalencia de esfuerzos: 1% TPH ≈ {dh_equiv_1pct:.2f} h/día")

# ================= 7) Narrativa ejecutiva =================
delta_tph_pct = (df["rendimiento_real_tph"].mean() - df["rendimiento_plan_tph"].mean()) / max(df["rendimiento_plan_tph"].mean(),1e-9) * 100
delta_h_pct   = (df["tiempo_operativo_real_h/dia"].mean() - df["tiempo_operativo_plan_h/dia"].mean()) / max(df["tiempo_operativo_plan_h/dia"].mean(),1e-9) * 100
p_tph = anova_tph["PR(>F)"].min() if "PR(>F)" in anova_tph.columns else np.nan
p_h   = anova_h["PR(>F)"].min() if "PR(>F)" in anova_h.columns else np.nan

st.subheader("Narrativa ejecutiva")
lines = []
lines.append(f"1) Promedios vs plan: TPH {delta_tph_pct:+.1f}% | Horas {delta_h_pct:+.1f}%.")
lines.append("2) La variabilidad mensual (CV) muestra meses inestables; estabilizar operación reduce pérdidas.")
if not np.isnan(p_tph):
    lines.append(f"3) ANOVA TPH por mes: p={p_tph:.4f} → diferencias {'significativas' if p_tph<0.05 else 'no significativas'}.")
if not np.isnan(p_h):
    lines.append(f"4) ANOVA Horas por mes: p={p_h:.4f} → diferencias {'significativas' if p_h<0.05 else 'no significativas'}.")
lines.append("5) Sensibilidad: aumentar TPH o horas eleva producción; el mapa equiparado indica qué palanca rinde más según la equivalencia empírica.")
if dh_equiv_1pct < 0.6:
    lines.append("6) Quick win: recuperar +0.5h/día suele superar +1% TPH → foco en disponibilidad.")
else:
    lines.append("6) Quick win: +1% TPH comparable/superior a +0.5h/día → foco en capacidad instantánea.")
st.code("\n".join(lines), language="markdown")

# ============================================================
# DESCARGA PPTX 16:9
# ============================================================
def save_current_fig_to_bytes(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    buf.seek(0)
    return buf

def build_pptx(df, figs, narrative_lines):
    prs = Presentation()
    prs.slide_width  = Inches(13.33)
    prs.slide_height = Inches(7.5)

    def add_title_slide(title, subtitle=""):
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        tx = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12.3), Inches(1.0))
        p = tx.text_frame.paragraphs[0]
        p.text = title; p.font.size = Pt(36); p.font.bold = True
        p.font.color.rgb = RGBColor(0x32,0x8B,0xA1)
        if subtitle:
            tx2 = slide.shapes.add_textbox(Inches(0.5), Inches(1.3), Inches(12.3), Inches(0.8))
            p2 = tx2.text_frame.paragraphs[0]
            p2.text = subtitle; p2.font.size = Pt(18); p2.font.color.rgb = RGBColor(0x0B,0x55,0x63)

    def add_image(title, img_bytes):
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        tx = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12.3), Inches(0.8))
        p = tx.text_frame.paragraphs[0]
        p.text = title; p.font.size = Pt(28); p.font.bold = True; p.font.color.rgb = RGBColor(0x32,0x8B,0xA1)
        slide.shapes.add_picture(img_bytes, Inches(0.5), Inches(1.1), width=Inches(12.3))

    def add_bullets(title, lines):
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        tx = slide.shapes.add_textbox(Inches(0.5), Inches(0.5), Inches(12.3), Inches(6.5))
        tf = tx.text_frame; tf.word_wrap = True
        p = tf.paragraphs[0]; p.text = title
        p.font.size = Pt(28); p.font.bold = True; p.font.color.rgb = RGBColor(0x32,0x8B,0xA1)
        for line in lines:
            pr = tf.add_paragraph(); pr.text = line; pr.level = 1; pr.font.size = Pt(20)

    add_title_slide("Chancado — Consolidado", f"{df['Fecha'].min().date()} a {df['Fecha'].max().date()}")

    # Agregar todas las figuras
    titles = [
        "Evolución diaria — TPH y Horas",
        "Distribución mensual — TPH y Horas",
        "Variabilidad mensual (CV)",
        "Brechas promedio vs plan",
        "Sensibilidad iso-%",
        "Sensibilidad equiparada",
        "ANOVA — TPH por mes",
        "ANOVA — Horas por mes"
    ]
    for title, fig in zip(titles, figs):
        add_image(title, fig)

    add_bullets("Narrativa ejecutiva", narrative_lines)
    out = io.BytesIO()
    prs.save(out)
    out.seek(0)
    return out

# Regenerar figuras para PPTX (en bytes)
fig1 = fig_serie_temporal(df)
buf1 = save_current_fig_to_bytes(fig1)

fig2 = fig_boxplots(df)
buf2 = save_current_fig_to_bytes(fig2)

fig3 = fig_cv(cv)
buf3 = save_current_fig_to_bytes(fig3)

fig4 = fig_brechas(promedios)
buf4 = save_current_fig_to_bytes(fig4)

# Para ANOVA, generamos tablas como imágenes simples
def table_to_fig(table_df, title):
    fig, ax = plt.subplots(figsize=(7.5,3.2))
    ax.axis("off")
    try:
        tb = table_df.copy().round(4).reset_index()
        tbl = ax.table(cellText=tb.values, colLabels=tb.columns.tolist(), loc="center")
        tbl.scale(1,1.2)
        ax.set_title(title, pad=6)
    except Exception as e:
        ax.text(0.5,0.5,f"Error: {e}",ha="center",va="center")
    plt.tight_layout()
    return fig

fig5 = fig_iso
buf5 = save_current_fig_to_bytes(fig5)

fig6 = fig_eq
buf6 = save_current_fig_to_bytes(fig6)

fig7 = table_to_fig(anova_tph, "ANOVA — TPH por mes")
buf7 = save_current_fig_to_bytes(fig7)

fig8 = table_to_fig(anova_h, "ANOVA — Horas por mes")
buf8 = save_current_fig_to_bytes(fig8)

ppt_bytes = build_pptx(df, [buf1,buf2,buf3,buf4,buf5,buf6,buf7,buf8], lines)

st.download_button(
    "⬇️ Descargar PPTX 16:9",
    data=ppt_bytes,
    file_name=f"chancado_fusion_{pd.Timestamp.now():%Y%m%d_%H%M}.pptx",
    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
)
