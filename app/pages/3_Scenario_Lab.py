from __future__ import annotations

import json

import pandas as pd
import plotly.express as px
import streamlit as st

from steelflow.product.scenario import (
    approve_scenario,
    evaluate_interactive_scenario,
    scenario_csv_bytes,
    scenario_json_bytes,
)
from steelflow.product.ui import (
    COLORS,
    cached_dataset,
    cached_scenario_runtime,
    callout,
    configure_page,
    load_app_context,
    metric_card,
    page_header,
    section_title,
    sidebar_context,
    style_figure,
)

configure_page("Scenario Lab", "◇")
root, profile, artifacts, _ = load_app_context(__file__)
sidebar_context(artifacts, "Scenario Lab")
page_header(
    "Constrained decisions / 04",
    "Experimente dentro do envelope",
    "Ajuste somente controles elegíveis, compare alternativas Pareto e submeta um cenário "
    "à revisão humana. Fora do suporte histórico, o laboratório recusa a recomendação.",
)
callout(
    "Nenhuma ação nesta página envia comando à produção. Todos os limites são internos e "
    "simulados; "
    "a confirmação humana registra apenas revisão de uma simulação sintética."
)

scenarios = cached_dataset(str(root), profile, "scenarios")
contexts = sorted({item["context_id"] for item in scenarios})
context_id = st.selectbox("Contexto", contexts)
context_scenarios = [item for item in scenarios if item["context_id"] == context_id]
current = next(item for item in context_scenarios if item["label"] == "current")
context = current["fixed_context"]
badges = " ".join(
    f'<span class="sf-badge">{value}</span>'
    for value in (
        context["line_id"],
        context["product_code"],
        context["grade_family"],
        context["shift_id"],
    )
)
st.markdown(badges, unsafe_allow_html=True)

section_title("Alternativas publicadas", "Todas passaram nas restrições e no guarda OOD")
summary_rows = []
for item in context_scenarios:
    summary_rows.append(
        {
            "Perfil": item["label"],
            "TBH proxy": item["predictions"]["estimated_tbh_proxy"]["p50"],
            "FPY": item["predictions"]["quality"]["estimated_fpy"],
            "Energia": item["predictions"]["energy_per_good_tonne_kwh_t"]["p50"],
            "Risco qualidade": item["predictions"]["quality"]["failure_probability"],
            "Distância": item["ood_assessment"]["distance_ratio"],
        }
    )
summary = pd.DataFrame(summary_rows)
st.dataframe(
    summary,
    width="stretch",
    hide_index=True,
    column_config={
        "TBH proxy": st.column_config.NumberColumn(format="%.2f t boa/h"),
        "FPY": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
        "Energia": st.column_config.NumberColumn(format="%.1f kWh/t"),
        "Risco qualidade": st.column_config.ProgressColumn(
            format="percent", min_value=0, max_value=1
        ),
        "Distância": st.column_config.ProgressColumn(format="%.2f×", min_value=0, max_value=1),
    },
)

selected_label = st.radio(
    "Ponto de partida",
    ["conservative", "balanced", "productivity"],
    horizontal=True,
    index=1,
)
selected = next(item for item in context_scenarios if item["label"] == selected_label)
envelope_path = artifacts.optimization_root / "envelopes" / f"{context_id}.json"
envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
bounds = {item["name"]: item for item in envelope["bounds"]}

section_title("Controles elegíveis", "Faixas condicionais e mudança máxima já aplicadas")
with st.form(f"scenario_form_{context_id}"):
    parameters: dict[str, float] = {}
    groups = st.columns(3)
    for index, (name, specification) in enumerate(selected["parameters"].items()):
        bound = bounds[name]
        lower = float(bound["decision_lower"])
        upper = float(bound["decision_upper"])
        value = min(max(float(specification["value"]), lower), upper)
        step = max((upper - lower) / 100, 0.001)
        with groups[index % 3]:
            parameters[name] = st.slider(
                name.replace("_", " ").title(),
                min_value=lower,
                max_value=upper,
                value=value,
                step=step,
                format="%.3f",
                help=f"Atual: {bound['current_value']:.3f} {specification['unit']}",
                key=f"{context_id}_{name}",
            )
    submitted = st.form_submit_button("Avaliar cenário", type="primary", width="stretch")

