# ruff: noqa: E501 - CSS rules are intentionally kept in native form.
"""Shared Streamlit presentation primitives and cached product access."""

from __future__ import annotations

import html
import os
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from steelflow.config import load_config_bundle
from steelflow.product.artifacts import (
    ProductArtifactError,
    ProductArtifacts,
    resolve_product_artifacts,
)
from steelflow.product.repository import ProductRepository, project_root_from_file
from steelflow.product.scenario import InteractiveScenarioRuntime, build_interactive_runtime

COLORS = {
    "ink": "#071421",
    "panel": "#0d2234",
    "panel_alt": "#102a3f",
    "steel": "#8ca5b8",
    "text": "#eff7fb",
    "muted": "#9ab0bf",
    "teal": "#31d6c4",
    "cyan": "#4cc9f0",
    "amber": "#ffb547",
    "orange": "#ff7849",
    "red": "#ff5f6d",
    "green": "#4ade80",
}

BASE_CSS = """
<style>
:root { --sf-ink:#071421; --sf-panel:#0d2234; --sf-teal:#31d6c4; --sf-amber:#ffb547; }
.stApp { background:
    radial-gradient(circle at 88% 2%, rgba(49,214,196,.10), transparent 28rem),
    radial-gradient(circle at 8% 22%, rgba(76,201,240,.07), transparent 24rem), #071421; }
html, body, [class*="css"] { font-family: Inter, 'Segoe UI', sans-serif; color: #eff7fb; }
[data-testid="stSidebar"] { background: #081a29; border-right: 1px solid rgba(140,165,184,.15); padding-left:1rem; }
[data-testid="stSidebarNav"] { padding-left:1rem; }
[data-testid="stSidebarUserContent"] { padding-left:1.5rem; padding-right:1.5rem; }
[data-testid="stHeader"] { background: rgba(7,20,33,.86); }
.block-container { max-width: 1440px; padding-top: 1.5rem; padding-bottom: 4rem; }
h1, h2, h3 { letter-spacing: -.03em; }
.sf-eyebrow { color:#31d6c4; font:600 .72rem Consolas, monospace; letter-spacing:.15em; text-transform:uppercase; }
.sf-title { font-size:clamp(2.2rem,4vw,4.1rem); line-height:1.02; font-weight:800; margin:.3rem 0 .7rem; }
.sf-subtitle { color:#9ab0bf; max-width:820px; font-size:1.02rem; line-height:1.65; }
.sf-rule { height:1px; margin:1.15rem 0 1.7rem; background:linear-gradient(90deg,#31d6c4,rgba(49,214,196,0)); }
.sf-badge { display:inline-flex; align-items:center; gap:.4rem; padding:.3rem .55rem; margin:.15rem .25rem .15rem 0;
  background:rgba(49,214,196,.08); border:1px solid rgba(49,214,196,.28); border-radius:999px;
  color:#b8fff6; font:500 .72rem Consolas, monospace; }
.sf-dot { width:.42rem; height:.42rem; border-radius:50%; background:#31d6c4; box-shadow:0 0 10px #31d6c4; }
.sf-card { min-height:128px; padding:1.05rem 1.15rem; border-radius:14px;
  background:linear-gradient(145deg,rgba(16,42,63,.96),rgba(10,29,45,.96));
  border:1px solid rgba(140,165,184,.14); box-shadow:0 12px 30px rgba(0,0,0,.16); }
.sf-card-label { color:#8ca5b8; font:500 .69rem Consolas, monospace; text-transform:uppercase; letter-spacing:.1em; }
.sf-card-value { font-size:1.75rem; font-weight:750; margin:.45rem 0 .15rem; }
.sf-card-note { color:#9ab0bf; font-size:.76rem; }
.sf-callout { padding:.9rem 1rem; border-radius:10px; color:#c8d8e3; background:rgba(255,181,71,.07);
  border-left:3px solid #ffb547; font-size:.86rem; }
.sf-safe { background:rgba(74,222,128,.08); border-left-color:#4ade80; }
.sf-danger { background:rgba(255,95,109,.08); border-left-color:#ff5f6d; }
.sf-section { margin-top:.65rem; color:#eef7fb; font-size:1.25rem; font-weight:700; }
[data-testid="stMetric"] { background:rgba(13,34,52,.82); border:1px solid rgba(140,165,184,.14); padding:1rem; border-radius:12px; }
[data-testid="stMetricValue"] { color:#eff7fb; }
[data-testid="stDataFrame"] { border:1px solid rgba(140,165,184,.12); border-radius:10px; overflow:hidden; }
.stButton > button, .stDownloadButton > button { border-radius:9px; font-weight:700; border:1px solid rgba(49,214,196,.35); }
.stButton > button[kind="primary"] { background:#31d6c4; color:#071421; border:0; }
code { font-family:Consolas, monospace; }
@media (max-width: 700px) { .block-container { padding-left:1rem; padding-right:1rem; } .sf-card { min-height:110px; } }
</style>
"""


