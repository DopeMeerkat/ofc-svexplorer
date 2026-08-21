"""Database overview page with cached static metrics and bar graph exploration."""

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, callback, dash_table, dcc, html

from pages.visualization_uploader import (
    BAR_X_AXES,
    BAR_Y_METRICS,
    _chromosome_category_sort_key,
    _create_grouped_bar_figure,
    load_bar_graph_data,
    processing_error,
)
from utils.styling import UCONN_LIGHT_BLUE, UCONN_NAVY, muted_text_style, page_title_style, uconn_styles


CACHE_DIR = Path(__file__).resolve().parents[1] / "database"
CARD_STYLE = {
    "backgroundColor": "#FFFFFF",
    "border": "1px solid #D8E2EA",
    "borderRadius": "10px",
    "padding": "18px",
    "boxShadow": "0 2px 8px rgba(0,0,0,0.04)",
}
CHART_HEIGHT = 380
SMALL_CHART_HEIGHT = 260
SV_TYPE_ORDER = ["DEL", "INS", "INV", "DUP"]
RACE_GROUP_ORDER = ["African", "Asian"]
ROLE_GROUP_ORDER = ["Child", "Parents", "Background population"]
PHENOTYPE_GROUP_ORDER = ["Affected", "Normal", "CL", "CLP"]
HG38_CHROMOSOME_LENGTHS = {
    "chr1": 248956422,
    "chr2": 242193529,
    "chr3": 198295559,
    "chr4": 190214555,
    "chr5": 181538259,
    "chr6": 170805979,
    "chr7": 159345973,
    "chr8": 145138636,
    "chr9": 138394717,
    "chr10": 133797422,
    "chr11": 135086622,
    "chr12": 133275309,
    "chr13": 114364328,
    "chr14": 107043718,
    "chr15": 101991189,
    "chr16": 90338345,
    "chr17": 83257441,
    "chr18": 80373285,
    "chr19": 58617616,
    "chr20": 64444167,
    "chr21": 46709983,
    "chr22": 50818468,
    "chrX": 156040895,
    "chrY": 57227415,
}


METRIC_TOOLTIPS = {
    "Families": "COUNT(DISTINCT family_id) from phenotype.",
    "Samples": "COUNT(*) from phenotype.",
    "Cases (Affected)": "COUNT(*) from phenotype where affected = 1.",
    "Parents": "COUNT(*) from phenotype where child = 0.",
    "Background Controls": "COUNT(DISTINCT sample) from background_svs.",
    "Unique SVs": "COUNT(DISTINCT id) from phenotype_svs.",
    "Annotated Genes": "COUNT(*) from genes.",
    "Regulatory Elements": "Distinct genomic intervals across active enhancers, promoters, insulators, and no-cleft embryo cCREs.",
}


def _load_csv(filename):
    path = CACHE_DIR / filename
    if not path.is_file():
        return pd.DataFrame()
    return pd.read_csv(path)


def _format_int(value):
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "N/A"


def _chromosome_order(values):
    return sorted([str(value) for value in values], key=_chromosome_category_sort_key)


def _table(dataframe, page_size=10):
    if dataframe.empty:
        return html.P("Cached data is not available. Run database/generate_database_overview.py.", style={"color": "#A61B1B"})
    return dash_table.DataTable(
        data=dataframe.to_dict("records"),
        columns=[{"name": column.replace("_", " ").title(), "id": column} for column in dataframe.columns],
        page_size=page_size,
        sort_action="native",
        filter_action="native",
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "8px", "maxWidth": "320px"},
        style_header={"backgroundColor": UCONN_LIGHT_BLUE, "fontWeight": "bold"},
    )


