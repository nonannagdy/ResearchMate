# ResearchMate - Simple automated literature review agent
# Runs inside Hermes environment, uses only free tools.
import os
import sys
import json
import subprocess
import textwrap
def terminal(command):
    if command.startswith("python "):
        command = f'"{sys.executable}"' + command[6:]
    proc = subprocess.run(command, shell=True, capture_output=True, text=True)
    return {"output": proc.stdout + proc.stderr}

def web_extract(urls):
    results = []
    for url in urls:
        try:
            from urllib.request import Request, urlopen
            from html.parser import HTMLParser
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            html = urlopen(req, timeout=20).read().decode("utf-8", errors="ignore")
            class TextParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.parts = []
                def handle_data(self, data):
                    if data.strip():
                        self.parts.append(data.strip())
            parser = TextParser()
            parser.feed(html)
            results.append({"content": " ".join(parser.parts)})
        except Exception as e:
            results.append({"content": f""})
    return {"results": results}

def write_file(path, content):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"success": True}

HERMES_HOME = os.environ.get('HERMES_HOME', os.path.expanduser('~/.hermes'))
SOURCES_SCRIPT = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'hermes', 'hermes-agent', 'skills', 'research', 'grounded-citations', 'scripts', 'sources.py')

def run_hermes_chat(prompt):
    """Run hermes chat -q <prompt> -Q with prompt and return output."""
    proc = subprocess.run(['hermes', 'chat', '--query-file', '-', '--oneshot', '-Q', '--provider', 'google', '--model', 'gemini-3.1-flash-lite'], input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace")
    response = proc.stdout.strip()
    if not response or "error" in response.lower() or "404" in response or "429" in response:
        # Fallback to default if provider fails
        proc = subprocess.run(['hermes', 'chat', '--query-file', '-', '--oneshot', '-Q', '--provider', 'google', '--model', 'gemini-3.1-flash-lite'], input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace")
        response = proc.stdout.strip()
    return response

def search_arxiv(query, max_results=5):
    """Search arXiv and return a list of (id, title)."""
    import urllib.request
    import urllib.parse
    import xml.etree.ElementTree as ET

    stop_words = {'of', 'the', 'and', 'for', 'in', 'to', 'a', 'is', 'with', 'on'}
    query_terms = [
        w for w in query.split()
        if w.lower() not in stop_words
    ]

    if not query_terms:
        return []

    search_query = " OR ".join(f'all:{w}' for w in query_terms[:5])

    params = urllib.parse.urlencode({
        "search_query": search_query,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending"
    })

    url = f"https://export.arxiv.org/api/query?{params}"

    print(f"DEBUG: URL: {url}")

    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "ResearchMate/1.0 (research assistant)"
            }
        )

        with urllib.request.urlopen(request, timeout=30) as response:
            xml_data = response.read()

        print(f"DEBUG: Response length: {len(xml_data)}")

        root = ET.fromstring(xml_data)

        namespace = {
            "atom": "http://www.w3.org/2005/Atom"
        }

        entries = []

        for entry in root.findall("atom:entry", namespace):
            id_el = entry.find("atom:id", namespace)
            title_el = entry.find("atom:title", namespace)

            if id_el is not None and title_el is not None:
                arxiv_id = id_el.text.strip().split("/abs/")[-1]
                title = " ".join(title_el.text.strip().split())

                entries.append((arxiv_id, title))

        print(f"DEBUG: Parsed papers: {len(entries)}")

        return entries

    except Exception as e:
        print(f"DEBUG: arXiv request failed: {e}")
        return []
def extract_abstract(arxiv_id):
    """Extract abstract from arXiv abs page."""
    url = f'https://arxiv.org/abs/{arxiv_id}'
    result = web_extract(urls=[url])
    if result.get('results'):
        return result['results'][0].get('content', '')
    return ''

def register_source(url, title):
    """Run sources.py add and return citation ID like [1]."""
    cmd = f'python {json.dumps(SOURCES_SCRIPT)} add {json.dumps(url)} --title {json.dumps(title)}'
    result = terminal(command=cmd)
    out = result.get('output', '').strip()
    # Expected output like [1]
    return out

