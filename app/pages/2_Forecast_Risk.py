from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from steelflow.product.ui import (
    COLORS,
    cached_dataset,
    callout,
    configure_page,
    load_app_context,
    metric_card,
    page_header,
    section_title,
    sidebar_context,
    style_figure,
)

configure_page("Forecast & Risk", "⌁")
root, profile, artifacts, _ = load_app_context(__file__)
sidebar_context(artifacts, "Forecast & Risk")
page_header(
    "Predictive intelligence / 03",
    "Previsões com faixa, risco com contexto",
    "Compare P10, P50 e P90, probabilidade calibrada e distância histórica. "
    "A incerteza é parte da decisão — não um rodapé.",
)

scenarios = cached_dataset(str(root), profile, "scenarios")
contexts = sorted({item["context_id"] for item in scenarios})
context_id = st.selectbox("Contexto demonstrativo", contexts)
view = [item for item in scenarios if item["context_id"] == context_id]
current = next(item for item in view if item["label"] == "current")
context = current["fixed_context"]
st.markdown(
    " ".join(
        [
            f'<span class="sf-badge">{context["line_id"]}</span>',
            f'<span class="sf-badge">{context["product_code"]}</span>',
            f'<span class="sf-badge">{context["grade_family"]}</span>',
            f'<span class="sf-badge">{context["shift_id"]}</span>',
        ]
    ),
    unsafe_allow_html=True,
)

columns = st.columns(5)
quality_risk = current["predictions"]["quality"]["failure_probability"]
downtime = current["predictions"]["downtime"]
cards = [
    (
        "TBH proxy P50",
        f"{current['predictions']['estimated_tbh_proxy']['p50']:.2f}",
        "t boa/h · proxy auxiliar",
        "teal",
    ),
    (
        "FPY estimado",
        f"{current['predictions']['quality']['estimated_fpy'] * 100:.1f}%",
        "probabilidade calibrada",
        "cyan",
    ),
    ("Risco qualidade", f"{quality_risk * 100:.1f}%", "limite duro: 25%", "amber"),
    ("Risco parada", f"{downtime['probability'] * 100:.1f}%", "invariante no contexto", "orange"),
    (
        "Distância histórica",
        f"{current['ood_assessment']['distance_ratio']:.2f}×",
        "máximo permitido: 1,00×",
        "green",
    ),
]
for column, card in zip(columns, cards, strict=True):
    column.markdown(metric_card(*card[:3], color=card[3]), unsafe_allow_html=True)

callout(
    "A proxy de TBH usa o surrogate de actual_tph e risco de qualidade; não substitui o modelo TBH "
    "pré-ordem. Risco de parada é fixo entre alternativas porque o modelo de ativo não "
    "recebe controles de laminação."
)

labels = [item["label"] for item in view]
throughput = pd.DataFrame(
    [
        {
            "label": item["label"],
            **{
                key: item["predictions"]["actual_tph_surrogate"][key]
                for key in ("p10", "p50", "p90")
            },
        }
        for item in view
    ]
)
energy = pd.DataFrame(
    [
        {
            "label": item["label"],
            **{
                key: item["predictions"]["energy_per_good_tonne_kwh_t"][key]
                for key in ("p10", "p50", "p90")
            },
        }
        for item in view
    ]
)
left, right = st.columns(2)
with left:
    section_title("Faixa de produtividade", "P10–P90 por alternativa")
    figure = go.Figure()
    figure.add_bar(
        x=throughput["label"],
        y=throughput["p50"],
        error_y={
            "type": "data",
            "symmetric": False,
            "array": throughput["p90"] - throughput["p50"],
            "arrayminus": throughput["p50"] - throughput["p10"],
        },
        marker_color=[COLORS["steel"], COLORS["teal"], COLORS["cyan"], COLORS["amber"]],
    )
    style_figure(figure, height=390, xaxis_title="", yaxis_title="actual_tph · t/h")
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})
with right:
    section_title("Faixa de energia", "P10–P90 por alternativa")
    figure = go.Figure()
    figure.add_bar(
        x=energy["label"],
        y=energy["p50"],
        error_y={
            "type": "data",
            "symmetric": False,
            "array": energy["p90"] - energy["p50"],
            "arrayminus": energy["p50"] - energy["p10"],
        },
        marker_color=[COLORS["steel"], COLORS["teal"], COLORS["cyan"], COLORS["amber"]],
    )
    style_figure(figure, height=390, xaxis_title="", yaxis_title="kWh / t boa")
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})

