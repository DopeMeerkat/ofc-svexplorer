# UCONN OFC SV Browser

## Overview

The UCONN OFC SV Browser is a web-based genomic visualization tool developed for the exploration of Structural Variations (SVs) in the Orofacial Cleft (OFC) dataset from the Gabriella Miller Kids First Pediatric Research Program. This application allows researchers to visualize and analyze structural variations across different chromosomes with a specific focus on understanding their potential role in orofacial cleft disorders.

## Project Description

Cleft lip is the 4th most common birth defect in the U.S., affecting approximately one in 800 babies worldwide annually. While single nucleotide variation (SNV) analysis in syndromic and non-syndromic OFC has identified functional impairments in genes such as IRF6, BMP4, MAPK3, etc., structural variations (SVs) remain an important and under-explored component of the genomic landscape related to OFC.

This browser application provides tools to explore three main SV types (deletion, duplication, and inversions) in both family-based and population-level analyses, helping researchers identify common and individual SV alleles that may contribute to OFC phenotypes.

## Features

- **Genome Browser**: Interactive visualization of genomic regions with IGV.js integration
- **Population SV Browser**: Aggregated view of structural variations across all families with tracks for:
  - Mothers (Combined)
  - Fathers (Combined)
  - Children (Combined)
  - Background Reference SVs
- **Family Genome Browser**: Family-specific visualization of structural variations
- **Gene Search**: Search for specific genes across the genome
- **Circos Plots**: Circular genome visualization
- **Network Visualization**: Gene and SV network analysis
- **Summary Tables**: Tabular presentation of variant data

## Technology Stack

- **Backend**: Python, SQLite
- **Web Framework**: Dash by Plotly
- **Genomic Visualization**: IGV.js, Dash Bio components
- **Data Processing**: Pandas, NumPy
- **Styling**: Bootstrap, CSS

## Directory Structure

```
.
├── app.py                  # Main application initialization
├── index.py                # Application routing and layout
├── run.py                  # Application runner script
├── assets/                 # Static assets (images, CSS)
├── components/             # Reusable UI components
│   ├── family_gene_search.py
│   ├── gene_search.py
│   ├── population_gene_search.py
│   ├── header.py
│   ├── footer.py
├── pages/                  # Application pages
│   ├── circos.py
│   ├── family_genomes.py
│   ├── genome_browser.py
│   ├── image_pages.py
│   ├── network.py
│   ├── population_svs.py
│   ├── summary.py
│   ├── table.py
└── utils/                  # Utility functions
    ├── circos_helpers.py
    ├── database.py
    ├── styling.py
```

## Installation & Setup

### Prerequisites

- Python 3.8+
- SQLite database with genomic data
- Required Python packages (see requirements section)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/UConn/ofc-sv-browser.git
   cd ofc-sv-browser
   ```

2. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure the database path in `utils/database.py` if needed.

4. Run the application:
   ```bash
   python run.py
   ```

5. Access the application at http://localhost:8002

## Required Packages

- dash
- dash-bio
- plotly
- pandas
- numpy
- sqlite3

## Database Structure

The application uses an SQLite database (`/data/cellvar.db/cellvar.db`) containing:
- Gene information
- Structural variation data
- Family/phenotype information
- Reference genome annotations

## Usage

1. **Home Page**: Overview of the project and available tools
2. **Genome Browser**: Select chromosomes or search for genes to visualize genomic regions
3. **Population SV Browser**: Explore structural variations across the population
4. **Family Genome Browser**: Examine SVs within specific family contexts

## Development

To run the application in development mode:

```bash
python run.py
```

This starts the application with hot reloading enabled.

## Contributing

Please follow these steps to contribute:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add some feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

## License

[Specify license information]

## Acknowledgments

This project is part of the Expert-Driven Small Projects to Strengthen Gabriella Miller Kids First Discovery (RFA-RM-22-006) and utilizes data from the Kids First program.

## Contact

[Provide contact information for the project maintainers]
