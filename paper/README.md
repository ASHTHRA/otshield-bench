# OTShield Bench v0.6 manuscript package

This directory contains a publication-ready preprint draft derived from the
committed OTShield Bench v0.6 technical report and frozen replacement study.
The manuscript is intentionally a software-and-evidence package: it does not
rerun the laboratory study or regenerate any research artifact.

## Source boundary

All numerical results and figures are read from:

`evidence/v06/20260922T021855Z/aggregate.json`

and the completion/accounting record:

`evidence/v06/20260922T021855Z/study.json`

Methodological and scope statements are derived from the v0.6 technical report,
protocol, release manifest, and the two preserved errata. The historical
calibration is referenced as the committed file
`research/v0.6_calibration.json`; it is not regenerated here.

## Build and figures

From the repository root, install the normal development dependencies and the
paper plotting dependency, then run:

```sh
python -m pip install -r paper/requirements.txt
python paper/generate_figures.py
pdflatex -interaction=nonstopmode -halt-on-error -output-directory paper paper/main.tex
pdflatex -interaction=nonstopmode -halt-on-error -output-directory paper paper/main.tex
```

The figure script is deterministic and reads the aggregate JSON. It writes PNG
files below `paper/figures/`. LaTeX compilation is optional where a TeX
distribution is unavailable.

The paper describes analysis reproduction from committed files separately from
laboratory reproduction. Laboratory execution requires an explicitly authorized
isolated Linux/Docker environment and is not needed to reproduce the figures or
the manuscript's analysis claims. Never direct traffic at a real OT system.

## Release and availability

The software release is `v0.6.0-alpha` at
<https://github.com/ASHTHRA/otshield-bench/releases/tag/v0.6.0-alpha> and the
archived release DOI is
<https://doi.org/10.5281/zenodo.22899466>.

This draft preserves the study's evidence boundary: isolated OpenPLC,
read-only Modbus/TCP Function Code 3, one documented host setup, and no claims
of production validation, full GRFICSv3 validation, external replication,
industry adoption, DNP3 validation, or EtherNet/IP validation.