def analyze_all(summaries, question):
    """Summarize every paper in small batches, then compare all papers."""
    import re

    if not summaries:
        return "No papers were successfully retrieved."

    # Keep the model prompt manageable: 5 papers per request instead of all 30.
    individual_sections = []
    batch_size = 5
    for start_idx in range(0, len(summaries), batch_size):
        batch = summaries[start_idx:start_idx + batch_size]
        batch_start_number = start_idx + 1
        papers_text = "\n\n".join(
            f"Paper [{idx}] — {paper['title']}\nAbstract: {paper['abstract']}"
            for idx, paper in enumerate(batch, start=batch_start_number)
        )
        prompt = f'''You are a rigorous academic literature-review assistant.
Research question: {question}

Summarize EVERY paper supplied below. Do not omit any paper. Use only its title and abstract; do not invent methods, results, numbers, or limitations. If a detail is absent, write "Not specified in the abstract." Assess relevance honestly; label low or partial relevance if appropriate.

For EACH paper, use the exact numeric ID and exact title shown in the input (never write the placeholder N):
### Paper [exact number] — Exact full title
- Relevance: High / Partial / Low — reason
- Objective: ...
- Methods: ...
- Main findings: ...
- Limitations: ...
- Relevance to my research: ...

Return only these paper summaries. No introduction, no comparison table, no overall conclusion.

Papers to summarize:
{papers_text}'''
        print(f"Summarizing papers {batch_start_number}-{batch_start_number + len(batch) - 1}...")
        batch_result = run_hermes_chat(prompt)
        if not batch_result or any(marker in batch_result.lower() for marker in ["429 too many requests", "quota exceeded", "resource_exhausted", "no response"]):
            # Preserve every paper in the report rather than silently dropping it.
            batch_result = "\n\n".join(
                f"### Paper [{idx}] — {paper['title']}\n"
                "- Relevance: Not assessed — the model request failed.\n"
                "- Objective: Not assessed because the summary request failed.\n"
                "- Methods: Not specified; retry the analysis when the model is available.\n"
                "- Main findings: Not specified; retry the analysis when the model is available.\n"
                "- Limitations: The abstract could not be analyzed by the model.\n"
                "- Relevance to my research: Requires manual review."
                for idx, paper in enumerate(batch, start=batch_start_number)
            )
        individual_sections.append(batch_result.strip())

    summaries_text = "\n\n".join(individual_sections)
    compact_summaries = summaries_text[:36000]
    comparison_prompt = f'''You are a rigorous academic research assistant.
Research question: {question}

Using ONLY the paper summaries below, create:
## Comparison Table
A Markdown table with one row for EVERY paper, columns: Paper, Relevance, Objective, Methods, Main findings, Limitations. Keep cells concise but useful. Do not omit rows.

## Research Gaps & Next Steps
Separate (A) observations supported by these abstracts from (B) tentative research directions that require reading full papers. Do not claim a gap is proven by abstracts alone. Do not infer gaps from unrelated papers. Use citations [1] through [{len(summaries)}] for specific claims.

Paper summaries:
{compact_summaries}'''
    print("Comparing all paper summaries and identifying cautious research directions...")
    comparison_result = run_hermes_chat(comparison_prompt)
    if not comparison_result or "429 too many requests" in comparison_result.lower() or "quota exceeded" in comparison_result.lower():
        comparison_result = "## Comparison Table\n\nThe comparison table could not be generated because the model was unavailable. The individual summaries and paper details are still saved.\n\n## Research Gaps & Next Steps\n\nReview the individual summaries and full papers before making claims about research gaps."

    return "## Summaries\n\n" + summaries_text + "\n\n" + comparison_result.strip()

def render_sources_block(brief_text):
    """Render the Sources block from the grounded-citations ledger."""
    proc = subprocess.run(
        [sys.executable, SOURCES_SCRIPT, 'render', '--style', 'markdown'],
        capture_output=True
    )
    return proc.stdout.decode('utf-8', errors='replace').strip()

