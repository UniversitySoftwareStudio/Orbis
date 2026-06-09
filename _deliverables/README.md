# CMPE 492 Final Submission Workspace

Moodle due date from the assignment list: **June 15, 2026, 23:00**.
Face-to-face presentation and poster demo: **June 22/23, 2026**.

Each team member must submit all required materials. The LMS announcement says
each file must be titled with `studentid_name_surname`; artifact-specific names
are listed in each folder.

## Artifact Folders

| Folder | Moodle artifact | Main output |
| --- | --- | --- |
| `01_Report1/` | `CMPE492-Report01` | `studentid_name_surname_Report1.pdf` |
| `02_Report2/` | `CMPE492-Report02` | `studentid_name_surname_Report2.pdf` |
| `03_Presentation/` | `CMPE492-Presentation` | `studentid_name_surname_presentation.pdf` or `.pptx` |
| `04_Code/` | `CMPE492-Code` | `studentid_name_surname_code.zip` |
| `05_Video/` | `CMPE492-Video` | `studentid_name_surname_video.mpg` |
| `06_Poster/` | `CMPE492-Poster` | `studentid_name_surname_poster.pdf` plus printed A1 poster |
| `07_Latex_Project/` | `CMPR492-Latex Project` | zipped/source LaTeX project |
| `00_Submission_Requirements/` | reference notes | copied checklist and LMS-derived requirements |

## Report Build Commands

Build both report PDFs:

```bash
cd _deliverables
./render_reports.sh
```

Build only one report:

```bash
cd _deliverables/01_Report1 && ./render.sh
cd _deliverables/02_Report2 && ./render.sh
```

Each report folder contains its own copied LaTeX `report/` directory. The
original top-level `report/` folder is left intact as the working source
history.

## Known Team Filename Stems

- `121200152_Atakan_Gul`
- `122200045_Arda_Kaan_Yildiz`

Submit all artifacts for each student account unless the course page states otherwise.
