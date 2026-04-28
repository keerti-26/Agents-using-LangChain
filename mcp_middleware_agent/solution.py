"""
Assignment 3: MCP Tool Overload
================================
This agent connects to 3 MCP servers with 53 total tools.
All tools are injected into every prompt, causing confusion, latency, and cost.

Run this and observe the tool confusion:
    python starter.py

Your job: Build middleware that dynamically selects the right tools per query.
"""

import json
import time
from typing import Any
import os
import uuid
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import StructuredTool, Tool
from pydantic import BaseModel, Field

from dotenv import load_dotenv
load_dotenv()


# ---------------------------------------------------------------------------
# Simulated MCP Server tool definitions
# ---------------------------------------------------------------------------

def _make_tool(name: str, description: str, server: str, params: dict[str, str]):
    """Create a simulated MCP tool."""
    # Build a dynamic Pydantic model for the tool's input schema
    fields = {}
    for param_name, param_desc in params.items():
        fields[param_name] = (str, Field(description=param_desc))

    InputModel = type(f"{name}_Input", (BaseModel,), {"__annotations__": {k: str for k in params}, **{k: Field(description=v) for k, v in params.items()}})

    def tool_func(**kwargs) -> str:
        return json.dumps({
            "server": server,
            "tool": name,
            "params": kwargs,
            "result": f"[Simulated {server} response for {name}]",
            "status": "success",
        }, indent=2)

    return StructuredTool.from_function(
        func=tool_func,
        name=name,
        description=f"[{server}] {description}",
        args_schema=InputModel,
    )


# --- GitHub MCP Server (18 tools) ---
GITHUB_TOOLS = [
    _make_tool("create_issue", "Create a new GitHub issue in a repository", "github",
               {"repo": "Repository name (owner/repo)", "title": "Issue title", "body": "Issue body/description"}),
    _make_tool("list_issues", "List issues in a GitHub repository", "github",
               {"repo": "Repository name (owner/repo)", "state": "Filter by state: open, closed, all"}),
    _make_tool("get_issue", "Get details of a specific GitHub issue", "github",
               {"repo": "Repository name (owner/repo)", "issue_number": "Issue number"}),
    _make_tool("create_pull_request", "Create a new pull request", "github",
               {"repo": "Repository name", "title": "PR title", "head": "Source branch", "base": "Target branch"}),
    _make_tool("list_pull_requests", "List pull requests in a repository", "github",
               {"repo": "Repository name", "state": "Filter: open, closed, all"}),
    _make_tool("merge_pull_request", "Merge a pull request", "github",
               {"repo": "Repository name", "pr_number": "PR number", "merge_method": "merge, squash, or rebase"}),
    _make_tool("search_code", "Search for code across GitHub repositories", "github",
               {"query": "Search query", "repo": "Optional: limit to specific repo"}),
    _make_tool("search_issues", "Search issues and PRs across GitHub", "github",
               {"query": "Search query", "repo": "Optional: limit to specific repo"})
]

# --- Slack MCP Server (15 tools) ---
SLACK_TOOLS = [
    _make_tool("send_message", "Send a message to a Slack channel", "slack",
               {"channel": "Channel name or ID", "text": "Message text"}),
    _make_tool("send_dm", "Send a direct message to a user", "slack",
               {"user": "User ID or username", "text": "Message text"}),
    _make_tool("list_channels", "List all Slack channels in the workspace", "slack",
               {"type": "public, private, or all"}),
    _make_tool("search_messages", "Search for messages across Slack", "slack",
               {"query": "Search query", "channel": "Optional: limit to channel"}),
    _make_tool("get_channel_history", "Get recent messages from a channel", "slack",
               {"channel": "Channel name or ID", "limit": "Number of messages"}),
    _make_tool("add_reaction", "Add an emoji reaction to a message", "slack",
               {"channel": "Channel ID", "timestamp": "Message timestamp", "emoji": "Emoji name"}),
]

# --- Database MCP Server (20 tools) ---
DATABASE_TOOLS = [
    _make_tool("query_sql", "Execute a read-only SQL query", "database",
               {"query": "SQL SELECT query", "database": "Database name"}),
    _make_tool("list_tables", "List all tables in a database", "database",
               {"database": "Database name"}),
    _make_tool("describe_table", "Get schema/columns of a table", "database",
               {"database": "Database name", "table": "Table name"}),
    _make_tool("insert_row", "Insert a new row into a table", "database",
               {"database": "Database name", "table": "Table name", "data": "JSON object of column:value pairs"}),
    _make_tool("update_rows", "Update rows matching a condition", "database",
               {"database": "Database name", "table": "Table name", "set_values": "JSON of updates", "where": "WHERE clause"}),
    _make_tool("delete_rows", "Delete rows matching a condition", "database",
               {"database": "Database name", "table": "Table name", "where": "WHERE clause"}),
    _make_tool("count_rows", "Count rows in a table with optional filter", "database",
               {"database": "Database name", "table": "Table name", "where": "Optional WHERE clause"}),
    _make_tool("get_table_stats", "Get statistics about a table (row count, size, indexes)", "database",
               {"database": "Database name", "table": "Table name"}),
    _make_tool("list_databases", "List all available databases", "database",
               {}),
    _make_tool("create_table", "Create a new table with specified schema", "database",
               {"database": "Database name", "table": "Table name", "schema": "JSON schema definition"}),
    _make_tool("drop_table", "Drop/delete a table (DANGEROUS)", "database",
               {"database": "Database name", "table": "Table name", "confirm": "Type 'yes' to confirm"})
]