risk = pd.DataFrame(
    [
        {
            "label": item["label"],
            "quality_failure": item["predictions"]["quality"]["failure_probability"],
            "downtime": item["predictions"]["downtime"]["probability"],
            "distance": item["ood_assessment"]["distance_ratio"],
        }
        for item in view
    ]
)
left, right = st.columns([1.25, 1])
with left:
    section_title("Risco calibrado", "Probabilidade; limites simulados")
    melted = risk.melt(
        id_vars="label",
        value_vars=["quality_failure", "downtime"],
        var_name="risk",
        value_name="probability",
    )
    figure = px.bar(
        melted,
        x="label",
        y="probability",
        color="risk",
        barmode="group",
        color_discrete_map={"quality_failure": COLORS["amber"], "downtime": COLORS["orange"]},
    )
    figure.add_hline(y=0.25, line_dash="dot", line_color=COLORS["red"])
    style_figure(
        figure,
        height=350,
        xaxis_title="",
        yaxis_title="Probabilidade",
        yaxis_tickformat=".0%",
    )
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})
with right:
    section_title("Guarda OOD", "Razão distância / limiar")
    figure = px.bar(
        risk,
        x="label",
        y="distance",
        color="distance",
        color_continuous_scale=[[0, COLORS["teal"]], [0.8, COLORS["amber"]], [1, COLORS["red"]]],
        range_color=[0, 1],
        text_auto=".2f",
    )
    figure.add_hline(y=1, line_dash="dash", line_color=COLORS["red"])
    figure.update_coloraxes(showscale=False)
    style_figure(figure, height=350, xaxis_title="", yaxis_title="Distância relativa")
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})

section_title("Modelo versus referências", "Mesmo teste final cronológico e intocado")
metrics = cached_dataset(str(root), profile, "final_metrics")
available_tasks = sorted(metrics["task"].unique())
task = st.selectbox("Tarefa", available_tasks, index=available_tasks.index("tbh"))
task_metrics = metrics[metrics["task"] == task].copy()
if task_metrics["problem_type"].iloc[0] == "regression":
    comparable = task_metrics.dropna(subset=["mae"])
    figure = px.bar(
        comparable,
        x="model",
        y="mae",
        color="model",
        color_discrete_sequence=[
            COLORS["steel"],
            COLORS["cyan"],
            COLORS["amber"],
            COLORS["orange"],
            COLORS["teal"],
        ],
        text_auto=".3f",
    )
    style_figure(
        figure,
        height=340,
        xaxis_title="",
        yaxis_title="MAE · menor é melhor",
        showlegend=False,
    )
else:
    comparable = task_metrics.dropna(subset=["pr_auc"])
    figure = px.bar(
        comparable,
        x="model",
        y="pr_auc",
        color="model",
        color_discrete_sequence=[
            COLORS["steel"],
            COLORS["cyan"],
            COLORS["amber"],
            COLORS["orange"],
            COLORS["teal"],
        ],
        text_auto=".3f",
    )
    style_figure(
        figure,
        height=340,
        xaxis_title="",
        yaxis_title="PR-AUC · maior é melhor",
        showlegend=False,
    )
st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})
if task == "tbh":
    st.warning(
        "Meta de engenharia não atingida: CatBoost reduziu o MAE em 0,98% contra a baseline "
        "condicionada, abaixo da meta de 5%."
    )
