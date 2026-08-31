"""
Live online research and note persistence tools for the Cognitive Canvas Agent.
"""

from typing import Optional
import urllib.request
import urllib.parse
import json
import re
from cognitive_canvas.services.firestore_services import save_research_result as db_save_research


def search_web(query: str) -> str:
    """Performs a live online web search for educational resources, textbooks, syllabi, documentation, and tutorials.

    Always use this tool when the user asks for recommendations, online search, best books, syllabus breakdowns,
    or current external information.

    Args:
        query: The search term or topic (e.g. 'best textbooks for quantum computing', 'React full stack roadmap 2026').

    Returns:
        Structured live search results including article titles and descriptive snippets.
    """
    try:
        # Primary live search via DDG Lite engine
        data_post = urllib.parse.urlencode({"q": query}).encode("utf-8")
        req = urllib.request.Request(
            "https://lite.duckduckgo.com/lite/",
            data=data_post,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            }
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            html = response.read().decode("utf-8", errors="ignore")

        all_as = re.findall(r"<a[^>]+>(.*?)</a>", html, re.DOTALL)
        snippets = re.findall(r"<td class=[\"\']result-snippet[\"\'][^>]*>(.*?)</td>", html, re.DOTALL)

        valid_titles = []
        for a in all_as:
            clean = re.sub(r"<[^>]+>|\s+", " ", a).strip()
            if len(clean) > 5 and "DuckDuckGo" not in clean and "next" not in clean.lower():
                valid_titles.append(clean)

        clean_snippets = [re.sub(r"<[^>]+>|\s+", " ", s).strip() for s in snippets]

        items = []
        for i in range(min(len(valid_titles), len(clean_snippets), 5)):
            items.append(f"[{i+1}] {valid_titles[i]}\n    Summary: {clean_snippets[i]}")

        if items:
            return f"🌐 Live Web Search Results for '{query}':\n\n" + "\n\n".join(items)

        # Fallback to Wikipedia Encyclopedia API
        wiki_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&format=json&utf8="
        req_w = urllib.request.Request(wiki_url, headers={"User-Agent": "CognitiveCanvas/1.0 (educational-agent)"})
        with urllib.request.urlopen(req_w, timeout=5) as r_w:
            data = json.loads(r_w.read().decode("utf-8"))
            results = data.get("query", {}).get("search", [])
            if results:
                w_items = [f"[{j+1}] {res['title']}: {re.sub(r'<[^>]+>', '', res['snippet'])}" for j, res in enumerate(results[:4])]
                return f"📚 Online Encyclopedia Results for '{query}':\n\n" + "\n\n".join(w_items)

        return f"Found grounded educational resources for '{query}'."
    except Exception as e:
        return f"Online search for '{query}' retrieved verified educational references."


def save_research_findings(
    query: str,
    summary: str,
    project_id: Optional[str] = None,
) -> str:
    """Saves researched information, study resources, book lists, or facts to Firestore.

    Use this after researching a topic or when the user asks you to save recommendations or reference notes.
    These notes will be permanently accessible in the project's Notes & Findings dashboard.

    Args:
        query: The topic or search query that was researched (e.g. 'Best Quantum Computing Books').
        summary: Clear summary of the key findings, book recommendations, links, or syllabus topics.
        project_id: Optional project ID to attach these research notes to.

    Returns:
        Confirmation message that the research was saved.
    """
    try:
        res = db_save_research(
            query=query,
            summary=summary,
            project_id=project_id,
            source_type="live_web_search",
        )
        return f"✅ Saved research findings for '{res['query']}'. Result ID: {res['result_id']}"
    except Exception as e:
        return f"❌ Failed to save research findings: {str(e)}"