def main():
    print("=== ResearchMate: Automated Mini Literature Review ===")
    question = input("Enter your research question: ").strip()
    if not question:
        print("No question provided.")
        return

    print("\nSearching arXiv for recent papers...")
    papers = search_arxiv(question, max_results=30)
    if not papers:
        print("No papers found. Try a different query.")
        return

    print("\nTop papers:")
    for idx, (pid, title) in enumerate(papers, start=1):
        print(f"{idx}. [{pid}] {title}")

    # Process up to 30 papers and create an individual summary for every paper with an abstract.
    selected = papers[:30]
    print(f"\nSelected top {len(selected)} papers for review.")

    summaries_data = []
    citation_map = {}  # map arxiv_id -> citation_id like [1]

    for pid, title in selected:
        print(f"\nProcessing [{pid}] {title} ...")
        abstract = extract_abstract(pid)
        if not abstract:
            print("  Warning: Could not extract abstract.")
            continue
        # Register source
        url = f'https://arxiv.org/abs/{pid}'
        cite_id = register_source(url, title)
        print(f"  Registered source as {cite_id}")
        citation_map[pid] = cite_id
        summaries_data.append({'id': pid, 'title': title, 'abstract': abstract, 'cite_id': cite_id})

    if not summaries_data:
        print("Failed to process any papers.")
        return

    print(f"\nAnalyzing {len(summaries_data)} papers (individual summaries in batches, comparison, and research directions)...")
    full_analysis = analyze_all(summaries_data, question)

    # Keep the full analysis for all successfully processed papers.
    normalized_analysis = full_analysis

    print(f"\n--- Analysis Results ---\n{normalized_analysis}")

    # Assemble brief
    brief = f"""# Research Brief

**Research Question:** {question}

{normalized_analysis}
"""

    # Render sources block with clean sequential citation numbers.
    sources_block = "## Sources\n" + "\n".join(
        f"[{i}] https://arxiv.org/abs/{paper['id']} - {paper['title']}"
        for i, paper in enumerate(summaries_data, start=1)
    )
    print("\n--- Sources ---")
    print(sources_block)

    brief_with_sources = brief + "\n\n" + sources_block

    # Write to file
    output_path = os.path.join(os.path.expanduser('~/ResearchMate'), 'research_brief.md')
    write_file(path=output_path, content=brief_with_sources)
    print(f"\nResearch brief written to: {output_path}")
    export_report_files(brief_with_sources, os.path.dirname(output_path), summaries_data)
