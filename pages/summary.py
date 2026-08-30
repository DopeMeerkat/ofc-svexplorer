"""
Summary page for the UCONN OFC SV Browser application.
"""

import math

from dash import Input, Output, callback, dcc, html, no_update
import plotly.graph_objects as go

from utils.styling import UCONN_LIGHT_BLUE, UCONN_NAVY, body_text_style, page_title_style, section_title_style, uconn_styles


def _circle_points(center_x, center_y, radius, steps=180):
    return [
        (
            center_x + radius * math.cos(2 * math.pi * index / steps),
            center_y + radius * math.sin(2 * math.pi * index / steps),
        )
        for index in range(steps + 1)
    ]


def _lens_points(left_center_x, right_center_x, radius, center_y=0, steps=80):
    half_distance = (right_center_x - left_center_x) / 2
    intersection_y = math.sqrt((radius * radius) - (half_distance * half_distance))
    upper_angle_left = math.atan2(intersection_y, half_distance)
    lower_angle_left = -upper_angle_left
    upper_angle_right = math.pi - upper_angle_left
    lower_angle_right = math.pi + upper_angle_left

    left_arc = [
        (
            left_center_x + radius * math.cos(lower_angle_left + (upper_angle_left - lower_angle_left) * index / steps),
            center_y + radius * math.sin(lower_angle_left + (upper_angle_left - lower_angle_left) * index / steps),
        )
        for index in range(steps + 1)
    ]
    right_arc = [
        (
            right_center_x + radius * math.cos(upper_angle_right + (lower_angle_right - upper_angle_right) * index / steps),
            center_y + radius * math.sin(upper_angle_right + (lower_angle_right - upper_angle_right) * index / steps),
        )
        for index in range(steps + 1)
    ]
    return left_arc + right_arc + [left_arc[0]]


def _lens_marker_points(spacing=0.22):
    marker_x = []
    marker_y = []
    y = -1.35
    while y <= 1.35:
        x = -0.78
        while x <= 0.78:
            if (x + 0.8) ** 2 + y ** 2 <= 1.6 ** 2 and (x - 0.8) ** 2 + y ** 2 <= 1.6 ** 2:
                marker_x.append(x)
                marker_y.append(y)
            x += spacing
        y += spacing
    return marker_x, marker_y


def _build_overlap_venn_figure():
    left_points = _circle_points(-0.8, 0, 1.6)
    right_points = _circle_points(0.8, 0, 1.6)
    lens_points = _lens_points(-0.8, 0.8, 1.6)
    lens_marker_x, lens_marker_y = _lens_marker_points()

    figure = go.Figure()
    figure.add_trace(go.Scatter(
        x=[point[0] for point in left_points],
        y=[point[1] for point in left_points],
        mode="lines",
        fill="toself",
        name="OFC literature genes",
        hovertemplate="OFC genes in the literature<extra></extra>",
        line={"color": UCONN_LIGHT_BLUE, "width": 3},
        fillcolor="rgba(0, 114, 206, 0.30)",
    ))
    figure.add_trace(go.Scatter(
        x=[point[0] for point in right_points],
        y=[point[1] for point in right_points],
        mode="lines",
        fill="toself",
        name="Child SV genes",
        hovertemplate="SV genes more than 1 child<extra></extra>",
        line={"color": UCONN_NAVY, "width": 3},
        fillcolor="rgba(0, 39, 76, 0.28)",
    ))
    figure.add_trace(go.Scatter(
        x=[point[0] for point in lens_points],
        y=[point[1] for point in lens_points],
        mode="lines",
        fill="toself",
        name="41 overlap genes",
        customdata=["overlap_table"] * len(lens_points),
        hovertemplate="41 overlap genes<br>Click to inspect the table<extra></extra>",
        line={"color": UCONN_NAVY, "width": 2},
        fillcolor="rgba(0, 39, 76, 0.72)",
    ))
    figure.add_trace(go.Scatter(
        x=lens_marker_x,
        y=lens_marker_y,
        mode="markers",
        name="41 overlap genes click target",
        customdata=["overlap_table"] * len(lens_marker_x),
        hovertemplate="41 overlap genes<br>Click to inspect the table<extra></extra>",
        marker={"size": 18, "color": "rgba(0, 39, 76, 0.01)"},
        showlegend=False,
    ))
    figure.add_trace(go.Scatter(
        x=[-1.55, 1.55],
        y=[0.22, 0.22],
        mode="text",
        text=["OFC genes<br>in literature", "SV genes<br>more than 1 child"],
        textfont={"size": 15, "color": UCONN_NAVY},
        hoverinfo="skip",
        showlegend=False,
    ))
    figure.add_trace(go.Scatter(
        x=[0],
        y=[0],
        mode="text",
        text=["<b>41<br>genes</b>"],
        customdata=["overlap_table"],
        hovertemplate="41 overlap genes<br>Click to inspect the table<extra></extra>",
        textfont={"size": 20, "color": "white"},
        showlegend=False,
    ))
    figure.update_layout(
        clickmode="event+select",
        dragmode=False,
        hovermode="closest",
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
        height=320,
        paper_bgcolor="#f8fbfd",
        plot_bgcolor="#f8fbfd",
        showlegend=False,
        xaxis={"visible": False, "range": [-2.7, 2.7], "fixedrange": True},
        yaxis={"visible": False, "range": [-1.9, 1.9], "scaleanchor": "x", "scaleratio": 1, "fixedrange": True},
    )
    return figure


