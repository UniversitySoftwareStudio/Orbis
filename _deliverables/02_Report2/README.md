# Report2

Moodle artifact: `CMPE492-Report02`

This folder contains the Report2 LaTeX/PDF deliverable copied from the original
`/report` source. It keeps the full current thesis report, including the
final-report additions required by the announcement.

Required filenames:

- `121200152_Atakan_Gul_Report2.pdf`
- `122200045_Arda_Kaan_Yildiz_Report2.pdf`

Required additional content:

- Design
- Potential risks
- Risk and change management
- Standards
- Sustainability
- Contributions

Mandatory realistic constraints content:

- Social, environmental, and economic impact within the scope of UN Sustainable Development Goals
- Cost analysis, including labor/design costs and technical costs
- Engineering standards, with emphasis on IEEE, IET, EU, Turkish standards, and engineering code of conduct
- Risk analysis and backup plans

Source and build:

- LaTeX entrypoint: `report/report2.tex`
- Bibliography: `report/references.bib`
- Thesis style: `report/styles/ibu-thesis.sty`
- Reference papers used by the bibliography: `report/baseline_papers/`
- Build command:

```bash
cd _deliverables/02_Report2
./render.sh
```

Build outputs:

- `Report2.pdf`
- `121200152_Atakan_Gul_Report2.pdf`
- `122200045_Arda_Kaan_Yildiz_Report2.pdf`

Report2 should be the final thesis/report submission unless the instructor
explicitly asks for a separate older Report1 document.
