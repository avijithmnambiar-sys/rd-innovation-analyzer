"""Small presentation helpers shared by Member 1's pages."""

import streamlit as st

CHART_COLORS = ["#0F766E", "#24466B", "#D97732", "#5286B0", "#647553", "#7C6599",
                "#299C94", "#6B7F98", "#A95532", "#35618B", "#88733B", "#A87C96"]


def apply_style():
    st.markdown("""
        <style>
        .block-container { max-width: 1280px; padding-top: 4.5rem; padding-bottom: 3rem; }
        h1, h2, h3 { color: #172B4D; }
        h1 { font-size: 2.25rem !important; line-height: 1.2 !important; }
        h2 { font-size: 1.5rem !important; padding-top: 1rem !important; }
        h3 { font-size: 1.1rem !important; }
        [data-testid="stMetric"] {
            background: white; border: 1px solid #DCE4EE; border-left: 4px solid #0F766E;
            border-radius: 10px; padding: 1rem; height: 100%;
        }
        [data-testid="stMetricValue"] { font-size: 1.65rem; color: #172B4D; }
        [data-testid="stForm"] { background: white; }
        [data-testid="stExpander"] { background: white; border-radius: 10px; }
        .st-key-home_sdg, [class*="st-key-home_module_"], .st-key-rd_filters { background: white; }
        @media (max-width: 640px) {
            h1 { font-size: 1.8rem !important; }
        }
        </style>
    """, unsafe_allow_html=True)
    st.sidebar.markdown("**Global R&D Analyzer**")
    st.sidebar.caption("Research spending · Patents · Institutions · Infrastructure")
    st.sidebar.divider()
    st.sidebar.caption("SDG 9 · Industry, Innovation & Infrastructure")


def style_chart(figure):
    figure.update_layout(
        font={"family": "Arial, sans-serif", "color": "#172B4D", "size": 13},
        title={"font": {"size": 17}, "x": 0},
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        margin={"l": 20, "r": 20, "t": 65, "b": 25},
    )
    figure.update_xaxes(gridcolor="#EAF0F7", zeroline=False)
    figure.update_yaxes(gridcolor="#EAF0F7", zeroline=False)
    return figure
