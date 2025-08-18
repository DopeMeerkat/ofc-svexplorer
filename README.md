# Orofacial Cleft Structural Variation Explorer (OFC-SVExplorer)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

The OFC-SVExplorer is a sophisticated web-based genomic visualization platform developed for comprehensive exploration of Structural Variations (SVs) in the Orofacial Cleft (OFC) dataset from the Gabriella Miller Kids First Pediatric Research Program. This interactive dashboard application enables researchers to visualize, analyze, and interpret structural variations across different chromosomes with a specific focus on understanding their potential role in orofacial cleft disorders.

## Background & Significance

Orofacial clefts, including cleft lip and palate, represent the fourth most common birth defect in the United States, affecting approximately 1 in 800 newborns worldwide annually. Despite significant advances in genomic research, the genetic architecture underlying OFC remains incompletely understood. While single nucleotide variation (SNV) analysis in both syndromic and non-syndromic OFC has identified functional impairments in key developmental genes (IRF6, BMP4, MAPK3, etc.), structural variations (SVs) constitute an important and under-explored component of the genomic landscape associated with OFC.

This browser application provides a comprehensive suite of tools to investigate three primary SV types (deletions, duplications, and inversions) through both family-based and population-level analyses. The platform facilitates the identification of common and individual SV alleles potentially contributing to OFC phenotypes, with particular emphasis on regulatory elements affecting mesenchymal and neural crest cell development.

## Key Features

### Data Visualization & Analysis
- **Interactive Genome Browser**: Seamless exploration of genomic regions with advanced IGV.js integration
- **Population SV Analytics**: Comprehensive aggregated view of structural variations across the cohort with specialized tracks for:
  - Maternal SVs (Combined)
  - Paternal SVs (Combined)
  - Proband SVs (Combined)
  - Control/Reference SVs
- **Family-Specific Genome Browser**: Detailed visualization of structural variations within family trios
- **SV Inheritance Patterns**: Analysis of inheritance patterns across probands
- **Cell-Type Specific Regulatory Analysis**: Investigation of mesenchymal stem cell (MSC) and neural crest cell (NCC) regulatory elements affected by SVs
- **Dashboard**: Statistical summary and distribution visualization of OFC-related structural variants

### Data Exploration Tools
- **Advanced Gene Search**: Precision search capability for specific genes across the genome with annotation integration
- **Circos Plot Visualization**: Circular genome visualization for identifying genome-wide patterns and hotspots
- **Network Analysis**: Gene and SV interaction network visualization and analysis
- **Data Tables**: Comprehensive tabular presentation of variant data with filtering and export capabilities

## Technology Stack

### Core Technologies
- **Backend Framework**: Python 3.8+
- **Database**: SQLite with optimized genomic data storage
- **Web Framework**: Dash by Plotly (interactive web applications)
- **Genomic Visualization**: 
  - IGV.js (Integrative Genomics Viewer) for detailed genome visualization
  - Dash Bio components for specialized bioinformatics visualizations
  - Circos.js for circular genome representation
- **Data Processing**: 
  - Pandas for efficient data manipulation
  - NumPy for numerical operations
  - Custom optimized algorithms for structural variant analysis

### User Interface
- **Responsive Design**: Bootstrap 5
- **Styling**: Custom CSS with UConn branding
- **Interactive Components**: Dash Core and HTML components
- **Data Visualization**: Plotly.js

## Architecture & Directory Structure

The application follows a modular architecture with clear separation of concerns:

```
.
├── app.py                  # Application initialization and configuration
├── index.py                # Application routing and primary layout
├── run.py                  # Application entry point with server configuration
├── assets/                 # Static assets and pre-computed data
│   ├── images/             # Application images and icons
│   ├── css/                # Custom styling
│   ├── proband_sv_inheritance.csv  # Pre-computed inheritance data
├── components/             # Reusable UI components
│   ├── family_gene_search.py   # Family-specific gene search component
│   ├── gene_search.py          # Global gene search functionality
│   ├── population_gene_search.py  # Population-level gene search
│   ├── header.py               # Application header component
│   ├── footer.py               # Application footer component
├── pages/                  # Application views and specialized pages
│   ├── circos.py               # Circular genome visualization
│   ├── dashboard.py            # Main dashboard with summary statistics
│   ├── family_genomes.py       # Family-specific genome analysis
│   ├── genome_browser.py       # Interactive genome browser
│   ├── population_svs.py       # Population-level SV analysis
│   ├── table.py                # Tabular data presentation
│   ├── visualization_uploader.py  # Custom visualization upload functionality
└── utils/                  # Utility functions and helpers
    ├── circos_helpers.py       # Circos plot generation utilities
    ├── database.py             # Database interaction layer
    ├── styling.py              # Global styling constants
```

## Installation & Deployment

### Prerequisites

- **Python**: Version 3.8 or higher
- **SQLite**: Database with genomic data (`/data/cellvar.db/cellvar.db`)
- **Environment**: Conda environment recommended for dependency management
- **Storage**: Minimum 10GB for database and pre-computed files