# ---------------------------------------------------------------------------
# Adding a router function that determine which MCP server is needed
# ---------------------------------------------------------------------------
def classify_intent(user_query):
    """
    Act as router and determine which MCP servers are needed.
    """
    session_id = str(uuid.uuid4())
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("BASE_URL"),
        streaming=True,
        default_headers={
            "X-Session-ID": session_id
        }
    )
    prompt = ChatPromptTemplate.from_messages([
       ("system", """ You are a techinal query router. Your job is to look at the query and determine which
        tool categories are required to answer it.
        Categories:
        - 'github' : For repos, PRs, code search, issues
        - 'slack' : For message, channels,, or notifying teams
        - 'database' : For SQL, counts, tables, data logs.
        Rules:
        - Return a JSON list of strings(e.g ["github", "database"])
        - If unsure choose the one which you feel more relevant
        - Output the json list
       """),
       ("human", "{input}"),
       ("placeholder", "{agent_scratchpad}")
    ])
    agent = prompt | llm
    response = agent.invoke({"input":user_query})

    try:
        selected = json.loads(response.content.strip())
        return selected
    except:
        return["github", "slack", "database"]

TOOL_REGISTRY = {
    "github" : GITHUB_TOOLS,
    "slack" : SLACK_TOOLS,
    "database" : DATABASE_TOOLS
}
# ---------------------------------------------------------------------------
# Middleware function that is called during a user request which will give only selected tool
# ---------------------------------------------------------------------------
def middleware(query):
    """
    The main entry point for your dynamic tool selection.
    """
    selected_domains = classify_intent(query)
    active_tools=[]
    for domain in selected_domains:
        if domain in TOOL_REGISTRY:
            active_tools.extend(TOOL_REGISTRY[domain])
    print(f"Selected Middleware {selected_domains} and tools available {len(active_tools)}")
    total_desc_chars = sum(len(t.name) + len(t.description) + len(str(t.args_schema.model_json_schema())) for t in active_tools)
    estimated_tokens = total_desc_chars // 4  # rough estimate
    print(f"   Estimated tool description tokens: ~{estimated_tokens:,}")
    return active_tools


# ---------------------------------------------------------------------------
# 🐛 THE BROKEN AGENT that has been fixed
# ---------------------------------------------------------------------------

def create_overloaded_agent(current_tools):
    session_id = str(uuid.uuid4())
    llm = ChatOpenAI(
        model='gpt-4o-mini',
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("BASE_URL"),
        streaming=True,
        default_headers={
            "X-Session-ID": session_id
        }
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         """You are a high level manager. You have 3 specialists Github, Slack and Database.
         1 Read the user's request carefully delegate the task appropriately
         2 If a task requires multiple systems call them one by one."""),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_tool_calling_agent(llm, current_tools, prompt)
    return AgentExecutor(agent=agent, tools=current_tools, verbose=True)


# ---------------------------------------------------------------------------
# Test queries
# ---------------------------------------------------------------------------

TEST_QUERIES = [
    # Clear single-server queries
    "Create a GitHub issue in myorg/myapp titled 'Fix login bug' with body 'The login page crashes on mobile'",
    "Send a message to #engineering channel saying 'Deploy is complete'",
    "How many rows are in the users table in the production database?",

    # Ambiguous queries (which server?)
    "Search for anything related to the authentication bug",
    "Find all messages or issues about the deployment failure last Friday",

    # Cross-server queries
    "Find the latest GitHub issue about the payment bug and post a summary to #bugs channel on Slack",
    "Query the errors table in the database and create a GitHub issue for each critical error",
]


def main():
   
    for i, query in enumerate(TEST_QUERIES):
        print(f"\n{'='*60}")
        print(f"QUERY {i+1}/{len(TEST_QUERIES)}: {query}")
        print(f"{'='*60}")

        start_time = time.time()
        try:
            current_tools = middleware(query)
            dynamic_agent = create_overloaded_agent(current_tools)
            result = dynamic_agent.invoke({"input": query})
            print(f"\nRESPONSE: {result['output']}")
            print(f"   🔧 Tools available: {len(current_tools)} (selected tool)")
        except Exception as e:
            print(f"\n❌ ERROR: {e}")

        elapsed = time.time() - start_time
        print(f"   ⏱ Time: {elapsed:.1f}s")
        


if __name__ == "__main__":
    main()