def _annotation_overlap_table(dataframe, page_size=8):
    if dataframe.empty:
        return html.P("Cached data is not available. Run database/generate_database_overview.py.", style={"color": "#A61B1B"})
    display = dataframe.copy()
    for column in display.columns:
        if column.startswith("pct_"):
            display[column] = pd.to_numeric(display[column], errors="coerce").map(lambda value: "N/A" if pd.isna(value) else f"{value:.1%}")
    labels = {
        "annotation": "Genomic Feature",
        "overlap_records": "Overlap Records",
        "distinct_sv_gene_pairs": "Distinct SV-Gene Pairs",
        "distinct_svs": "Distinct SVs",
        "distinct_genes": "Distinct Genes",
        "distinct_annotation_records": "Distinct GF Records",
        "pct_unique_svs": "% Unique SVs",
        "pct_annotated_genes": "% Annotated Genes",
        "pct_genomic_feature_records": "% GF Records",
    }
    return dash_table.DataTable(
        data=display.to_dict("records"),
        columns=[{"name": labels.get(column, column.replace("_", " ").title()), "id": column} for column in display.columns],
        page_size=page_size,
        sort_action="native",
        filter_action="native",
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "8px", "maxWidth": "320px"},
        style_header={"backgroundColor": UCONN_LIGHT_BLUE, "fontWeight": "bold"},
    )


def _metric_cards(summary):
    cards = [
        ("Families", summary.get("family_count")),
        ("Samples", summary.get("individual_count")),
        ("Cases (Affected)", summary.get("affected_case_count")),
        ("Parents", summary.get("parent_count")),
        ("Background Controls", summary.get("background_control_count")),
        ("Unique SVs", summary.get("unique_phenotype_svs")),
        ("Annotated Genes", summary.get("annotated_gene_count")),
        ("Regulatory Elements", summary.get("regulatory_element_count")),
    ]
    return html.Div([
        html.Div([
            html.Div(label, style={"fontSize": "13px", "color": "#52606D", "marginBottom": "6px"}),
            html.Div(_format_int(value), style={"fontSize": "26px", "fontWeight": "700", "color": UCONN_NAVY}),
        ], style=CARD_STYLE, title=METRIC_TOOLTIPS.get(label, ""))
        for label, value in cards
    ], style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(190px, 1fr))", "gap": "14px"})


def _load_summary():
    path = CACHE_DIR / "overview_summary.json"
    if not path.is_file():
        return {}
    return pd.read_json(path, typ="series").to_dict()


def _horizontal_bar_figure(dataframe, y_col, x_col, title, y_label, x_label, color=UCONN_NAVY):
    if dataframe.empty:
        return px.bar(title=title)
    fig = px.bar(
        dataframe,
        x=x_col,
        y=y_col,
        orientation="h",
        color_discrete_sequence=[color],
        labels={y_col: y_label, x_col: x_label},
        title=title,
    )
    fig.update_layout(
        showlegend=False,
        height=CHART_HEIGHT,
        margin=dict(l=120, r=30, t=70, b=50),
        plot_bgcolor="#FFFFFF",
        yaxis=dict(tickangle=0),
        xaxis=dict(title_font=dict(size=14), tickfont=dict(size=12)),
    )
    return fig


def _vertical_bar_figure(dataframe, x_col, y_col, title, x_label, y_label, color=UCONN_NAVY, category_order=None):
    if dataframe.empty:
        return px.bar(title=title)
    kwargs = {}
    if category_order:
        kwargs["category_orders"] = {x_col: category_order}
    fig = px.bar(
        dataframe,
        x=x_col,
        y=y_col,
        color_discrete_sequence=[color],
        labels={x_col: x_label, y_col: y_label},
        title=title,
        **kwargs,
    )
    fig.update_layout(
        showlegend=False,
        height=430,
        margin=dict(l=60, r=20, t=70, b=80),
        plot_bgcolor="#FFFFFF",
        xaxis=dict(
            title_font=dict(size=14),
            tickfont=dict(size=12),
            tickangle=-90,
        ),
        yaxis=dict(
            title_font=dict(size=14),
            tickfont=dict(size=12),
        ),
    )
    return fig


def _individual_figure(dataframe):
    if dataframe.empty:
        return px.bar(title="Samples")
    total = dataframe["count"].sum()
    fig = _horizontal_bar_figure(
        dataframe, "group", "ratio", "Samples", "Group", "% of Displayed Samples"
    )
    fig.update_xaxes(tickformat=".0%")
    fig.update_traces(customdata=dataframe[["count"]], hovertemplate="%{y}<br>%{x:.1%} of displayed samples<br>%{customdata[0]:,} / " + f"{total:,}" + " samples<extra></extra>")
    return fig