def configure_page(title: str, icon: str) -> None:
    st.set_page_config(
        page_title=f"{title} · SteelFlow AI",
        page_icon=icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(BASE_CSS, unsafe_allow_html=True)


def page_header(eyebrow: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="sf-eyebrow">{html.escape(eyebrow)}</div>
        <div class="sf-title">{html.escape(title)}</div>
        <div class="sf-subtitle">{html.escape(subtitle)}</div>
        <div class="sf-rule"></div>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str, note: str, *, color: str = "teal") -> str:
    safe_color = COLORS.get(color, COLORS["teal"])
    return f"""
    <div class="sf-card">
      <div class="sf-card-label">{html.escape(label)}</div>
      <div class="sf-card-value" style="color:{safe_color}">{html.escape(value)}</div>
      <div class="sf-card-note">{html.escape(note)}</div>
    </div>
    """


def callout(text: str, *, kind: str = "warning") -> None:
    css_class = "sf-callout"
    if kind == "safe":
        css_class += " sf-safe"
    elif kind == "danger":
        css_class += " sf-danger"
    st.markdown(
        f'<div class="{css_class}">{html.escape(text)}</div>',
        unsafe_allow_html=True,
    )


def section_title(title: str, caption: str | None = None) -> None:
    st.markdown(f'<div class="sf-section">{html.escape(title)}</div>', unsafe_allow_html=True)
    if caption:
        st.caption(caption)


def chart_layout(*, height: int = 380, **kwargs: Any) -> dict[str, Any]:
    layout: dict[str, Any] = {
        "height": height,
        "margin": {"l": 20, "r": 20, "t": 45, "b": 20},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(7,20,33,.2)",
        "font": {"family": "Inter, Segoe UI", "color": COLORS["muted"], "size": 12},
        "legend": {"orientation": "h", "y": 1.12, "x": 0},
        "legend_title_text": "",
        "hoverlabel": {"bgcolor": COLORS["panel"], "font_color": COLORS["text"]},
        "xaxis": {"gridcolor": "rgba(140,165,184,.08)", "zeroline": False},
        "yaxis": {"gridcolor": "rgba(140,165,184,.08)", "zeroline": False},
    }
    layout.update(kwargs)
    return layout


def style_figure(figure: go.Figure, *, height: int = 380, **kwargs: Any) -> go.Figure:
    figure.update_layout(**chart_layout(height=height, **kwargs))
    return figure


@st.cache_resource(show_spinner=False)
def cached_product(root_text: str, profile: str) -> tuple[ProductArtifacts, ProductRepository]:
    root = Path(root_text)
    bundle = load_config_bundle(profile, root)
    artifacts = resolve_product_artifacts(bundle, project_root=root)
    return artifacts, ProductRepository(artifacts)


@st.cache_data(show_spinner=False, ttl=3600)
def cached_dataset(root_text: str, profile: str, name: str, argument: str = "") -> Any:
    _, repository = cached_product(root_text, profile)
    method = getattr(repository, name)
    return method(argument) if argument else method()


@st.cache_resource(show_spinner="Carregando modelos e envelope do contexto…")
def cached_scenario_runtime(
    root_text: str,
    profile: str,
    context_id: str,
) -> InteractiveScenarioRuntime:
    artifacts, _ = cached_product(root_text, profile)
    return build_interactive_runtime(artifacts, context_id)


def load_app_context(source_file: str) -> tuple[Path, str, ProductArtifacts, ProductRepository]:
    root = project_root_from_file(Path(source_file))
    profile = os.environ.get("STEELFLOW_PROFILE", "mvp")
    try:
        artifacts, repository = cached_product(str(root), profile)
    except (ProductArtifactError, OSError, ValueError) as exc:
        page_header(
            "Artifact readiness",
            "Dados da demonstração ainda não estão disponíveis",
            "A interface iniciou corretamente, mas precisa dos artefatos "
            "reproduzíveis do pipeline.",
        )
        callout(str(exc), kind="danger")
        st.code(
            "\n".join(
                [
                    f"python -m steelflow generate --profile {profile}",
                    f"python -m steelflow build-db --profile {profile}",
                    f"python -m steelflow build-features --profile {profile}",
                    f"python -m steelflow train --profile {profile}",
                    f"python -m steelflow evaluate --profile {profile}",
                    f"python -m steelflow optimize-demo --profile {profile}",
                ]
            ),
            language="bash",
        )
        st.stop()
        raise RuntimeError("unreachable") from exc
    return root, profile, artifacts, repository


def sidebar_context(artifacts: ProductArtifacts, page_name: str) -> None:
    with st.sidebar:
        st.markdown("## STEELFLOW / AI")
        st.caption("Decision-support digital twin · sintético")
        st.markdown(
            '<span class="sf-badge"><span class="sf-dot"></span>PIPELINE READY</span>',
            unsafe_allow_html=True,
        )
        st.markdown("---")
        st.caption("PÁGINA ATUAL")
        st.markdown(f"**{page_name}**")
        st.caption("PERFIL")
        st.code(artifacts.profile)
        st.caption("EXECUÇÃO")
        st.code(artifacts.simulation_run_id[-18:])
        st.markdown("---")
        st.caption(
            "100% dados sintéticos · limites internos simulados · sem API 5CT · "
            "sem comando de máquina"
        )


def format_number(value: float, decimals: int = 1) -> str:
    return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def aggregate_executive(frame: pd.DataFrame) -> dict[str, float]:
    good_tonnes = float(frame["good_tonnes"].sum())
    productive_hours = float(frame["productive_hours"].sum())
    energy = float(frame["energy_kwh"].sum())
    tube_count = float(frame["tube_count"].sum())
    return {
        "tbh": good_tonnes / max(productive_hours, 1e-12),
        "fpy": float((frame["fpy"] * frame["tube_count"]).sum()) / max(tube_count, 1e-12),
        "oee": float((frame["oee"] * frame["tube_count"]).sum()) / max(tube_count, 1e-12),
        "energy": energy / max(good_tonnes, 1e-12),
        "downtime": float(frame["unplanned_downtime_minutes"].sum()),
        "good_tonnes": good_tonnes,
    }