def page_layout():
    """
    Create the summary page layout

    Returns:
        dash.html.Div: Summary page layout
    """
    return html.Div([
        html.H2('OFC Structural Variation Explorer', style=page_title_style),
        html.P(
            "This portal summarizes structural variation (SV) calls and regulatory annotations for an orofacial cleft cohort from the Gabriella Miller Kids First program. The site is designed for cohort-level review of SV burden, gene overlap, regulatory context, pathway membership, and curated case examples.",
            style=body_text_style,
        ),
        html.P(
            "The analysis emphasizes deletions, duplications, insertions, and inversions that intersect annotated genes, exons, active enhancer candidates, promoters, insulators, and no-cleft embryo cCREs. Aggregate views are used throughout the public-facing pages to avoid exposing sample identifiers.",
            style=body_text_style,
        ),
        html.P(
            "Use Database Overview for cohort summaries, Table Inspection for curated gene-level evidence, IGV/Population for genome browser review, Pathway for gene-set context, and Case Study for publication-oriented examples.",
            style=body_text_style,
        ),
        html.H3('OFC Literature and SV-Gene Overlap', style={**section_title_style, 'marginTop': '30px'}),
        dcc.Graph(
            id='summary-overlap-venn',
            figure=_build_overlap_venn_figure(),
            config={'displayModeBar': False, 'responsive': True},
            style={
                'maxWidth': '680px', 'margin': '0 auto 8px auto',
                'border': f'1px solid {UCONN_LIGHT_BLUE}', 'borderRadius': '8px',
                'overflow': 'hidden',
            },
        ),
        html.P('Select the overlap region to open the curated 41-gene table.', style={'fontSize': '14px', 'color': UCONN_NAVY, 'textAlign': 'center'}),
    ], style={**uconn_styles['content'], 'maxWidth': '900px', 'margin': '40px auto 0 auto'})


@callback(
    Output('url', 'pathname', allow_duplicate=True),
    Output('url', 'search', allow_duplicate=True),
    Input('summary-overlap-venn', 'clickData'),
    prevent_initial_call=True,
)
def route_from_overlap_venn(click_data):
    if not click_data:
        return no_update, no_update

    point = (click_data.get('points') or [{}])[0]
    if point.get('customdata') == 'overlap_table':
        return '/table', ''

    return no_update, no_update