def _individual_sv_figure(dataframe):
    if dataframe.empty:
        return px.bar(title="SV Calls per Sample")
    fig = _horizontal_bar_figure(
        dataframe, "group", "svs_per_sample", "SV Calls per Sample", "Group", "SV Calls per Sample",
        color=UCONN_LIGHT_BLUE,
    )
    fig.update_traces(customdata=dataframe[["count", "samples"]], hovertemplate="%{y}<br>%{x:,.1f} SV calls/sample<br>%{customdata[0]:,} SV rows / %{customdata[1]:,} samples<extra></extra>")
    return fig


def _sv_type_figure(dataframe):
    if dataframe.empty:
        return px.bar(title="SV Type Counts")
    working = dataframe.sort_values("structural_variants", ascending=True)
    total = int(working["structural_variants"].sum())
    fig = _horizontal_bar_figure(
        working, "sv_type", "ratio", "SV Type Distribution", "SV Type", "% of SV Rows",
        color="#45B7D1",
    )
    fig.update_xaxes(tickformat=".0%")
    fig.update_traces(customdata=working[["structural_variants"]], hovertemplate="%{y}<br>%{x:.1%} of SV rows<br>%{customdata[0]:,} / " + f"{total:,}" + " SV rows<extra></extra>")
    return fig


def _phenotype_figure(dataframe):
    if dataframe.empty:
        return px.bar(title="Phenotype Distribution")
    total = int(dataframe["count"].sum())
    fig = _horizontal_bar_figure(
        dataframe, "phenotype", "ratio", "Phenotype Distribution", "Phenotype", "% of Samples",
        color="#96CEB4",
    )
    fig.update_xaxes(tickformat=".0%")
    fig.update_traces(customdata=dataframe[["count"]], hovertemplate="%{y}<br>%{x:.1%} of samples<br>%{customdata[0]:,} / " + f"{total:,}" + " samples<extra></extra>")
    return fig


def _sv_region_figure(dataframe):
    order = ["Exonic", "Intronic", "Promoter", "Enhancer", "Insulator", "Intergenic"]
    if dataframe.empty:
        return px.bar(title="Where SVs Occur")
    total = int(round(dataframe.loc[dataframe["region"].isin(["Exonic", "Intronic", "Intergenic"]), "sv_count"].sum())) or int(dataframe["sv_count"].max())
    fig = _vertical_bar_figure(
        dataframe, "region", "ratio", "Where SVs Occur", "Region", "% of Unique SVs",
        color=UCONN_LIGHT_BLUE,
        category_order=order,
    )
    fig.update_yaxes(tickformat=".0%")
    fig.update_traces(customdata=dataframe[["sv_count"]], hovertemplate="%{x}<br>%{y:.1%} of unique SVs<br>%{customdata[0]:,} / " + f"{total:,}" + " unique SVs<extra></extra>")
    return fig