if submitted:
    try:
        runtime = cached_scenario_runtime(str(root), profile, context_id)
        with st.spinner("Aplicando modelos congelados, quantis e guarda OOD…"):
            st.session_state["interactive_scenario"] = evaluate_interactive_scenario(
                runtime,
                parameters,
            )
        st.session_state.pop("approved_scenario", None)
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
        st.error(f"A avaliação segura não pôde ser concluída: {exc}")

result = st.session_state.get("interactive_scenario")
if result and result.get("context_id") == context_id:
    section_title("Resultado estimado", "Backtest sintético; não contrafactual causal")
    predictions = result["predictions"]
    columns = st.columns(5)
    cards = [
        ("TBH proxy", f"{predictions['estimated_tbh_proxy']:.2f}", "t boa/h", "teal"),
        ("FPY", f"{predictions['estimated_fpy'] * 100:.1f}%", "estimado", "cyan"),
        ("Energia", f"{predictions['energy_per_good_tonne']['p50']:.1f}", "kWh/t boa", "amber"),
        (
            "Risco qualidade",
            f"{predictions['quality_failure_probability'] * 100:.1f}%",
            "calibrado",
            "orange",
        ),
        (
            "Distância",
            f"{result['ood_assessment']['distance_ratio']:.2f}×",
            "máximo 1,00×",
            "green" if result["recommendation_issued"] else "red",
        ),
    ]
    for column, card in zip(columns, cards, strict=True):
        column.markdown(metric_card(*card[:3], color=card[3]), unsafe_allow_html=True)

    if result["recommendation_issued"]:
        callout(
            "Cenário dentro do envelope e das restrições. Elegível apenas para revisão humana; "
            "nenhuma ação automática será executada.",
            kind="safe",
        )
    else:
        callout(
            "Cenário recusado. Nenhuma recomendação foi emitida; solicite validação de engenharia.",
            kind="danger",
        )

    comparison = pd.DataFrame(
        [
            {
                "Cenário": "Atual",
                "TBH proxy": current["predictions"]["estimated_tbh_proxy"]["p50"],
                "FPY": current["predictions"]["quality"]["estimated_fpy"],
                "Energia": current["predictions"]["energy_per_good_tonne_kwh_t"]["p50"],
            },
            {
                "Cenário": "Customizado",
                "TBH proxy": predictions["estimated_tbh_proxy"],
                "FPY": predictions["estimated_fpy"],
                "Energia": predictions["energy_per_good_tonne"]["p50"],
            },
        ]
    )
    left, right = st.columns([1.2, 1])
    with left:
        figure = px.bar(
            comparison.melt(id_vars="Cenário", value_vars=["TBH proxy", "Energia"]),
            x="variable",
            y="value",
            color="Cenário",
            barmode="group",
            color_discrete_map={"Atual": COLORS["steel"], "Customizado": COLORS["teal"]},
        )
        style_figure(figure, height=340, xaxis_title="", yaxis_title="Valor")
        st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})
    with right:
        constraints = pd.DataFrame(result["constraints"]).sort_values("margin")
        st.dataframe(
            constraints[["name", "margin", "status"]],
            width="stretch",
            hide_index=True,
            column_config={"margin": st.column_config.NumberColumn(format="%.3f")},
        )

    if result["recommendation_issued"]:
        acknowledgement = st.checkbox(
            "Confirmo que revisei uma simulação sintética e que isto não constitui "
            "comando de máquina.",
            key=f"ack_{context_id}",
        )
        if st.button("Registrar aprovação humana", type="primary", disabled=not acknowledgement):
            try:
                st.session_state["approved_scenario"] = approve_scenario(
                    result,
                    acknowledgement=acknowledgement,
                )
                st.success("Revisão humana registrada localmente nesta sessão.")
            except ValueError as exc:
                st.error(str(exc))
        approved = st.session_state.get("approved_scenario")
        if approved and approved.get("context_id") == context_id:
            st.markdown("**Exportação auditável**")
            export_columns = st.columns(2)
            export_columns[0].download_button(
                "Baixar JSON",
                data=scenario_json_bytes(approved),
                file_name=f"{context_id}-approved-scenario.json",
                mime="application/json",
                width="stretch",
            )
            export_columns[1].download_button(
                "Baixar CSV",
                data=scenario_csv_bytes(approved),
                file_name=f"{context_id}-approved-scenario.csv",
                mime="text/csv",
                width="stretch",
            )
else:
    st.info(
        "Ajuste os controles e selecione **Avaliar cenário** para executar os "
        "modelos congelados."
    )
