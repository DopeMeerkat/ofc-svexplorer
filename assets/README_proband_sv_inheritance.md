# Proband SV Inheritance Generator and Data Files

This directory contains the script to generate a CSV file with inheritance patterns for structural variations (SVs) found in probands, as well as the generated CSV files.

## Data Generation

To generate a new CSV file with the latest data, run:

```bash
python generate_proband_sv_inheritance.py
```

The script will:
1. Query the database for all SVs found in probands
2. Determine which SVs are inherited from the father, mother, or both
3. Calculate percentages and inheritance patterns
4. Save the results to a CSV file with a timestamp in the filename

## Output File Format

The CSV file contains the following columns:
- SV ID: Unique identifier for the structural variation
- Associated Gene: Gene associated with the SV from the cellvar_ofc_children_table.csv file
- Proband Count: Number of probands with this SV
- Percentage of Probands (%): Percentage of all probands with this SV
- Inherited From Father: Count of cases where the SV is inherited from the father
- Inherited From Mother: Count of cases where the SV is inherited from the mother
- Inherited From Both Parents: Count of cases where the SV is inherited from both parents
- SV Type: Type of structural variation (DEL, INS, DUP, etc.)
- Chromosome: The chromosome where the SV is located
- Start Position: Starting genomic coordinate of the SV
- End Position: Ending genomic coordinate of the SV
- Length (bp): Length of the SV in base pairs

## Integration with Dashboard

The dashboard page now loads the data directly from the CSV file instead of querying the database each time. This improves performance and reduces the load on the database.

1. The file `proband_sv_inheritance.csv` is the main file used by the dashboard
2. Files named `proband_sv_inheritance_YYYYMMDD_HHMMSS.csv` are timestamped backups 

To update the data displayed in the dashboard:
1. Generate a new CSV file using the script
2. Copy the new file to `proband_sv_inheritance.csv` to make it the default

The dashboard will automatically load the most recent CSV file.
