# OFC SV Explorer

OFC SV Explorer is a web portal for reviewing structural variation in an orofacial cleft research cohort. It brings together cohort-level summaries, a curated gene table, IGV-based locus review, pathway networks, and selected case studies in one interface.

## Links

- Web portal: https://ofc-sv.cse.uconn.edu/
- Screenshot gallery: https://github.com/DopeMeerkat/ofc-svexplorer/blob/prod/gallery.md
- Source code: https://github.com/DopeMeerkat/ofc-svexplorer/tree/prod

## Data Scope

The portal is backed by a local research database built for OFC structural variant analysis. It includes cohort phenotype summaries, structural variant calls, gene and exon coordinates, SV-gene overlap records, and regulatory annotations such as active enhancer candidates, promoter candidates, insulator candidates, and no-cleft embryo cCREs.

Production views are designed to avoid exposing individual sample identifiers. The main outputs are aggregate counts, genomic intervals, summary tables, and curated case-study evidence.

## Summary

The Summary page is the entry point for the site. It introduces the cohort analysis and highlights overlap between known OFC genes and genes with recurrent SV signal in the cohort.

![Summary page](images/summary.png)

Use this page to:

- Review the high-level purpose of the portal.
- Identify the overlap between literature-supported OFC genes and cohort SV findings.
- Open the curated 41-gene table by selecting the overlap region.

Screenshot note: this image should show the landing page and the gene-overlap visualization.

## Database Overview

The Database Overview page summarizes the contents of the database through charts and compact tables. It has two tabs: Static and Interactive.

![Database Overview](images/database-overview.png)

Use the Static tab to review:

- Cohort-level counts for families, samples, affected cases, parents, controls, unique SVs, genes, and regulatory elements.
- SV distributions by type, chromosome, length, and genomic region.
- Cohort breakdowns by phenotype and related categories.
- SV-GF overlap per person, where genomic feature overlap summaries are normalized across the cohort.

Use the Interactive tab to build custom aggregate bar graphs:

- Select one or more grouping options, such as Chromosome and SV Type.
- Choose a value to summarize, such as Unique SVs or Samples.
- Use the generated chart to compare distributions across selected categories.

Screenshot note: this image should show the Database Overview page with the Static tab visible. A separate image can be added later if an Interactive tab example is preferred.

## Table Inspection

The Table Inspection page presents the curated 41-gene overlap table. It is intended for moving from a summary gene list into locus- and pathway-level review.

![Table Inspection](images/table-inspection.png)

Use this page to:

- Sort and search the curated table.
- Review gene annotations, candidate SVs, expression columns, and supporting context.
- Select clickable Gene or FusorSV ID fields to open navigation options.
- Open supported entries in IGV/Population, Pathway, or Case Study views.

Screenshot note: this image should show the curated table and, if possible, the navigation action menu after selecting a gene or SV value.

## IGV/Population

The IGV/Population page supports locus-level review of aggregate structural variant tracks. It is the main genome-browser view in the production site.

![IGV/Population](images/population.png)

Use this page to:

- Search for a gene and jump directly to its genomic locus.
- Browse by chromosome when reviewing broader regions.
- View aggregate SV tracks across the cohort.
- Add optional annotation tracks, including exons, active enhancer candidates, promoter candidates, insulator candidates, and no-cleft embryo cCREs.

When opened from Table Inspection or Case Study links, the page can load the relevant gene or locus directly.

Screenshot note: this image should show an IGV/Population locus with SV tracks and selected annotation tracks visible.

## Pathway

The Pathway page compares a user-entered gene list against curated palatogenesis network models.

![Pathway](images/pathway.png)

Use this page to:

- Enter genes as a comma-separated list, for example `TP63, IRF6, GRHL3`.
- Select `Highlight genes` to mark matching genes and annotated pathway terms.
- Use `Clear` to remove highlights from the pathway diagrams.
- Use `Reset view` to reload the diagrams and return to a clean layout.
- Show or hide the Baseline, Extended, and Case Study 6 network views.
- Click nodes to inspect labels, identifiers, and annotations.

Screenshot note: this image should show the pathway controls and one or more network diagrams with highlighted query genes.

## Case Study

The Case Study page contains curated gene-level examples. Each case connects a selected gene to cohort findings, genomic context, pathway interpretation, and supporting literature.

![Case Study](images/igv.png)

Use this page to:

- Review the case-study summary table.
- Select a curated case study from the dropdown.
- Read the gene function, IGV, literature, pathway, and supporting-data sections.
- Follow embedded links to the IGV/Population and Pathway pages.

Screenshot note: replace this placeholder with a dedicated Case Study page screenshot when available.

## Privacy

This is an internal UConn research dashboard prepared for publication-facing review. Production-facing views should avoid exposing individual sample identifiers in the interface, logs, screenshots, or downloads unless a separate internal-only exception is made.

## Citation

Citation details will be added when the companion publication is available.

```bibtex
@article{ofc_sv_explorer,
  title = {OFC SV Explorer: an interactive portal for orofacial cleft structural variation analysis},
  author = {TBD},
  journal = {TBD},
  year = {TBD},
  doi = {TBD}
}
```

## Acknowledgements

This project was developed at the University of Connecticut for research use in orofacial cleft structural variation analysis.
