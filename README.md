# ResearchMate

A simple automated literature review agent that turns a research question into a structured mini literature review with citations.

## What it does

1. Accepts a research question from the user.
2. Searches arXiv for recent relevant papers.
3. Extracts abstracts of the top papers.
4. Keeps track of sources and assigns stable numeric IDs.
5. Uses the Hermes language model to summarize each paper's methods, key findings, and limitations, inserting inline citations.
6. Generates a markdown table comparing the papers.
7. Identifies research gaps and suggests next steps.
8. Produces a final research brief with a formatted `Sources:` block.
9. Saves the brief to `research_brief.md` in the same folder.

## Requirements

- Hermes Agent installed and accessible via the `hermes` command.
- No paid API credits are required. The project uses Hermes built-in research tools and a free-tier LLM provider configured in Hermes.

## Setup

1. Ensure Hermes is installed and you can run `hermes` from a terminal.
2. Clone or copy this folder to your desired location (e.g., `~/ResearchMate`).
3. Open a terminal and navigate to the folder:
   ```bash
   cd ~/ResearchMate
   ```
4. Run the agent:
   ```bash
   & "C:\Users\dell\AppData\Local\hermes\tools\python-3.14.7+20260901-win32-x64\python.exe" .\main.py
   ```
5. Follow the prompts:
   - Enter your research question when asked.
   - The agent will automatically select the top three most recent arXiv papers, process them, and produce a brief.

## Example

```bash
$ & "C:\Users\dell\AppData\Local\hermes\tools\python-3.14.7+20260901-win32-x64\python.exe" .\main.py
=== ResearchMate: Automated Mini Literature Review ===
Enter your research question: parameter-efficient fine-tuning of large language models

Searching arXiv for recent papers...
Top papers:
1. [2405.12345] LoRA: Low-Rank Adaptation of Large Language Models
2. [2405.23456] QLoRA: Efficient Finetuning of Quantized LLMs
3. [2405.34567] AdaLoRA: Adaptive Budget Allocation for Parameter-Efficient Fine-Tuning
...

Processing [...]
...
Research brief written to: /home/youruser/ResearchMate/research_brief.md
```

Open `research_brief.md` to see the formatted literature review with citations.

## How it works (non‑programmer view)

- The script calls `hermes chat -q` to ask the built‑in AI to read abstracts and write summaries.
- It uses the `grounded-citations` skill’s `sources.py` tool to register each arXiv abstract URL and retrieve a stable citation ID like `[1]`.
- All citations in the final document refer to those IDs, and the `Sources:` block at the end lists the corresponding URLs.
- No manual copying of links or formatting is required.

## Troubleshooting

- **No papers found**: Try a different or broader research question.
- **Empty abstract**: The arXiv abstract page may have changed; the agent will warn and skip that paper.
- **Heremes command not found**: Ensure Hermes is installed and its executable is in your PATH.
- **Errors about missing modules**: The script relies only on the Python standard library and the Hermes‑provided `hermes_tools` module, which is available when running inside Hermes.

## License

MIT – feel free to adapt and extend.
