"""
Main application entry point for UCONN OFC SV Browser.
This file initializes the Dash application and server.
"""

from dash import Dash
from flask import Response, abort, request
from utils.database import load_genomes_from_db, get_chromosome_size, DB_PATH

# Create the Dash application instance
app = Dash(
    __name__,
    suppress_callback_exceptions=True,
    external_stylesheets=[
        'https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap',
        'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css'
    ]
)

# Configure the application
app.title = "UCONN OFC SV Browser"

# Load genome information from database
HOSTED_GENOME_DICT = load_genomes_from_db(DB_PATH)

# Export the server variable for WSGI deployment
server = app.server


def build_local_igv_reference(chrom):
    """
    Build an IGV reference object backed by local synthetic sequence routes.

    The database stores annotations and SV coordinates, but not reference bases.
    IGV still needs reference coordinate metadata, so these routes serve an
    indexed N-only FASTA for the selected chromosome without loading hg38.
    """
    chrom = str(chrom)
    return {
        "id": f"db-{chrom}",
        "name": f"Database coordinates ({chrom})",
        "fastaURL": f"/_igv_local_reference/{chrom}.fa",
        "indexURL": f"/_igv_local_reference/{chrom}.fa.fai",
        "indexed": True,
        "wholeGenomeView": False,
        "chromosomeOrder": [chrom],
    }


def _virtual_fasta_byte(chrom, chrom_size, position, line_bases=50, line_width=51):
    header = f">{chrom}\n".encode("ascii")
    if position < len(header):
        return header[position]

    sequence_position = position - len(header)
    line_offset = sequence_position % line_width
    base_index = (sequence_position // line_width) * line_bases + min(line_offset, line_bases)

    if base_index >= chrom_size:
        return ord("\n") if line_offset == 0 else None
    return ord("\n") if line_offset == line_bases else ord("N")


def _virtual_fasta_length(chrom, chrom_size, line_bases=50, line_width=51):
    header_len = len(f">{chrom}\n".encode("ascii"))
    full_lines, remainder = divmod(chrom_size, line_bases)
    sequence_len = full_lines * line_width + (remainder + 1 if remainder else 0)
    return header_len + sequence_len


@server.route("/_igv_local_reference/<path:filename>")
def serve_local_igv_reference(filename):
    if filename.endswith(".fa.fai"):
        chrom = filename[:-7]
        chrom_size = get_chromosome_size(chrom)
        offset = len(f">{chrom}\n".encode("ascii"))
        fai = f"{chrom}\t{chrom_size}\t{offset}\t50\t51\n"
        return Response(fai, mimetype="text/plain")

    if not filename.endswith(".fa"):
        abort(404)

    chrom = filename[:-3]
    chrom_size = get_chromosome_size(chrom)
    total_length = _virtual_fasta_length(chrom, chrom_size)
    range_header = request.headers.get("Range")

    if range_header:
        try:
            range_spec = range_header.replace("bytes=", "", 1)
            start_text, end_text = range_spec.split("-", 1)
            start = int(start_text) if start_text else 0
            requested_end = int(end_text) if end_text else start + 1024 * 1024 - 1
            end = min(requested_end, total_length - 1)
        except (ValueError, TypeError):
            abort(416)
    else:
        start = 0
        end = min(total_length - 1, 1024 * 1024 - 1)

    if start < 0 or start >= total_length or end < start:
        abort(416)

    data = bytes(
        byte
        for byte in (_virtual_fasta_byte(chrom, chrom_size, position) for position in range(start, end + 1))
        if byte is not None
    )
    status = 206 if range_header else 200
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Range": f"bytes {start}-{end}/{total_length}",
        "Content-Length": str(len(data)),
        "Cache-Control": "no-store",
    }
    return Response(data, status=status, headers=headers, mimetype="text/plain")

# Import the views after initializing the app to avoid circular imports
# This uses the index.py as the router
if __name__ == '__main__':
    from index import *
    
    app.run_server(debug=True, host='0.0.0.0', port=8003)
