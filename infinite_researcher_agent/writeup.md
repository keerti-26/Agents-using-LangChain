#### Problem:
The original agent was stuck in a loop. Every time it searched the web or read a page, the tools would suggest "Related Searches" or "More Reading". Because the agent didn't have a clear stopping constraint it treated every suggestion as a new mandatory task. This caused it to keep researching forever, which quickly drained the API budget and eventually made the program crash when it ran out of memory (the token limit).

#### Approach to resolve the issue:

- I have implemented the guardrails by adding max_iteration = 5. It forces the agent to limit total number of search calls, reads and move toward a conclusion regardless of how many "Related searches"
  it sees
- Added early_stopping_method = "generate" to make sure agent doesnt crash after reaching the limit it refers internal scratchpad and gives the final response.
- I updated the system instructions to tell the agent to trust its first search and stop after 2-3 sources. This changes the agent's mindset from trying to find everything to just finding enough to answer the question.
- Changed the read_webpage output to 2 sentence summary that reduced the number of tokens and kept the memory clean