from __future__ import annotations

import json

import pandas as pd
import plotly.express as px
import streamlit as st

from steelflow.product.ui import (
    COLORS,
    cached_dataset,
    callout,
    configure_page,
    load_app_context,
    page_header,
    section_title,
    sidebar_context,
    style_figure,
)

configure_page("Root Cause & Explainability", "⌁")
root, profile, artifacts, _ = load_app_context(__file__)
sidebar_context(artifacts, "Root Cause & Explainability")
page_header(
    "Explainability / 02",
    "Sinais associados, não culpados",
    "TreeSHAP global, por segmento e local revela quais features moveram previsões. "
    "O diagnóstico orienta investigação; não comprova causalidade industrial.",
)
callout(
    "SHAP explica o comportamento do modelo no conjunto sintético. Ele não mede efeito de "
    "intervenção, "
    "não ranqueia operadores e não substitui análise de engenharia."
)

task_labels = {
    "TBH": "tbh",
    "Falha de qualidade": "quality_failure",
    "Energia": "energy_intensity",
    "Excentricidade": "wall_eccentricity",
    "Ovalização": "ovality",
    "Parada": "downtime_occurrence",
}
selected_label = st.selectbox("Alvo explicado", list(task_labels))
task = task_labels[selected_label]

global_shap = cached_dataset(str(root), profile, "global_shap", task).head(12).sort_values(
    "mean_abs_shap"
)
left, right = st.columns([1.2, 1])
with left:
    section_title("Drivers globais", "Magnitude média absoluta TreeSHAP")
    figure = px.bar(
        global_shap,
        x="mean_abs_shap",
        y="feature",
        orientation="h",
        color="mean_abs_shap",
        color_continuous_scale=[[0, COLORS["panel_alt"]], [1, COLORS["teal"]]],
    )
    figure.update_coloraxes(showscale=False)
    style_figure(figure, height=460, xaxis_title="|SHAP| médio", yaxis_title="")
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})
with right:
    section_title("Como ler", "Uma trilha de evidência, não uma sentença")
    top = global_shap.sort_values("mean_abs_shap", ascending=False).head(4)
    for _, row in top.iterrows():
        st.markdown(f"**{row['feature']}**")
        st.progress(
            min(float(row["mean_abs_shap"] / top["mean_abs_shap"].max()), 1.0),
            text=f"importância relativa · rank {int(row['rank'])}",
        )
    st.info(
        "Sinal positivo/negativo depende do caso local. A magnitude global apenas indica quanto "
        "o modelo usou a feature em média."
    )

segment_shap = cached_dataset(str(root), profile, "segment_shap", task)
segment_column, value_column = st.columns(2)
segment = segment_column.selectbox("Recorte", sorted(segment_shap["segment"].unique()))
available_values = sorted(
    segment_shap.loc[segment_shap["segment"] == segment, "segment_value"].unique()
)
segment_value = value_column.selectbox("Segmento", available_values)
segment_view = segment_shap[
    (segment_shap["segment"] == segment)
    & (segment_shap["segment_value"] == segment_value)
].head(10)
section_title("Explicação por segmento", f"{segment} = {segment_value}")
figure = px.bar(
    segment_view.sort_values("mean_abs_shap"),
    x="mean_abs_shap",
    y="feature",
    orientation="h",
    text="rank",
    color_discrete_sequence=[COLORS["cyan"]],
)
style_figure(figure, height=390, xaxis_title="|SHAP| médio", yaxis_title="")
st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})

local = cached_dataset(str(root), profile, "local_explanations", task)
section_title("Caso local congelado", "Contribuições para uma previsão individual do teste final")
sample_key = st.selectbox("Amostra", local["sample_key"].astype(str).tolist())
row = local[local["sample_key"].astype(str) == sample_key].iloc[0]
contributions = pd.DataFrame(json.loads(row["top_contributions_json"]))
contributions["direction"] = contributions["shap"].map(
    lambda value: "eleva" if value >= 0 else "reduz"
)
metric_columns = st.columns(3)
metric_columns[0].metric("Observado", f"{row['observed']:.3f}")
metric_columns[1].metric("Previsto", f"{row['prediction']:.3f}")
metric_columns[2].metric("Base do modelo", f"{row['base_value']:.3f}")
figure = px.bar(
    contributions.sort_values("shap"),
    x="shap",
    y="feature",
    orientation="h",
    color="direction",
    color_discrete_map={"eleva": COLORS["orange"], "reduz": COLORS["teal"]},
    hover_data=["value"],
)
figure.add_vline(x=0, line_color=COLORS["steel"], line_width=1)
style_figure(figure, height=350, xaxis_title="Contribuição SHAP", yaxis_title="")
st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})

section_title("Interação de processo", "Velocidade × uniformidade térmica, estratificada")
interactions = cached_dataset(str(root), profile, "process_interactions")
filter_columns = st.columns(3)
product = filter_columns[0].selectbox("Produto", sorted(interactions["product_code"].unique()))
grade_values = sorted(
    interactions.loc[interactions["product_code"] == product, "grade_family"].unique()
)
grade = filter_columns[1].selectbox("Grau", grade_values)
line_values = sorted(
    interactions.loc[
        (interactions["product_code"] == product) & (interactions["grade_family"] == grade),
        "line_id",
    ].unique()
)
selected_line = filter_columns[2].selectbox("Linha", line_values)
interaction_view = interactions[
    (interactions["product_code"] == product)
    & (interactions["grade_family"] == grade)
    & (interactions["line_id"] == selected_line)
]
pivot = interaction_view.pivot_table(
    index="thermal_uniformity_band",
    columns="roll_speed_band",
    values="mean_actual_tph",
)
figure = px.imshow(
    pivot,
    color_continuous_scale=[[0, COLORS["panel_alt"]], [0.5, COLORS["cyan"]], [1, COLORS["amber"]]],
    labels={"x": "Faixa de velocidade", "y": "Faixa térmica", "color": "TPH médio"},
    text_auto=".1f",
    aspect="auto",
)
style_figure(figure, height=390)
st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})

associations = cached_dataset(str(root), profile, "segment_associations")
section_title(
    "Associações para investigação",
    "Coeficientes descritivos por produto × grau × linha",
)
st.dataframe(
    associations.drop(columns=["simulation_run_id"]).head(20),
    width="stretch",
    hide_index=True,
)