def _chromosome_figure(dataframe):
    if dataframe.empty:
        return px.bar(title="SVs by Chromosome")
    working = dataframe.copy()
    working["chrom"] = working["chrom"].astype(str)
    chrom_order = _chromosome_order(working["chrom"].unique())
    working = working.set_index("chrom").reindex(chrom_order).reset_index()
    working["chromosome_length_mb"] = working["chrom"].map(HG38_CHROMOSOME_LENGTHS).fillna(0) / 1_000_000
    total = int(working["structural_variants"].sum())
    fig = go.Figure()
    fig.add_bar(
        x=working["chrom"],
        y=working["structural_variants"],
        name="Unique SVs",
        marker_color=UCONN_LIGHT_BLUE,
        customdata=working[["ratio"]],
        hovertemplate=(
            "Chromosome: %{x}<br>"
            "Unique SVs: %{y:,}<br>"
            "% of unique SVs: %{customdata[0]:.1%}"
            "<extra></extra>"
        ),
    )
    fig.add_scatter(
        x=working["chrom"],
        y=working["chromosome_length_mb"],
        name="Chromosome length",
        mode="lines+markers",
        yaxis="y2",
        line={"color": UCONN_NAVY, "width": 3},
        marker={"size": 7},
        hovertemplate="Chromosome: %{x}<br>Length: %{y:.1f} Mb<extra></extra>",
    )
    fig.update_layout(
        title="SVs by Chromosome and Chromosome Length",
        height=430,
        margin=dict(l=70, r=80, t=70, b=70),
        plot_bgcolor="#FFFFFF",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        xaxis={
            "title": "Chromosome",
            "categoryorder": "array",
            "categoryarray": chrom_order,
            "tickangle": -90,
        },
        yaxis={"title": f"Unique SVs (n={total:,})"},
        yaxis2={
            "title": "Chromosome Length (Mb)",
            "overlaying": "y",
            "side": "right",
            "showgrid": False,
        },
    )
    return fig


def _length_figure(dataframe):
    if dataframe.empty:
        return px.bar(title="SV Length Distribution")
    order = ["0-50 bp", "51-100 bp", "101 bp-1 kb", "1-10 kb", "10-100 kb", "100 kb-1 Mb", ">1 Mb"]
    fig = px.bar(
        dataframe,
        x="length_bin",
        y="structural_variants",
        category_orders={"length_bin": order},
        labels={"length_bin": "SV Length", "structural_variants": "Structural Variants"},
        title="SV Length Distribution",
        color_discrete_sequence=[UCONN_LIGHT_BLUE],
    )
    fig.update_layout(height=430, margin=dict(l=60, r=20, t=70, b=70), plot_bgcolor="#FFFFFF")
    return fig


def _cohort_figure(dataframe):
    if dataframe.empty:
        return px.bar(title="Cohort Breakdown")
    fig = px.bar(
        dataframe,
        x="value",
        y="samples",
        color="category",
        facet_col="category",
        facet_col_wrap=3,
        labels={"value": "Group", "samples": "Samples", "category": "Category"},
        title="Cohort Breakdown",
    )
    fig.update_xaxes(matches=None, showticklabels=True)
    fig.update_layout(height=620, margin=dict(l=60, r=20, t=80, b=80), plot_bgcolor="#FFFFFF")
    return fig


def _sv_type_order(values):
    present = [str(value) for value in values if pd.notna(value)]
    ordered = [value for value in SV_TYPE_ORDER if value in present]
    ordered.extend(sorted(value for value in present if value not in ordered))
    return ordered


def _sv_type_group_figure(dataframe, group):
    if dataframe.empty:
        return px.bar(title=group)
    group_df = dataframe[dataframe["group"] == group].copy()
    if group_df.empty:
        return px.bar(title=group)

    order = _sv_type_order(dataframe["sv_type"].unique())
    group_df = group_df.set_index("sv_type").reindex(order).reset_index()
    group_df["group"] = group
    for column in ["raw_count", "group_total", "normalized_percent", "unique_samples", "count_per_sample"]:
        group_df[column] = pd.to_numeric(group_df[column], errors="coerce").fillna(0)
    group_df["percent_label"] = group_df["normalized_percent"].map(lambda value: f"{value:.1f}%")

    fig = px.bar(
        group_df,
        x="normalized_percent",
        y="sv_type",
        text="percent_label",
        orientation="h",
        title=group,
        labels={"normalized_percent": "% of SV Rows", "sv_type": "SV Type"},
        color_discrete_sequence=[UCONN_LIGHT_BLUE],
        category_orders={"sv_type": order},
    )
    fig.update_xaxes(range=[0, 100], ticksuffix="%")
    fig.update_layout(
        showlegend=False,
        height=SMALL_CHART_HEIGHT,
        margin=dict(l=70, r=20, t=52, b=44),
        plot_bgcolor="#FFFFFF",
        yaxis={"categoryorder": "array", "categoryarray": order[::-1]},
    )
    fig.update_traces(textposition="auto", textfont=dict(size=12), cliponaxis=False)
    fig.update_traces(
        customdata=group_df[["group", "raw_count", "group_total", "unique_samples", "count_per_sample"]],
        hovertemplate=(
            "Group: %{customdata[0]}<br>"
            "SV type: %{y}<br>"
            "Raw count: %{customdata[1]:,.0f}<br>"
            "Total SVs in group: %{customdata[2]:,.0f}<br>"
            "Percent of group: %{x:.1f}%<br>"
            "Unique samples: %{customdata[3]:,.0f}<br>"
            "SV calls/sample: %{customdata[4]:,.1f}"
            "<extra></extra>"
        ),
    )
    return fig


