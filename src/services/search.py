"""
Web search service - Perplexity-style search with AI summarization.
Free, no API key required for search.

Flow:
1. Search DuckDuckGo for results
2. Fetch content from top pages
3. Pass to AI for intelligent summarization with sources
"""
import httpx
import re
import asyncio
from urllib.parse import quote, urlparse, unquote, parse_qs
from src.services.llm import llm_service


# System prompt for AI summarization
SEARCH_SYSTEM_PROMPT = """You are a helpful AI assistant that answers questions based on web search results.

RULES:
1. Answer the user's question using ONLY the provided search results
2. Be concise but comprehensive
3. ALWAYS cite sources using [1], [2], etc. format inline
4. If information conflicts, mention both perspectives
5. If the search results don't contain enough info, say so
6. Respond in the SAME LANGUAGE as the user's question
7. Format response clearly with paragraphs
8. Do NOT make up information not in the sources

RESPONSE FORMAT:
- Start with a direct answer
- Provide details with citations [1], [2] etc.
- Keep it under 500 words
"""


def _extract_real_url(ddg_url: str) -> str | None:
    """
    Extract real URL from DuckDuckGo redirect link.
    
    DuckDuckGo uses links like:
    - //duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpage&rut=...
    - /l/?uddg=https%3A%2F%2Fexample.com
    - Direct URLs (https://example.com)
    """
    if not ddg_url:
        return None
    
    # Already a direct URL
    if ddg_url.startswith("http://") or ddg_url.startswith("https://"):
        return ddg_url
    
    # Handle //duckduckgo.com/l/? or /l/? redirects
    try:
        # Try to find uddg parameter
        if "uddg=" in ddg_url:
            # Extract the uddg parameter value
            if "?" in ddg_url:
                query_part = ddg_url.split("?", 1)[1]
                params = parse_qs(query_part)
                if "uddg" in params:
                    real_url = unquote(params["uddg"][0])
                    if real_url.startswith("http"):
                        return real_url
        
        # Fallback: try regex
        match = re.search(r'uddg=([^&]+)', ddg_url)
        if match:
            real_url = unquote(match.group(1))
            if real_url.startswith("http"):
                return real_url
        
        # If starts with //, add https:
        if ddg_url.startswith("//"):
            return "https:" + ddg_url
            
    except Exception as e:
        print(f"[Search] URL extract error: {e}")
    
    return None


async def search_duckduckgo(query: str, num_results: int = 5) -> list[dict]:
    """
    Search DuckDuckGo and return results.
    Returns list of {title, url, snippet}.
    """
    try:
        search_url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(search_url, headers=headers, timeout=15)
            response.raise_for_status()
            html = response.text
        
        results = []
        
        # Parse result links and snippets
        # DuckDuckGo uses redirect URLs like //duckduckgo.com/l/?uddg=REAL_URL
        link_pattern = r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>(.+?)</a>'
        snippet_pattern = r'<a class="result__snippet"[^>]*>(.+?)</a>'
        
        links = re.findall(link_pattern, html, re.DOTALL)
        snippets = re.findall(snippet_pattern, html, re.DOTALL)
        
        for i, (raw_url, title) in enumerate(links[:num_results]):
            # Extract actual URL from DuckDuckGo redirect
            actual_url = _extract_real_url(raw_url)
            if not actual_url:
                continue
            
            snippet = snippets[i] if i < len(snippets) else ""
            # Clean HTML tags from title and snippet
            title = re.sub(r'<[^>]+>', '', title).strip()
            snippet = re.sub(r'<[^>]+>', '', snippet).strip()
            snippet = ' '.join(snippet.split())  # Normalize whitespace
            
            results.append({
                "title": title,
                "url": actual_url,
                "snippet": snippet[:300]
            })
        
        print(f"[Search] Found {len(results)} results for: {query}")
        return results
        
    except Exception as e:
        print(f"[Search] DuckDuckGo error: {e}")
        return []


