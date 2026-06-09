# Report1

Moodle artifact: `CMPE492-Report01`

This folder contains the Report1 LaTeX/PDF deliverable copied from the original
`/report` source. It is derived from the current thesis report, but the
Report2-only realistic constraints, standards, risk-analysis, cost-analysis,
and contribution sections are removed.

Required filenames:

- `121200152_Atakan_Gul_Report1.pdf`
- `122200045_Arda_Kaan_Yildiz_Report1.pdf`

Required sections from the announcement:

- Introduction
- Related works
- Design
- Methodology
- Experimental setup
- Experiments and discussion
- Conclusion and future work

Source and build:

- LaTeX entrypoint: `report/report1.tex`
- Bibliography: `report/references.bib`
- Thesis style: `report/styles/ibu-thesis.sty`
- Reference papers used by the bibliography: `report/baseline_papers/`
- Build command:

```bash
cd _deliverables/01_Report1
./render.sh
```

Build outputs:

- `Report1.pdf`
- `121200152_Atakan_Gul_Report1.pdf`
- `122200045_Arda_Kaan_Yildiz_Report1.pdf`

Report1 should be used when the LMS expects the earlier report scope: project
background, design, methodology, setup, experiments, discussion, conclusion,
and future work.
