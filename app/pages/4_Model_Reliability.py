from __future__ import annotations

import pandas as pd
import plotly.express as px
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

configure_page("Model Reliability", "◎")
root, profile, artifacts, _ = load_app_context(__file__)
sidebar_context(artifacts, "Model Reliability")
page_header(
    "Reliability & governance / 05",
    "Confiança exige evidência — e limites",
    "Desempenho temporal, calibração, cobertura, segmentos, latência e OOD em uma visão "
    "auditável. Falhas de meta permanecem visíveis.",
)

metrics = cached_dataset(str(root), profile, "final_metrics")
manifest = cached_dataset(str(root), profile, "evaluation_manifest")
optimization = cached_dataset(str(root), profile, "optimization_manifest")
quantiles = metrics[metrics["model"] == "catboost_multiquantile"].copy()
classifiers = metrics[metrics["model"] == "catboost_calibrated_sigmoid"].copy()

columns = st.columns(5)
cards = [
    ("Teste final", "1×", "avaliação congelada", "teal"),
    ("Checks modelos", "50/50", "validação Fase 5", "green"),
    (
        "Cobertura P10–P90",
        f"{quantiles['empirical_coverage_80'].min() * 100:.1f}–"
        f"{quantiles['empirical_coverage_80'].max() * 100:.1f}%",
        "seis regressões",
        "cyan",
    ),
    (
        "ECE calibrado",
        f"{classifiers['ece_10'].min():.4f}–{classifiers['ece_10'].max():.4f}",
        "quatro classificadores",
        "amber",
    ),
    (
        "Cenários seguros",
        f"{optimization['published_hard_constraint_pass_rate'] * 100:.0f}%",
        "12 publicados",
        "green",
    ),
]
for column, card in zip(columns, cards, strict=True):
    column.markdown(metric_card(*card[:3], color=card[3]), unsafe_allow_html=True)

if not manifest["engineering_goal"]["met"]:
    callout(
        "Meta TBH não atingida: melhora relativa de 0,98% contra a baseline mais forte, abaixo "
        "da meta de 5%. O resultado não foi reclassificado nem ocultado.",
        kind="danger",
    )

left, right = st.columns(2)
with left:
    section_title("Cobertura dos intervalos", "Meta nominal de 80%")
    figure = px.bar(
        quantiles,
        x="task",
        y="empirical_coverage_80",
        color="coverage_error_abs",
        color_continuous_scale=[[0, COLORS["teal"]], [1, COLORS["amber"]]],
        text_auto=".1%",
    )
    figure.add_hline(y=0.8, line_dash="dash", line_color=COLORS["cyan"])
    figure.update_coloraxes(showscale=False)
    style_figure(
        figure,
        height=390,
        xaxis_title="",
        yaxis_title="Cobertura",
        yaxis_tickformat=".0%",
    )
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})
with right:
    section_title("Probabilidades calibradas", "ECE e Brier no teste final")
    calibration = classifiers[["task", "ece_10", "brier", "pr_auc"]].melt(
        id_vars="task",
        value_vars=["ece_10", "brier"],
        var_name="metric",
        value_name="value",
    )
    figure = px.bar(
        calibration,
        x="task",
        y="value",
        color="metric",
        barmode="group",
        color_discrete_map={"ece_10": COLORS["teal"], "brier": COLORS["amber"]},
    )
    style_figure(figure, height=390, xaxis_title="", yaxis_title="Erro · menor é melhor")
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})

section_title("Comparação por tarefa", "Baselines e modelo principal no mesmo teste")
task = st.selectbox("Tarefa", sorted(metrics["task"].unique()))
task_metrics = metrics[metrics["task"] == task]
problem_type = task_metrics["problem_type"].iloc[0]
if problem_type == "regression":
    view = task_metrics.dropna(subset=["mae"])
    figure = px.bar(
        view,
        x="model",
        y="mae",
        color="model",
        text_auto=".3f",
        color_discrete_sequence=[
            COLORS["steel"],
            COLORS["cyan"],
            COLORS["amber"],
            COLORS["orange"],
            COLORS["teal"],
        ],
    )
    ylabel = "MAE · menor é melhor"
