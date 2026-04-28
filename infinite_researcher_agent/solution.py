"""
Assignment 2: The Infinite Researcher
======================================
This research agent searches the web and compiles reports, but it NEVER STOPS.
It keeps exploring deeper and deeper until it crashes or drains your API budget.

Run this and observe the runaway behavior:
    python starter.py

Your job: Add stopping conditions, cost controls, and fix the prompt.
"""

import os
import time
from typing import Optional
import uuid
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool



from dotenv import load_dotenv
load_dotenv()

# ---------------------------------------------------------------------------
# Simulated web search & reading (no real API calls needed for testing)
# ---------------------------------------------------------------------------

_SIMULATED_SEARCH_RESULTS = {
    "default": [
        {"title": "Comprehensive Guide to {topic}", "url": "https://example.com/guide", "snippet": "An in-depth look at {topic} covering all major aspects..."},
        {"title": "{topic}: What Experts Say", "url": "https://example.com/experts", "snippet": "Leading researchers weigh in on {topic}..."},
        {"title": "The History and Future of {topic}", "url": "https://example.com/history", "snippet": "From its origins to modern developments, {topic} has evolved..."},
        {"title": "10 Things You Didn't Know About {topic}", "url": "https://example.com/10things", "snippet": "Surprising facts and lesser-known aspects of {topic}..."},
        {"title": "{topic} vs Alternatives: A Deep Dive", "url": "https://example.com/comparison", "snippet": "How does {topic} compare to competing approaches..."},
    ]
}

_SEARCH_CALL_COUNT = 0
_READ_CALL_COUNT = 0


@tool
def web_search(query: str) -> str:
    """Search the web for information on a topic.

    Args:
        query: Search query string.
    """
    global _SEARCH_CALL_COUNT
    _SEARCH_CALL_COUNT += 1

    results = []
    for r in _SIMULATED_SEARCH_RESULTS["default"]:
        results.append(
            f"  - [{r['title'].format(topic=query)}]({r['url']})\n"
            f"    {r['snippet'].format(topic=query)}"
        )

    # Every search returns results that hint at MORE things to explore
    return (
        f"Search results for '{query}' ({len(results)} results):\n\n"
        + "\n".join(results)
        + f"\n\nRelated searches: '{query} advanced techniques', "
        f"'{query} common pitfalls', '{query} case studies', "
        f"'{query} latest research 2026', '{query} expert opinions', "
        f"'{query} implementation details', '{query} theoretical foundations'"
    )


@tool
def read_webpage(url: str) -> str:
    """Read and extract content from a webpage.

    Args:
        url: The URL to read.
    """
    global _READ_CALL_COUNT
    _READ_CALL_COUNT += 1

    # Simulated page content that always suggests more avenues to explore
    return (
       f"Key Summary from {url}: [the article discusses X,Y and Z]."
       "Provide 2 sentence takeaway only to save space"
    )

@tool
def save_notes(content: str) -> str:
    """Save research notes for later compilation into the final report.

    Args:
        content: The research notes to save.
    """
    # In the real version this writes to a file; here we just acknowledge
    return f"✅ Notes saved ({len(content)} chars). Provide the final report if you have enough info."


# ---------------------------------------------------------------------------
# 🐛 THE BROKEN AGENT has been fixed here
# ---------------------------------------------------------------------------

def create_research_agent():
    session_id = str(uuid.uuid4())
    llm =  ChatOpenAI(
        model='gpt-4o-mini',
        temperature=0,
        max_tokens=1000,
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("BASE_URL"),
        streaming=True,
        default_headers={
            "X-Session-ID": session_id
        }
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         """You are a research agent. Your goal is to answer the user's question 
    accurately and concisely.

    Your research methodology:
    - Search for relevant, high-quality sources
    - Do not perform multiple searches for the same concept using different keywords. Trust your initial search results.
    - You have a strict budget so stop after consulting 2-3 sources maximum
    - Once you have enough to answer the question confidently, stop researching
    - Prefer depth on a few good sources over breadth across many
    - When you can answer the question, stop immediately
    - If you are running out of itereations, provide a high-level summary using bullet points immediately
    - Keep the note in internal scratchpad and output the final report directly

    You are not being graded on how many sources you find. 
    A concise, accurate answer from 4 sources is better than an 
    incomplete answer from 20 sources.

     """),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    tools = [web_search, read_webpage]
    agent = create_tool_calling_agent(llm, tools, prompt)

    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=4,
        max_execution_time=120,
        early_stopping_method="generate"
    )


# ---------------------------------------------------------------------------
# Test queries
# ---------------------------------------------------------------------------

TEST_QUERIES = [
    "What are the pros and cons of microservices architecture?",
    "Summarize the current state of quantum computing in 2026.",
]


def main():
    global _SEARCH_CALL_COUNT, _READ_CALL_COUNT
    agent = create_research_agent()

    for query in TEST_QUERIES:
        _SEARCH_CALL_COUNT = 0
        _READ_CALL_COUNT = 0
        start_time = time.time()

        print(f"\n{'='*60}")
        print(f"QUERY: {query}")
        print(f"{'='*60}")

        try:
            result = agent.invoke({"input": query})
            print(f"\nRESPONSE: {result['output']}")
        except Exception as e:
            print(f"\n❌ ERROR: {e}")

        elapsed = time.time() - start_time
        print(f"\n📊 Stats:")
        print(f"   Search calls: {_SEARCH_CALL_COUNT}")
        print(f"   Page reads:   {_READ_CALL_COUNT}")
        print(f"   Time:         {elapsed:.1f}s")
        print(f"   (Imagine each search = $0.01, each LLM call = $0.05)")
        print(f"   Estimated cost: ${_SEARCH_CALL_COUNT * 0.01 + (_SEARCH_CALL_COUNT + _READ_CALL_COUNT) * 0.05:.2f}")


if __name__ == "__main__":
    main()