### Installation Steps

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/DopeMeerkat/ofc-svexplorer.git
   cd ofc-svexplorer
   ```

2. **Set Up Environment**:
   ```bash
   conda create -n svexplorer python=3.8
   conda activate svexplorer
   pip install -r requirements.txt
   ```

3. **Configure the Application**:
   - Review database path configuration in `utils/database.py`
   - Update any institution-specific branding in `utils/styling.py`
   - Generate pre-computed data files:
     ```bash
     python assets/generate_proband_sv_inheritance.py
     ```

4. **Launch the Application**:
   ```bash
   python run.py
   ```

5. **Access the Web Interface**:
   The application will be available at http://localhost:8002

### Production Deployment

For production environments, we recommend:
- Using Gunicorn as a WSGI server
- Setting up Nginx as a reverse proxy
- Implementing SSL for secure connections

Example Gunicorn deployment:
```bash
gunicorn --workers=4 --bind=0.0.0.0:8002 app:server
```

## Required Dependencies

### Core Requirements
- dash==2.11.0
- dash-bio==1.0.2
- plotly==5.14.0
- pandas==1.5.3
- numpy==1.24.3
- dash-bootstrap-components==1.4.1

### Visualization Requirements
- dash-daq==0.5.0
- igv-jupyter==0.9.9

### Data Processing
- scipy==1.10.1
- scikit-learn==1.2.2

## Data Architecture

### Database Schema

The application utilizes a comprehensive SQLite database (`/data/cellvar.db/cellvar.db`) with the following core components:

- **Gene Information**:
  - Genomic coordinates and annotations
  - Gene-specific metadata and identifiers
  - Functional annotations and pathway associations

- **Structural Variation Catalog**:
  - SV coordinates, types, and sizes
  - Family-specific SV annotations
  - Population frequency metrics
  - Regulatory impact predictions

- **Family & Phenotype Data**:
  - De-identified family structures
  - OFC phenotype classifications
  - Family relationships (proband, parent, sibling)
  - Inheritance patterns

- **Regulatory Elements**:
  - Enhancers, promoters, and insulators
  - Cell type-specific regulatory activity
  - Chromatin interaction domains
  - Mesenchymal and neural crest cell regulatory annotations

### Data Integration

The application integrates multiple data sources:
- Whole genome sequencing data from Kids First OFC cohort
- Reference SV datasets
- Functional genomics datasets (ENCODE, Roadmap Epigenomics)
- Gene interaction networks

## User Guide

### Dashboard Interface

1. **Home Dashboard**: 
   - Summary statistics and cohort overview
   - SV distribution visualization
   - Inheritance pattern analysis

2. **Genome Exploration**:
   - **Genome Browser**: Interactive navigation of genomic regions with IGV
   - **Gene Search**: Query specific genes and view associated SVs
   - **Population SV Browser**: Explore variation patterns across the entire cohort
   - **Family Browser**: Analyze SVs within family contexts

3. **Advanced Visualization**:
   - **Circos Plots**: Circular visualization of genome-wide SV patterns
   - **Network View**: Gene-gene and SV-gene interaction networks

4. **Data Export**:
   - Download gene lists, SV catalogs, and interaction data
   - Export visualizations for publications

## Development & Extension

### Development Environment

To run the application in development mode with hot reloading:

```bash
python run.py --debug
```

### Adding New Features

The modular architecture facilitates extension:

1. For new data visualizations: Add components to the appropriate page module
2. For new data types: Extend the database utilities in `utils/database.py`
3. For custom analyses: Create new analysis modules in the `utils` directory

## Contributing

We welcome contributions to enhance the OFC-SVExplorer platform. Please follow our contribution guidelines:

1. **Fork the Repository**: Create a personal fork of the project on GitHub
2. **Create a Feature Branch**: `git checkout -b feature/your-feature-name`
3. **Code Development**:
   - Follow the project's coding style and documentation standards
   - Write appropriate tests for new functionality
4. **Commit Changes**: Use clear, descriptive commit messages
   - `git commit -m 'Add feature: concise description of changes'`
5. **Push Changes**: `git push origin feature/your-feature-name`
6. **Submit a Pull Request**: Include a clear description of the changes and any relevant issue numbers

## Code of Conduct

This project adheres to a Code of Conduct adapted from the [Contributor Covenant](https://www.contributor-covenant.org/). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

This project is supported by the Expert-Driven Small Projects to Strengthen Gabriella Miller Kids First Discovery (RFA-RM-22-006) and utilizes data from the Kids First Data Resource Center. We gratefully acknowledge:

- The Gabriella Miller Kids First Pediatric Research Program
- UConn School of Medicine and UConn Health
- Contributing families and researchers in the orofacial cleft research community
- Open source contributors to the genomics visualization community

## Citation

If you use this software in your research, please cite:
```
OFC-SVExplorer: A Genomic Visualization Platform for Structural Variation Analysis in Orofacial Cleft Research. 
(2025). University of Connecticut School of Medicine. https://github.com/DopeMeerkat/ofc-svexplorer
```

## Contact

**Project Lead:** Justin Cotney, Ph.D.  
**Email:** cotney@uchc.edu  
**Institution:** Department of Genetics and Genome Sciences, UConn Health  
**Project Repository:** [https://github.com/DopeMeerkat/ofc-svexplorer](https://github.com/DopeMeerkat/ofc-svexplorer)