else:
    view = task_metrics.dropna(subset=["pr_auc"])
    figure = px.bar(
        view,
        x="model",
        y="pr_auc",
        color="model",
        text_auto=".3f",
        color_discrete_sequence=[
            COLORS["steel"],
            COLORS["cyan"],
            COLORS["amber"],
            COLORS["orange"],
            COLORS["teal"],
        ],
    )
    ylabel = "PR-AUC · maior é melhor"
style_figure(figure, height=350, xaxis_title="", yaxis_title=ylabel, showlegend=False)
st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})

segments = cached_dataset(str(root), profile, "segment_metrics")
segment_view = segments[segments["task"] == task].copy()
if not segment_view.empty:
    segment = st.selectbox("Dimensão de segmento", sorted(segment_view["segment"].unique()))
    segment_view = segment_view[segment_view["segment"] == segment]
    metric = "mae" if problem_type == "regression" else "pr_auc"
    segment_view = segment_view.dropna(subset=[metric]).sort_values(metric)
    section_title("Estabilidade por segmento", f"{metric.upper()} · suporte mínimo contratado")
    figure = px.bar(
        segment_view,
        x="segment_value",
        y=metric,
        color=metric,
        color_continuous_scale=[[0, COLORS["teal"]], [1, COLORS["orange"]]],
        hover_data=["rows"],
    )
    figure.update_coloraxes(showscale=False)
    style_figure(figure, height=350, xaxis_title="", yaxis_title=metric.upper())
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})

left, right = st.columns([1.15, 1])
with left:
    section_title("Backtest temporal", "Três folds expansivos antes do teste final")
    stability = pd.DataFrame(
        [
            {"task": name, **record}
            for name, record in manifest["backtest_stability"].items()
        ]
    )
    figure = px.bar(
        stability,
        x="task",
        y="mean",
        error_y="std",
        color="task",
        color_discrete_sequence=[COLORS["teal"], COLORS["amber"], COLORS["cyan"]],
        hover_data=["metric", "min", "max", "folds"],
    )
    style_figure(
        figure,
        height=340,
        xaxis_title="",
        yaxis_title="Média do métrico",
        showlegend=False,
    )
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})
with right:
    section_title("Latência congelada", "Lote de 1.000 linhas; medição local")
    latency = pd.DataFrame(manifest["inference_latency"]["tasks"])
    figure = px.bar(
        latency.sort_values("median_batch_ms"),
        x="median_batch_ms",
        y="task",
        orientation="h",
        color="median_batch_ms",
        color_continuous_scale=[[0, COLORS["teal"]], [1, COLORS["amber"]]],
    )
    figure.update_coloraxes(showscale=False)
    style_figure(figure, height=340, xaxis_title="ms por lote", yaxis_title="")
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})

scenarios = cached_dataset(str(root), profile, "scenarios")
ood = pd.DataFrame(
    [
        {
            "scenario": item["scenario_id"],
            "context": item["context_id"],
            "label": item["label"],
            "distance_ratio": item["ood_assessment"]["distance_ratio"],
            "in_distribution": item["ood_assessment"]["in_distribution"],
        }
        for item in scenarios
    ]
)
section_title("Monitor OOD dos cenários publicados", "Razão abaixo de 1,00 em todos os casos")
figure = px.scatter(
    ood,
    x="scenario",
    y="distance_ratio",
    color="context",
    symbol="label",
    color_discrete_sequence=[COLORS["teal"], COLORS["amber"], COLORS["cyan"]],
)
figure.add_hline(y=1, line_dash="dash", line_color=COLORS["red"])
style_figure(figure, height=340, xaxis_title="", yaxis_title="Distância relativa")
st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})

with st.expander("Model card da tarefa selecionada"):
    st.markdown(cached_dataset(str(root), profile, "model_card", task))
