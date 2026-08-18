from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from steelflow.product.ui import (
    COLORS,
    aggregate_executive,
    cached_dataset,
    callout,
    configure_page,
    format_number,
    load_app_context,
    metric_card,
    page_header,
    section_title,
    sidebar_context,
    style_figure,
)

configure_page("Executive Overview", "◈")
root, profile, artifacts, _ = load_app_context(__file__)
sidebar_context(artifacts, "Executive Overview")

page_header(
    "Executive intelligence / 01",
    "Da retrospectiva à decisão contextual",
    "Desempenho, qualidade, energia e perdas em uma fábrica OCTG inteiramente sintética. "
    "Os números apoiam exploração; não representam produção ou ganho real.",
)

trend = cached_dataset(str(root), profile, "executive_trend").copy()
trend["full_date"] = pd.to_datetime(trend["full_date"])
with st.sidebar:
    st.markdown("---")
    st.caption("FILTROS EXECUTIVOS")
    line = st.selectbox("Linha", ["Todas", *sorted(trend["line_id"].unique())])
    shift = st.selectbox("Turno", ["Todos", *sorted(trend["shift_id"].unique())])
    date_range = st.date_input(
        "Período",
        value=(trend["full_date"].min().date(), trend["full_date"].max().date()),
        min_value=trend["full_date"].min().date(),
        max_value=trend["full_date"].max().date(),
    )

filtered = trend.copy()
if line != "Todas":
    filtered = filtered[filtered["line_id"] == line]
if shift != "Todos":
    filtered = filtered[filtered["shift_id"] == shift]
if isinstance(date_range, tuple) and len(date_range) == 2:
    filtered = filtered[
        filtered["full_date"].between(pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1]))
    ]
if filtered.empty:
    st.warning("Nenhum dado disponível para os filtros selecionados.")
    st.stop()

kpis = aggregate_executive(filtered)
columns = st.columns(6)
cards = [
    ("TBH", f"{format_number(kpis['tbh'], 2)} t/h", "Toneladas boas / hora produtiva", "teal"),
    ("FPY", f"{format_number(kpis['fpy'] * 100, 1)}%", "Aprovação estimada na 1ª passagem", "cyan"),
    ("OEE", f"{format_number(kpis['oee'] * 100, 1)}%", "Referência interna simulada", "amber"),
    ("Energia", f"{format_number(kpis['energy'], 1)}", "kWh por tonelada boa", "orange"),
    (
        "Paradas",
        f"{format_number(kpis['downtime'] / 60, 0)} h",
        "Minutos não planejados agregados",
        "red",
    ),
    (
        "Toneladas boas",
        format_number(kpis["good_tonnes"], 0),
        "Massa sintética no período",
        "green",
    ),
]
for column, (label, value, note, color) in zip(columns, cards, strict=True):
    column.markdown(metric_card(label, value, note, color=color), unsafe_allow_html=True)

callout(
    "Leitura executiva: resultados agregados misturam produto, grau e condição operacional. "
    "Use o gap ajustado por mix antes de atribuir mudança ao processo."
)

monthly = (
    filtered.assign(month=filtered["full_date"].dt.to_period("M").dt.to_timestamp())
    .groupby(["month", "line_id"], as_index=False)
    .agg(
        good_tonnes=("good_tonnes", "sum"),
        productive_hours=("productive_hours", "sum"),
        total_tonnes=("total_tonnes", "sum"),
        tube_count=("tube_count", "sum"),
        energy_kwh=("energy_kwh", "sum"),
        downtime=("unplanned_downtime_minutes", "sum"),
        weighted_fpy=("fpy", lambda values: float(values.mean())),
    )
)
monthly["tbh"] = monthly["good_tonnes"] / monthly["productive_hours"]
monthly["energy"] = monthly["energy_kwh"] / monthly["good_tonnes"]

