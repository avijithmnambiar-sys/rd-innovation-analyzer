"""Small presentation helpers shared by Member 1's pages."""

import streamlit as st

# Mid-tone hues that keep >= 3:1 contrast on both the light and dark chart surfaces.
CHART_COLORS = ["#12958A", "#D2691E", "#3D7CC9", "#5E9E2E", "#C0504D", "#8A64CF",
                "#B0851A", "#D0588F", "#2E9CC0", "#9C8C24", "#6E73D6", "#C46A3A"]


def apply_style():
    # Colours are derived from the inherited theme text colour (currentColor), so the
    # same rules work in both the light and dark themes defined in .streamlit/config.toml.
    st.markdown("""
        <style>
        .block-container { max-width: 1280px; padding-top: 4.5rem; padding-bottom: 3rem; }
        h1 { font-size: 2.25rem !important; line-height: 1.2 !important; }
        h2 { font-size: 1.5rem !important; padding-top: 1rem !important; }
        h3 { font-size: 1.1rem !important; }
        [data-testid="stMetric"] {
            background: color-mix(in srgb, currentColor 4%, transparent);
            border: 1px solid color-mix(in srgb, currentColor 15%, transparent);
            border-left: 4px solid #12958A; border-radius: 10px; padding: 1rem; height: 100%;
        }
        [data-testid="stMetricValue"] { font-size: 1.65rem; }
        [data-testid="stForm"], [data-testid="stExpander"],
        .st-key-home_sdg, [class*="st-key-home_module_"], .st-key-rd_filters {
            background: color-mix(in srgb, currentColor 3%, transparent);
        }
        [data-testid="stExpander"] { border-radius: 10px; }
        @media (max-width: 640px) {
            h1 { font-size: 1.8rem !important; }
        }
        </style>
    """, unsafe_allow_html=True)
    st.sidebar.markdown("**Global R&D Analyzer**")
    st.sidebar.caption("Research spending · Patents · Institutions · Infrastructure")
    st.sidebar.divider()
    st.sidebar.caption("SDG 9 · Industry, Innovation & Infrastructure")
    st.sidebar.caption("Switch light/dark theme: ⋮ menu › Settings")


def style_chart(figure):
    # Backgrounds, text and grid colours are left to Streamlit's chart theme so they
    # follow the active light or dark theme.
    figure.update_layout(
        font={"family": "Arial, sans-serif", "size": 13},
        title={"font": {"size": 17}, "x": 0},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 20, "r": 20, "t": 65, "b": 25},
    )
    figure.update_xaxes(zeroline=False)
    figure.update_yaxes(zeroline=False)
    return figure
