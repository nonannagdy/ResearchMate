# ResearchMate

ResearchMate is a lightweight research assistant that searches arXiv and creates a mini literature review for a research question. It aims to retrieve up to 30 papers, extract their abstracts, generate individual summaries in batches, compare the studies, and identify cautious research directions.

## Features

- Searches arXiv for papers relevant to a user-provided question.
- Retrieves paper titles, arXiv IDs, links, and abstracts.
- Generates an individual summary for each successfully retrieved abstract (objective, methods, findings, limitations, and relevance), in batches of five papers.
- Produces a comparison table and tentative research directions.
- Exports a Markdown research brief, a Word report, and an Excel workbook with separate sheets for the brief, paper comparison, paper metadata/abstracts, and individual summaries.

## Important runtime requirement

The current `main.py` is designed for the **Hermes Agent environment**. It invokes the `hermes` command-line tool and uses the Google Gemini `gemini-3.1-flash-lite` model through Hermes. It is not a standalone script for a plain Python installation unless you adapt `run_hermes_chat()` to a model provider you have configured.

You need:
- Python 3.10 or newer
- Hermes Agent CLI installed and configured with Google/Gemini access
- Python packages: `python-docx` and `openpyxl`
- Network access to the arXiv API and arXiv abstract pages

Install the Python packages in the Python environment used to run the script:

```bash
python -m pip install -r requirements.txt
```

## Run

Run from the folder where you want the output to be created:

```bash
python main.py
```

When prompted, enter a focused research question, for example:

```text
Structural health monitoring and damage detection methods for long-span bridges under traffic and environmental loads
```

The output files are written to a `ResearchMate` folder inside the current user's home directory:

- `research_brief.md`
- `ResearchMate_Report.docx`
- `ResearchMate_Comparison.xlsx`

## Notes and limitations

- arXiv may return fewer than 30 results for a query, and some results may be only partially relevant. Always review the titles and abstracts before using the output in academic work.
- The summaries are based on abstracts retrieved by the script, not necessarily full papers. Details absent from an abstract should not be treated as established findings.
- Gemini free-tier quotas/rate limits may interrupt summaries or comparisons. The script attempts to retain a report structure when a model request fails, but generated summaries should be checked.
- The project does not establish that a research gap is proven. Full-text review and independent verification are required before drawing academic conclusions.
- arXiv is a preprint repository and does not cover all engineering journals or conference proceedings.

## Suggested citation practice

Use the generated arXiv links to verify each paper. Cite the original paper or published version—not the ResearchMate-generated summary—in any thesis or publication.