def _sv_type_group_section(dataframe):
    if dataframe.empty:
        return html.Div([
            html.H3("SV Type Distributions by Group", style={"color": UCONN_NAVY}),
            html.P("Cached data is not available. Run database/generate_database_overview.py.", style={"color": "#A61B1B"}),
        ], style={**CARD_STYLE, "marginTop": "18px"})

    race_df = dataframe[dataframe["comparison"] == "Race / ancestry comparison"]
    role_df = dataframe[dataframe["comparison"] == "Role / phenotype comparison"]
    race_groups = [group for group in RACE_GROUP_ORDER if group in set(race_df["group"])]
    role_groups = [group for group in ROLE_GROUP_ORDER if group in set(role_df["group"])]
    phenotype_groups = [group for group in PHENOTYPE_GROUP_ORDER if group in set(role_df["group"])]

    return html.Div([
        html.H3("SV Type Distributions by Group", style={"color": UCONN_NAVY, "marginBottom": "6px"}),
        html.P(
            "Each chart shows SV row-type composition within a group. Bar length is normalized percentage; hover text includes raw counts, total SV rows, unique samples, and SV calls per sample.",
            style={"fontSize": "13px", "color": "#52606D", "marginBottom": "16px"},
        ),
        html.H4("Race / Ancestry Comparison", style={"color": UCONN_NAVY, "margin": "0 0 10px 0"}),
        html.Div([
            dcc.Graph(figure=_sv_type_group_figure(race_df, group), config={"displayModeBar": False})
            for group in race_groups
        ], style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(280px, 1fr))", "gap": "14px"}),
        html.H4("Role Comparison", style={"color": UCONN_NAVY, "margin": "22px 0 10px 0"}),
        html.Div([
            dcc.Graph(figure=_sv_type_group_figure(role_df, group), config={"displayModeBar": False})
            for group in role_groups
        ], style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(280px, 1fr))", "gap": "14px"}),
        html.H4("Phenotype / Status Comparison", style={"color": UCONN_NAVY, "margin": "22px 0 10px 0"}),
        html.Div([
            dcc.Graph(figure=_sv_type_group_figure(role_df, group), config={"displayModeBar": False})
            for group in phenotype_groups
        ], style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(280px, 1fr))", "gap": "14px"}),
    ], style={**CARD_STYLE, "marginTop": "18px"})


def _gene_exon_figure(dataframe):
    if dataframe.empty:
        return px.bar(title="Genes and Exons by Chromosome")
    working = dataframe.copy()
    working["chrom"] = working["chrom"].astype(str)
    long_df = working.melt(id_vars="chrom", value_vars=["genes", "exons"], var_name="annotation", value_name="count")
    fig = px.bar(
        long_df,
        x="chrom",
        y="count",
        color="annotation",
        barmode="group",
        category_orders={"chrom": _chromosome_order(working["chrom"].unique())},
        labels={"chrom": "Chromosome", "count": "Records", "annotation": "Annotation"},
        title="Genes and Exons by Chromosome",
    )
    fig.update_layout(height=460, margin=dict(l=60, r=20, t=70, b=70), plot_bgcolor="#FFFFFF")
    return fig