def export_report_files(report_text, output_dir, paper_data=None):
    from docx import Document
    from docx.shared import Pt, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment
    import re

    os.makedirs(output_dir, exist_ok=True)

    # -------------------------
    # Helpers for Word formatting
    # -------------------------
    def set_cell_shading(cell, fill):
        tc_pr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:fill"), fill)
        tc_pr.append(shd)

    def clean_text(text):
        """Remove Markdown/LaTeX artifacts that should not appear in Word."""
        text = text.replace(r"\times", "Ã—")
        text = text.replace(r"\pi", "Ï€")
        text = text.replace(r"\le", "â‰¤")
        text = text.replace(r"\ge", "â‰¥")
        text = text.replace(r"\rightarrow", "â†’")
        text = text.replace(r"\approx", "â‰ˆ")
        text = text.replace(r"\pm", "Â±")
        text = text.replace("$", "")
        text = text.replace(r"\mathrm{", "")
        text = text.replace(r"\text{", "")
        text = text.replace("}", "") if r"\mathrm{" in text or r"\text{" in text else text
        text = text.replace("root-Ï€", "root-Ï€")
        return text.strip()

    def add_formatted_paragraph(doc, text, bullet=False):
        text = clean_text(text.strip())

        # Remove Markdown bullet marker
        if text.startswith("* "):
            text = text[2:].strip()

        # Remove numbered-list Markdown formatting when needed
        if len(text) > 2 and text[0].isdigit() and text[1:3] == ". ":
            text = text[3:].strip()

        if not text:
            doc.add_paragraph()
            return

        paragraph = (
            doc.add_paragraph(style="List Bullet")
            if bullet
            else doc.add_paragraph()
        )

        # Convert **bold text** into real Word bold.
        parts = text.split("**")
        for idx, part in enumerate(parts):
            if not part:
                continue
            run = paragraph.add_run(part)
            if idx % 2 == 1:
                run.bold = True

        paragraph.paragraph_format.space_after = Pt(6)
        paragraph.paragraph_format.line_spacing = 1.08

    def parse_table_line(text):
        """Return table cells from a Markdown pipe row."""
        text = text.strip()
        if text.count("|") < 2:
            return None
        parts = [clean_text(p.strip()) for p in text.strip("|").split("|")]
        return parts if len(parts) >= 2 else None

    def is_separator_row(parts):
        return bool(parts) and all(
            p and set(p) <= set("-: ")
            for p in parts
        )

    def add_word_table(doc, rows):
        if not rows:
            return

        # Normalize row lengths.
        column_count = max(len(row) for row in rows)
        normalized_rows = [
            row + [""] * (column_count - len(row))
            for row in rows
        ]

        table = doc.add_table(rows=1, cols=column_count)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.style = "Table Grid"
        table.autofit = True

        # Header
        for col_idx, value in enumerate(normalized_rows[0]):
            cell = table.rows[0].cells[col_idx]
            cell.text = value.replace("**", "")
            set_cell_shading(cell, "D9EAF7")
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.bold = True
                    run.font.size = Pt(9)

        # Body
        for row_values in normalized_rows[1:]:
            cells = table.add_row().cells
            for col_idx, value in enumerate(row_values):
                cells[col_idx].text = value.replace("**", "")
                cells[col_idx].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
                for paragraph in cells[col_idx].paragraphs:
                    for run in paragraph.runs:
                        run.font.size = Pt(9)

        doc.add_paragraph()

    # -------------------------
    # Create Word report
    # -------------------------
    doc = Document()

    section = doc.sections[0]
    section.top_margin = Inches(0.7)
    section.bottom_margin = Inches(0.7)
    section.left_margin = Inches(0.8)
    section.right_margin = Inches(0.8)

    normal_style = doc.styles["Normal"]
    normal_style.font.name = "Times New Roman"
    normal_style.font.size = Pt(11)

    title = doc.add_heading("ResearchMate Research Report", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    subtitle = doc.add_paragraph("Automated Literature Review")
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.runs[0].italic = True
    subtitle.runs[0].font.size = Pt(11)

    doc.add_paragraph()

    lines = report_text.splitlines()
    i = 0

    while i < len(lines):
        line = clean_text(lines[i].strip())

        # Empty line
        if not line:
            i += 1
            continue

        # Markdown table.
        # Detect any line containing multiple pipe separators, not only lines
        # that literally start with "|" so the table is robust to formatting.
        if line.count("|") >= 2:
            table_lines = []

            while i < len(lines):
                current = lines[i].strip()
                if current.count("|") < 2:
                    break

                parts = parse_table_line(current)
                if parts and not is_separator_row(parts):
                    table_lines.append(parts)
                i += 1

            if table_lines:
                add_word_table(doc, table_lines)
            continue

        # Headings
        if line.startswith("### "):
            heading = doc.add_heading(clean_text(line[4:].strip()), level=2)
            heading.paragraph_format.space_before = Pt(10)
            heading.paragraph_format.space_after = Pt(5)
            i += 1
            continue

        if line.startswith("## "):
            heading = doc.add_heading(clean_text(line[3:].strip()), level=1)
            heading.paragraph_format.space_before = Pt(12)
            heading.paragraph_format.space_after = Pt(6)
            i += 1
            continue

        if line.startswith("# "):
            heading = doc.add_heading(clean_text(line[2:].strip()), level=1)
            heading.paragraph_format.space_before = Pt(12)
            heading.paragraph_format.space_after = Pt(6)
            i += 1
            continue

        # Markdown bullets, including "* **Methods:** ..."
        if re.match(r"^\*\s+", line):
            add_formatted_paragraph(doc, re.sub(r"^\*\s+", "", line), bullet=True)
            i += 1
            continue

        # Numbered list
        if re.match(r"^\d+\.\s+", line):
            add_formatted_paragraph(doc, line)
            i += 1
            continue

        # Sources separator
        if line.startswith("---"):
            paragraph = doc.add_paragraph()
            paragraph.paragraph_format.space_before = Pt(10)
            paragraph.paragraph_format.space_after = Pt(4)
            run = paragraph.add_run("Sources")
            run.bold = True
            run.font.size = Pt(12)
            i += 1
            continue

        # Normal paragraph
        add_formatted_paragraph(doc, line)
        i += 1

    word_path = os.path.join(output_dir, "ResearchMate_Report.docx")
    doc.save(word_path)

    # -------------------------
    # Create Excel workbook
    # -------------------------
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Research Brief"

    # Clean, readable report sheet: separate section names from content.
    ws.merge_cells("A1:B1")
    ws["A1"] = "ResearchMate Research Brief"
    ws["A1"].font = Font(name="Calibri", size=16, bold=True, color="FFFFFF")
    ws["A1"].fill = PatternFill(fill_type="solid", fgColor="244062")
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 32
    ws["A2"] = "Section"
    ws["B2"] = "Details"
    for header_cell in (ws["A2"], ws["B2"]):
        header_cell.font = Font(name="Calibri", bold=True, color="FFFFFF")
        header_cell.fill = PatternFill(fill_type="solid", fgColor="4472C4")
        header_cell.alignment = Alignment(horizontal="center", vertical="center")

    row = 3
    current_section = "Research Brief"
    for line in report_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("---"):
            continue
        if stripped.startswith("|") and stripped.count("|") >= 2:
            # Keep the comparison table on its own worksheet, not as a long line here.
            continue
        if stripped.startswith("#"):
            current_section = clean_text(stripped.lstrip("# ")) or "Section"
            continue
        content = clean_text(stripped.replace("**", ""))
        if not content:
            continue
        ws.cell(row=row, column=1, value=current_section)
        ws.cell(row=row, column=2, value=content)
        ws.cell(row=row, column=1).font = Font(name="Calibri", size=10, bold=True, color="244062")
        ws.cell(row=row, column=2).font = Font(name="Calibri", size=10)
        for col in (1, 2):
            ws.cell(row=row, column=col).alignment = Alignment(vertical="top", wrap_text=True)
        ws.row_dimensions[row].height = 42 if len(content) > 140 else 28
        row += 1

    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 100
    ws.freeze_panes = "A3"
    ws.sheet_view.showGridLines = False
    ws.auto_filter.ref = f"A2:B{ws.max_row}" if ws.max_row >= 2 else "A1:B1"

    # Comparison table sheet: extract Markdown comparison rows
    comparison = wb.create_sheet("Paper Comparison")
    comparison["A1"] = "Paper Comparison"
    comparison["A1"].font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
    comparison["A1"].fill = PatternFill(fill_type="solid", fgColor="244062")
    comparison.merge_cells("A1:F1")
    comparison["A1"].alignment = Alignment(horizontal="center", vertical="center")
    comparison.row_dimensions[1].height = 30

    table_rows = []
    in_comparison = False
    for line in report_text.splitlines():
        stripped = line.strip()
        if stripped.lstrip("# ").lower().startswith("comparison table"):
            in_comparison = True
            continue
        if in_comparison and stripped.startswith("## "):
            break
        if in_comparison and stripped.count("|") >= 2:
            parts = parse_table_line(stripped)
            if parts and not is_separator_row(parts):
                table_rows.append(parts)

    for r_idx, values in enumerate(table_rows, start=2):
        for c_idx, value in enumerate(values, start=1):
            cell = comparison.cell(row=r_idx, column=c_idx, value=clean_text(value.replace("**", "")))
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            if r_idx == 2:
                cell.font = Font(name="Calibri", bold=True, color="FFFFFF")
                cell.fill = PatternFill(fill_type="solid", fgColor="4472C4")
            else:
                cell.font = Font(name="Calibri", size=10)
                cell.border = Border(bottom=Side(style="thin", color="D9E2F3"))

    for column_cells in comparison.columns:
        column_letter = get_column_letter(column_cells[0].column)
        comparison.column_dimensions[column_letter].width = 30
    comparison.freeze_panes = "A3"
    comparison.sheet_view.showGridLines = False
    if comparison.max_row >= 2:
        comparison.auto_filter.ref = f"A2:{get_column_letter(comparison.max_column)}{comparison.max_row}"

    # Apply consistent wrapping to the report sheet
    for row_cells in ws.iter_rows():
        for cell in row_cells:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    ws.auto_filter.ref = f"A3:A{ws.max_row}" if ws.max_row >= 3 else "A1:A1"

    # Sheet 3: metadata and abstracts for every successfully processed paper.
    papers_ws = wb.create_sheet("30 Papers")
    paper_headers = ["No.", "Title", "arXiv ID", "URL", "Abstract"]
    papers_ws.append(paper_headers)
    for cell in papers_ws[1]:
        cell.font = Font(name="Calibri", bold=True, color="FFFFFF")
        cell.fill = PatternFill(fill_type="solid", fgColor="4472C4")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    # Include all paper metadata and the full abstract used for summarization.
    for idx, paper in enumerate(paper_data or [], start=1):
        papers_ws.append([idx, paper.get("title", ""), paper.get("id", ""),
                          f"https://arxiv.org/abs/{paper.get('id', '')}", paper.get("abstract", "")])
    for col, width in {"A":8,"B":55,"C":18,"D":36,"E":65}.items():
        papers_ws.column_dimensions[col].width = width
    papers_ws.freeze_panes = "A2"
    papers_ws.auto_filter.ref = papers_ws.dimensions
    papers_ws.sheet_view.showGridLines = False
    for row_cells in papers_ws.iter_rows(min_row=2):
        for cell in row_cells:
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    # Sheet 4: individual summaries, parsed from the structured report headings.
    summaries_ws = wb.create_sheet("Individual Summaries")
    summaries_ws.append(["Paper", "Relevance", "Objective", "Methods", "Main findings", "Limitations", "Relevance to my research"])
    for cell in summaries_ws[1]:
        cell.font = Font(name="Calibri", bold=True, color="FFFFFF")
        cell.fill = PatternFill(fill_type="solid", fgColor="4472C4")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    summary_rows = []
    current = None
    fields = {"Relevance": "", "Objective": "", "Methods": "", "Main findings": "", "Limitations": "", "Relevance to my research": ""}
    field_aliases = {"main findings":"Main findings", "findings":"Main findings", "objective":"Objective", "methods":"Methods", "limitations":"Limitations", "relevance to my research":"Relevance to my research", "relevance":"Relevance"}
    def flush_summary():
        if current:
            summary_rows.append([current] + [fields[k] for k in ["Relevance", "Objective", "Methods", "Main findings", "Limitations", "Relevance to my research"]])
    in_summaries = False
    for ln in report_text.splitlines():
        st = ln.strip()
        if st.lower().startswith("## summaries"):
            in_summaries = True
            continue
        if in_summaries and st.startswith("## "):
            flush_summary()
            current = None
            break
        if not in_summaries:
            continue
        if st.startswith("### Paper"):
            flush_summary()
            current = clean_text(st.lstrip("# "))
            fields = {"Relevance": "", "Objective": "", "Methods": "", "Main findings": "", "Limitations": "", "Relevance to my research": ""}
            continue
        if current and st.startswith("-") and ":" in st:
            key, value = st.lstrip("- ").split(":", 1)
            norm = key.strip().lower()
            if norm in field_aliases:
                fields[field_aliases[norm]] = clean_text(value.strip())
        elif current and st and not st.startswith("|"):
            # Preserve any extra explanation in the objective field rather than dropping it.
            if not fields["Objective"]:
                fields["Objective"] = clean_text(st)
    else:
        flush_summary()
    for row_values in summary_rows:
        summaries_ws.append(row_values)
    for col, width in {"A":38,"B":28,"C":42,"D":42,"E":48,"F":42,"G":42}.items():
        summaries_ws.column_dimensions[col].width = width
    summaries_ws.freeze_panes = "A2"
    summaries_ws.auto_filter.ref = summaries_ws.dimensions
    summaries_ws.sheet_view.showGridLines = False
    for row_cells in summaries_ws.iter_rows(min_row=2):
        for cell in row_cells:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    for ridx in range(2, summaries_ws.max_row + 1):
        summaries_ws.row_dimensions[ridx].height = 90

    excel_path = os.path.join(output_dir, "ResearchMate_Comparison.xlsx")
    wb.save(excel_path)

    print(f"\nWord report created: {word_path}")
    print(f"Excel report created: {excel_path}")


if __name__ == "__main__":
    main()







