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
    proc = subprocess.run(['hermes', 'chat', '--query-file', '-', '--oneshot', '-Q', '--provider', 'google', '--model', 'gemini-3.1-flash-lite'], input=prompt, capture_output=True, text=True)
    response = proc.stdout.strip()
    if not response or "error" in response.lower() or "404" in response or "429" in response:
        # Fallback to default if provider fails
        proc = subprocess.run(['hermes', 'chat', '--query-file', '-', '--oneshot', '-Q', '--provider', 'google', '--model', 'gemini-3.1-flash-lite'], input=prompt, capture_output=True, text=True)
        response = proc.stdout.strip()
    return response

def search_arxiv(query, max_results=5):
    """Search arXiv and return list of (id, title)."""
    # Use Lucene phrase-based query with proper encoding
    import urllib.parse
    stop_words = {'of', 'the', 'and', 'for', 'in', 'to', 'a', 'is', 'with', 'on'}
    query_terms = [f'all:{w}' for w in query.split() if w.lower() not in stop_words]
    q = urllib.parse.quote_plus(" AND ".join(query_terms[:2]))
    url = f'https://export.arxiv.org/api/query?search_query={q}&max_results={max_results}&sortBy=submittedDate&sortOrder=descending'
    print(f"DEBUG: URL: {url}")
    result = terminal(command=f'curl -s {json.dumps(url)}')
    xml = result.get('output', '')
    if not xml:
        print("DEBUG: Empty response from arXiv")
    else:
        print(f"DEBUG: Response length: {len(xml)}")
    # Simple parsing using python one-liner
    parse_cmd = f'''
import sys, xml.etree.ElementTree as ET, json
root = ET.fromstring(sys.stdin.read())
entries = []
for entry in root.findall('{{http://www.w3.org/2005/Atom}}entry'):
    id_el = entry.find('{{http://www.w3.org/2005/Atom}}id')
    title_el = entry.find('{{http://www.w3.org/2005/Atom}}title')
    if id_el is not None and title_el is not None:
        arxiv_id = id_el.text.split('/abs/')[-1]
        title = title_el.text.strip()
        entries.append((arxiv_id, title))
print(json.dumps(entries))
'''
    # Pipe xml to python
    proc = subprocess.run(['python', '-c', parse_cmd], input=xml.encode(), capture_output=True)
    out = proc.stdout.decode().strip()
    try:
        return json.loads(out)
    except Exception:
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

def analyze_all(summaries):
    """Perform comprehensive analysis in ONE LLM call."""
    # summaries is list of dict with id, title, abstract, cite_id
    text = "\n\n".join([f"Paper {s['cite_id']} ({s['title']}):\nAbstract: {s['abstract']}" for s in summaries])
    prompt = f"""You are a research assistant. Based on the following paper abstracts, perform a comprehensive literature review:

1. Provide a summary for each paper including methods, findings, and limitations.
2. Provide a markdown comparison table summarizing Methods, Findings, and Limitations.
3. Identify research gaps and suggest concrete next steps.

Use citation IDs (e.g. [1]) where appropriate.
Format the output with Markdown headers:
## Summaries
## Comparison Table
## Research Gaps & Next Steps

Abstracts:
{text}"""
    return run_hermes_chat(prompt)

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
    papers = search_arxiv(question, max_results=10)
    if not papers:
        print("No papers found. Try a different query.")
        return

    print("\nTop papers:")
    for idx, (pid, title) in enumerate(papers, start=1):
        print(f"{idx}. [{pid}] {title}")

    # Select top 3 automatically (non-programmer friendly)
    selected = papers[:3]
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

    print("\nAnalyzing papers (summarization, comparison, gaps, and steps)...")
    full_analysis = analyze_all(summaries_data)
    print(f"\n--- Analysis Results ---\n{full_analysis}")

    # Assemble brief
    brief = f"""# Research Brief

**Research Question:** {question}

{full_analysis}
"""

    # Render sources block
    sources_block = render_sources_block(brief)
    print("\n--- Sources ---")
    print(sources_block)

    brief_with_sources = brief + "\n\n" + sources_block

    # Write to file
    output_path = os.path.join(os.path.expanduser('~/ResearchMate'), 'research_brief.md')
    write_file(path=output_path, content=brief_with_sources)
    print(f"\nResearch brief written to: {output_path}")

if __name__ == '__main__':
    main()