def _static_layout():
    summary = _load_summary()
    table_counts = _load_csv("table_counts.csv")
    cohort_counts = _load_csv("cohort_counts.csv")
    sv_count_statistics = _load_csv("sv_count_statistics.csv")
    sv_type_counts = _load_csv("sv_type_counts.csv")
    chromosome_distribution = _load_csv("chromosome_distribution.csv")
    sv_length_bins = _load_csv("sv_length_bins.csv")
    gene_exon_by_chromosome = _load_csv("gene_exon_by_chromosome.csv")
    sv_gene_summary = _load_csv("sv_gene_summary.csv")
    sv_gene_annotation_overlap = _load_csv("sv_gene_annotation_overlap.csv")
    gene_annotation_overlap = _load_csv("gene_annotation_overlap.csv")
    individual_group_counts = _load_csv("individual_group_counts.csv")
    individual_sv_counts = _load_csv("individual_sv_counts.csv")
    phenotype_distribution = _load_csv("phenotype_distribution.csv")
    sv_region_counts = _load_csv("sv_region_counts.csv")
    sv_type_group_distribution = _load_csv("sv_type_group_distribution.csv")

    return html.Div([
        html.P(
            "Cached aggregate summaries describe cohort composition, SV burden, genomic context, and annotation overlap. Individual sample identifiers are not displayed.",
            style={**muted_text_style, "marginBottom": "18px"},
        ),
        _metric_cards(summary),
        html.Div([
            dcc.Graph(figure=_individual_figure(individual_group_counts), config={"displayModeBar": False}),
            dcc.Graph(figure=_individual_sv_figure(individual_sv_counts), config={"displayModeBar": False}),
            dcc.Graph(figure=_sv_type_figure(sv_type_counts), config={"displayModeBar": False}),
            dcc.Graph(figure=_phenotype_figure(phenotype_distribution), config={"displayModeBar": False}),
        ], style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(320px, 1fr))", "gap": "16px", "marginTop": "18px"}),
        html.Div([
            dcc.Graph(figure=_sv_region_figure(sv_region_counts), config={"displayModeBar": False}),
            dcc.Graph(figure=_chromosome_figure(chromosome_distribution), config={"displayModeBar": False}),
        ], style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(420px, 1fr))", "gap": "16px", "marginTop": "18px"}),
        html.Div([
            html.Div([html.H3("SV Count Statistics", style={"color": UCONN_NAVY}), _table(sv_count_statistics, page_size=8)], style=CARD_STYLE),
            html.Div([html.H3("SV-Gene Overlap Summary", style={"color": UCONN_NAVY}), _table(sv_gene_summary, page_size=5)], style=CARD_STYLE),
        ], style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(360px, 1fr))", "gap": "16px", "marginTop": "18px"}),
        html.Div([
            html.Div([
                html.H3("SV-GF Overlap", style={"color": UCONN_NAVY}),
                html.P(
                    "SV-gene records where the SV interval intersects each genomic feature (GF). Exon counts require gene matching; active enhancer counts use MESENCHYMAL and NEURALCREST rows.",
                    style={"fontSize": "13px", "color": "#52606D", "marginBottom": "12px"},
                ),
                _annotation_overlap_table(sv_gene_annotation_overlap, page_size=8),
            ], style=CARD_STYLE),
            html.Div([
                html.H3("Gene-GF Overlap", style={"color": UCONN_NAVY}),
                html.P(
                    "Gene intervals intersecting each genomic feature (GF). Exon counts use gene_id matching; active enhancer counts use MESENCHYMAL and NEURALCREST rows.",
                    style={"fontSize": "13px", "color": "#52606D", "marginBottom": "12px"},
                ),
                _annotation_overlap_table(gene_annotation_overlap, page_size=8),
            ], style=CARD_STYLE),
        ], style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(520px, 1fr))", "gap": "16px", "marginTop": "18px"}),
        html.Div([
            html.Div([
                dcc.Graph(figure=_length_figure(sv_length_bins), config={"displayModeBar": False}),
                html.P(
                    "SV calls were generated from Illumina short-read sequencing data; length distributions should be interpreted in that detection context.",
                    style={**muted_text_style, "fontSize": "12px", "margin": "-8px 18px 10px 18px"},
                ),
            ]),
            dcc.Graph(figure=_cohort_figure(cohort_counts), config={"displayModeBar": False}),
        ], style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(420px, 1fr))", "gap": "16px", "marginTop": "18px"}),
        html.Div(dcc.Graph(figure=_gene_exon_figure(gene_exon_by_chromosome), config={"displayModeBar": False}), style={**CARD_STYLE, "marginTop": "18px"}),
        _sv_type_group_section(sv_type_group_distribution),
        html.Div([html.H3("Database Table Counts", style={"color": UCONN_NAVY}), _table(table_counts, page_size=12)], style={**CARD_STYLE, "marginTop": "18px"}),
    ])


