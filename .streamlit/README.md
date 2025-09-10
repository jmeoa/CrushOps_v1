# EDA Chancado — FUSIÓN (Streamlit)

Sube un CSV con columnas de chancado (con alias aceptados). Limpieza robusta, KPIs, series/boxplots/CV, brechas, ANOVA y mapas de sensibilidad. Exporta PPTX 16:9.

## Despliegue
- Repositorio con `app.py` y `requirements.txt`.
- En https://streamlit.io/cloud: New app → elige tu repo/branch → file path: app.py → Deploy.

## Columnas requeridas (con alias)
- Fecha: fecha, date
- mineral_procesado_real_t: mineral_real_t, ton_real, tons_real
- rendimiento_real_tph: tph_real, real_tph
- tiempo_operativo_real_h/dia: tiempo_operativo_real_h_dia, horas_reales, h_real
- mineral_procesado_plan_t: mineral_plan_t, ton_plan, tons_plan
- rendimiento_plan_tph: tph_plan, plan_tph
- tiempo_operativo_plan_h/dia: tiempo_operativo_plan_h_dia, horas_plan, h_plan