async def fetch_page_content(url: str, max_chars: int = 1000) -> str | None:
    """
    Fetch and extract main text content from a URL.
    Returns cleaned text or None on error.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9,ru;q=0.8"
        }
        
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, headers=headers, timeout=10)
            
            # Check content type
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type:
                return None
            
            html = response.text
        
        # Remove script, style, nav, footer, header tags
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<nav[^>]*>.*?</nav>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<footer[^>]*>.*?</footer>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<header[^>]*>.*?</header>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<aside[^>]*>.*?</aside>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
        
        # Extract text from remaining HTML
        # Get content from <p>, <article>, <main>, <div> tags
        paragraphs = re.findall(r'<(?:p|article|main|h[1-6])[^>]*>(.*?)</(?:p|article|main|h[1-6])>', html, flags=re.DOTALL | re.IGNORECASE)
        
        if not paragraphs:
            # Fallback: just strip all tags
            text = re.sub(r'<[^>]+>', ' ', html)
        else:
            text = ' '.join(paragraphs)
            text = re.sub(r'<[^>]+>', ' ', text)
        
        # Clean up
        text = re.sub(r'\s+', ' ', text).strip()
        text = re.sub(r'[^\w\s.,!?;:()\[\]{}"\'-]', '', text)
        
        # Limit length
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
        
        return text if len(text) > 100 else None
        
    except Exception as e:
        print(f"[Search] Fetch error for {url[:50]}: {e}")
        return None


async def fetch_multiple_pages(urls: list[str], max_concurrent: int = 3) -> dict[str, str]:
    """
    Fetch content from multiple URLs concurrently.
    Returns dict of {url: content}.
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def fetch_with_semaphore(url: str) -> tuple[str, str | None]:
        async with semaphore:
            content = await fetch_page_content(url)
            return url, content
    
    tasks = [fetch_with_semaphore(url) for url in urls]
    results = await asyncio.gather(*tasks)
    
    return {url: content for url, content in results if content}


async def search_and_summarize(query: str, num_results: int = 5, model: str | None = None) -> str:
    """
    Main search function - Perplexity-style search with AI summarization.
    
    Args:
        query: Search query
        num_results: Number of results to fetch
        model: LLM model to use (uses default if None)
    """
    # Step 1: Search
    results = await search_duckduckgo(query, num_results=num_results)
    
    if not results:
        return f"🔍 Ничего не найдено по запросу: _{query}_\n\n💡 Попробуйте:\n• Другие ключевые слова\n• Более простой запрос\n• Английский язык"
    
    # Step 2: Fetch page content
    urls = [r["url"] for r in results]
    page_contents = await fetch_multiple_pages(urls)
    
    # Step 3: Build context for AI
    sources_context = []
    source_list = []
    
    for i, result in enumerate(results, 1):
        url = result["url"]
        title = result["title"]
        snippet = result["snippet"]
        
        # Get page content or fall back to snippet
        content = page_contents.get(url, snippet)
        if not content:
            content = snippet
        
        sources_context.append(f"[{i}] {title}\nURL: {url}\nContent: {content}\n")
        # Full URL instead of just domain
        source_list.append(f"[{i}] {title}\n🔗 {url}")
    
    # Step 4: AI Summarization
    full_context = "\n---\n".join(sources_context)
    
    ai_prompt = f"""User question: {query}

Search results:
{full_context}

Based on these search results, answer the user's question. Remember to cite sources using [1], [2] etc."""

    try:
        messages = [
            {"role": "system", "content": SEARCH_SYSTEM_PROMPT},
            {"role": "user", "content": ai_prompt}
        ]
        
        # Use provided model or default
        summary = await llm_service.get_response(messages, model=model)
        
        # Format final response
        response = f"🔍 *{query}*\n\n{summary}\n\n"
        response += "━━━━━━━━━━━━━━━\n📚 *Источники:*\n"
        response += "\n".join(source_list)
        
        return response
        
    except Exception as e:
        print(f"[Search] AI summarization error: {e}")
        # Fallback to simple results
        return await _format_simple_results(query, results)


async def _format_simple_results(query: str, results: list[dict]) -> str:
    """Fallback: format results without AI."""
    lines = [f"🔍 *Результаты:* _{query}_\n"]
    
    for i, r in enumerate(results, 1):
        domain = urlparse(r["url"]).netloc.replace("www.", "")
        lines.append(f"{i}. *{r['title']}*")
        if r['snippet']:
            lines.append(f"   {r['snippet'][:150]}...")
        lines.append(f"   🔗 {domain}\n")
    
    return "\n".join(lines)


async def quick_search(query: str) -> str:
    """
    Quick search without fetching pages - just snippets.
    Faster but less accurate.
    """
    results = await search_duckduckgo(query, num_results=3)
    
    if not results:
        return f"Ничего не найдено: {query}"
    
    # Use snippets only
    snippets = [f"[{i}] {r['title']}: {r['snippet']}" for i, r in enumerate(results, 1)]
    context = "\n".join(snippets)
    
    ai_prompt = f"Question: {query}\n\nSearch snippets:\n{context}\n\nProvide a brief answer based on these snippets. Cite sources."
    
    try:
        summary = await llm_service.get_response([
            {"role": "system", "content": SEARCH_SYSTEM_PROMPT},
            {"role": "user", "content": ai_prompt}
        ], model="llama-3.3-70b-versatile")
        
        return f"🔍 _{query}_\n\n{summary}"
    except:
        return await _format_simple_results(query, results)