left, right = st.columns([1.65, 1])
with left:
    section_title("Trajetória de produtividade", "TBH mensal por linha")
    figure = px.line(
        monthly,
        x="month",
        y="tbh",
        color="line_id",
        color_discrete_sequence=[COLORS["teal"], COLORS["amber"], COLORS["cyan"]],
        markers=True,
    )
    figure.update_traces(line_width=2.4, marker_size=5)
    style_figure(figure, height=390, xaxis_title="", yaxis_title="TBH · t/h")
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})
with right:
    section_title("Linhas em perspectiva", "Resultado agregado do filtro")
    line_summary = (
        filtered.groupby("line_id", as_index=False)
        .agg(good_tonnes=("good_tonnes", "sum"), productive_hours=("productive_hours", "sum"))
    )
    line_summary["tbh"] = line_summary["good_tonnes"] / line_summary["productive_hours"]
    figure = px.bar(
        line_summary,
        x="tbh",
        y="line_id",
        orientation="h",
        text_auto=".2f",
        color="tbh",
        color_continuous_scale=[[0, COLORS["panel_alt"]], [1, COLORS["teal"]]],
    )
    figure.update_coloraxes(showscale=False)
    style_figure(figure, height=390, xaxis_title="TBH · t/h", yaxis_title="")
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})

mix = cached_dataset(str(root), profile, "mix_adjustment").copy()
mix["full_date"] = pd.to_datetime(mix["full_date"])
if line != "Todas":
    mix = mix[mix["line_id"] == line]
mix_monthly = (
    mix.assign(month=mix["full_date"].dt.to_period("M").dt.to_timestamp())
    .groupby(["month", "line_id"], as_index=False)["mix_adjusted_tbh_gap"]
    .mean()
)
losses = cached_dataset(str(root), profile, "loss_pareto").copy()
losses["share"] = losses["loss_tonnes_equivalent"] / losses["loss_tonnes_equivalent"].sum()
losses["cumulative"] = losses["share"].cumsum()

left, right = st.columns([1.35, 1])
with left:
    section_title(
        "Sinal após ajuste de mix",
        "Gap observado − esperado por mix; associação descritiva",
    )
    figure = px.bar(
        mix_monthly,
        x="month",
        y="mix_adjusted_tbh_gap",
        color="line_id",
        barmode="group",
        color_discrete_sequence=[COLORS["teal"], COLORS["amber"], COLORS["cyan"]],
    )
    figure.add_hline(y=0, line_color=COLORS["steel"], line_width=1)
    style_figure(figure, height=360, xaxis_title="", yaxis_title="Gap TBH · t/h")
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})
with right:
    section_title("Pareto de perdas", "Equivalente sintético em toneladas")
    figure = go.Figure()
    figure.add_bar(
        x=losses["loss_type"],
        y=losses["loss_tonnes_equivalent"],
        marker_color=COLORS["orange"],
        name="Perda",
    )
    figure.add_scatter(
        x=losses["loss_type"],
        y=losses["cumulative"] * 100,
        yaxis="y2",
        mode="lines+markers",
        line={"color": COLORS["teal"], "width": 2},
        name="Acumulado",
    )
    style_figure(
        figure,
        height=360,
        xaxis_title="",
        yaxis_title="t equivalentes",
        yaxis2={
            "title": "% acumulado",
            "overlaying": "y",
            "side": "right",
            "range": [0, 105],
            "gridcolor": "rgba(0,0,0,0)",
        },
    )
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})

section_title("Sinais que pedem investigação", "Alertas estatísticos não equivalem a causa")
quality_alerts = cached_dataset(str(root), profile, "quality_alerts")
tbh_signals = cached_dataset(str(root), profile, "tbh_control_signals")
tbh_recent = tbh_signals[tbh_signals["control_signal"]].sort_values("full_date", ascending=False)
alert_columns = st.columns(3)
alert_columns[0].metric(
    "Sinais dimensionais",
    len(quality_alerts),
    help="Últimos 100 registros materializados",
)
alert_columns[1].metric(
    "Sinais de TBH",
    len(tbh_recent),
    help="Limites estimados no baseline temporal",
)
alert_columns[2].metric("Linhas no filtro", filtered["line_id"].nunique())
if not quality_alerts.empty:
    display = quality_alerts.head(8).rename(
        columns={
            "full_date": "Data",
            "line_id": "Linha",
            "product_code": "Produto",
            "grade_family": "Grau",
            "characteristic": "Característica",
            "conformance_rate": "Conformidade",
        }
    )
    st.dataframe(
        display[["Data", "Linha", "Produto", "Grau", "Característica", "Conformidade"]],
        width="stretch",
        hide_index=True,
        column_config={
            "Conformidade": st.column_config.ProgressColumn(
                format="percent", min_value=0, max_value=1
            )
        },
    )

st.caption(
    "SteelFlow AI · protótipo offline com dados 100% sintéticos · limites internos simulados · "
    "nenhuma recomendação controla equipamentos."
)
