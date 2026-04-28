#### Problem:
There were couple of problems in the code:
1. Every time user asks a question all the 25 tools were loaded in the context consuming approximately 2209 of tokens resulting in Context exhaustion.
2. Because of similar tools LLM was getting confused which tool to pick and it was processing 25 json schemas which slowed it down.
3. It was also calling wrong tools sometimes

#### Resolution:
1. First we tried to limit the number of tools passed to LLM context by adding an agent which understands user requests and dynamically
   chose the relevant MCP server
2. We have tried to explain to the agent when to choose which MCP server based on the avaialble tools 
3. Then we created a middleware function that serves as the entry point to the agent mentioned above.This middleware layer gave us the    selected tools for LLM context 
4. We then pass this list as a tool to LLM function which ultimately reduced the tokens as well as LLM confusion to choose relevant tools