def _interactive_layout():
    return html.Div([
        html.P(
            "Build a grouped bar graph from the joined phenotype and phenotype_svs database tables. "
            "This option queries aggregate counts only when controls change.",
            style={"marginBottom": "16px"},
        ),
        html.Div([
            html.Label("X Axes", style={"fontWeight": "600", "marginBottom": "8px"}),
            dcc.Checklist(
                id="database-bar-x-axis",
                options=[{"label": config["label"], "value": value} for value, config in BAR_X_AXES.items()],
                value=["chrom"],
                inline=True,
                inputStyle={"marginRight": "6px"},
                labelStyle={
                    "display": "inline-block",
                    "border": "1px solid #B7C2CE",
                    "borderRadius": "6px",
                    "padding": "8px 12px",
                    "margin": "0 8px 8px 0",
                    "cursor": "pointer",
                },
            ),
        ], style={"marginBottom": "14px"}),
        html.Div([
            html.Label("Y Value", style={"fontWeight": "600", "marginBottom": "8px"}),
            dcc.RadioItems(
                id="database-bar-y-value",
                options=[{"label": config["label"], "value": value} for value, config in BAR_Y_METRICS.items()],
                value="unique_svs",
                inline=True,
                inputStyle={"marginRight": "6px"},
                labelStyle={"margin": "0 18px 8px 0", "cursor": "pointer"},
            ),
        ], style={"marginBottom": "18px"}),
        dcc.Loading(html.Div(id="database-bar-graph-output"), type="default"),
    ], style=CARD_STYLE)


def page_layout():
    return html.Div([
        html.H2("Database Overview", style=page_title_style),
        dcc.Tabs(
            id="database-overview-tabs",
            value="static",
            children=[
                dcc.Tab(label="Static", value="static", children=html.Div(_static_layout(), style={"paddingTop": "22px"})),
                dcc.Tab(label="Interactive", value="interactive", children=html.Div(_interactive_layout(), style={"paddingTop": "22px"})),
            ],
            colors={"border": UCONN_LIGHT_BLUE, "primary": UCONN_NAVY, "background": "#FFFFFF"},
        ),
    ], style={**uconn_styles["content"], "maxWidth": "1400px", "margin": "30px auto"})


@callback(
    Output("database-bar-graph-output", "children"),
    Input("database-bar-x-axis", "value"),
    Input("database-bar-y-value", "value"),
)
def update_database_bar_graph(x_axes, y_metric):
    try:
        df, axes, metrics = load_bar_graph_data(x_axes, y_metric)
        if df.empty:
            raise ValueError("No joined phenotype and SV data was found.")
        fig, primary_order = _create_grouped_bar_figure(
            df,
            axes,
            metrics,
            {axis: BAR_X_AXES[axis]["label"] for axis in axes},
            {metric: BAR_Y_METRICS[metric]["label"] for metric in metrics},
            "Count",
        )
        labels = [BAR_X_AXES[axis]["label"] for axis in axes]
        return html.Div([
            html.P(
                f"Data source: phenotype joined to phenotype_svs on bam_id/sample. "
                f"{len(primary_order)} {labels[0].lower()} groups.",
                style={"marginBottom": "15px"},
            ),
            dcc.Graph(figure=fig, style={"height": "600px", "marginBottom": "20px"}),
        ])
    except Exception as exc:
        return processing_error(exc)
