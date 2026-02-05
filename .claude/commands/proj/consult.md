---
name: Consult
description: Interactive consultation mode for research and Q&A. Can save findings on explicit request.
category: onetool
tags: [consultation, research, qa, findings]
---

**Assumptions**
- Uses openspec (`openspec/project.md` for context)
- Language agnostic

**Output Structure**
Findings are organized into two parts:

**Part 1: Recommendations**
- Detailed changes that will be implemented
- Starts EMPTY at the beginning of consultation
- Only filled in once the way forward is clear
- Written in enough detail to be used in an openspec proposal
- Should include specific file paths, function signatures, and implementation details

**Part 2: Analysis and Options**
- Research findings, discoveries, and explorations
- Filled during the consultation as you explore the codebase
- Include code references, patterns found, and architectural insights
- Present multiple options or approaches when applicable
- Note trade-offs, risks, and considerations

**Guardrails**
- This is primarily a READ-ONLY consultation session. You MUST NOT:
  - Make git commits or push changes
  - Run commands that modify the system (e.g., `git commit`, `rm`, `mv`, `npm install`)
  - Modify existing project source code
- You CAN and SHOULD:
  - Read files, search code, and explore the codebase
  - Run read-only commands (e.g., `git log`, `git status`, `git diff`, `ls`, `cat`)
  - Use web search for up-to-date information
  - Answer questions thoroughly with code references
  - Ask clarifying questions to understand user needs
- **Writing Findings (on explicit request only)**:
  - When the user explicitly asks to save, write, or document findings (e.g., "save these findings", "write this up", "document what we found"):
    - Suggest a descriptive filename based on the topic discussed
    - Write findings to `wip/consult/<name>.md`
    - Unless user specifies a different location
    - Use the two-part structure (Recommendations + Analysis)
    - Include dated heading and topic
  - Do NOT write findings unless the user explicitly requests it
- The session continues until the user explicitly ends it (e.g., "end consultation", "done consulting", "exit consult mode").

**Steps**
1. Begin the consultation:
   - Acknowledge entering consultation mode.
   - Briefly explain the read-only constraints and two-part structure.
   - Ask what the user would like to explore or discuss.

2. Research and explore (Part 2: Analysis and Options):
   - Listen to the user's question or topic.
   - Use read-only tools (Read, Glob, Grep, WebSearch, WebFetch, Task with Explore agent) to research.
   - Build up findings in Part 2: Analysis and Options:
     - Document discoveries, patterns, and code references
     - Present multiple approaches when applicable
     - Note trade-offs and considerations
   - Provide clear, detailed answers with file references where relevant.
   - Ask follow-up questions if clarification is needed.

3. Continue the dialogue:
   - After answering, check if the user has more questions.
   - Offer to dive deeper into related topics.
   - Suggest areas that might be worth exploring.
   - When the way forward becomes clear, offer to move to recommendations.

4. Formulate recommendations (Part 1: Recommendations):
   - Once the approach is decided:
     - Write detailed, actionable recommendations in Part 1
     - Include specific file paths, function signatures, implementation details
     - Make recommendations detailed enough to be used in an openspec proposal
     - Keep Part 2 as supporting analysis

5. Save findings (on explicit request):
   - When user asks to save/document findings:
     - Suggest a filename: "I'll save this as `wip/consult/<topic>.md` - sound good?"
     - Write using the two-part structure:
       ```markdown
       # [Topic] - [Date]

       ## Part 1: Recommendations
       [Detailed changes to implement - may be empty initially]

       ## Part 2: Analysis and Options
       [Research findings, discoveries, code references]
       ```
     - Confirm what was written

6. End the session:
   - When the user signals they are done (e.g., "end consultation", "done", "exit"):
     - Summarize key findings from the session.
     - Suggest next steps if applicable (e.g., creating a proposal, making changes).
     - Confirm the session has ended.

**Reference**
- Use exploration agents (Task with subagent_type=Explore) for open-ended codebase questions.
- Reference files using markdown link format: `[filename.ts](path/to/file.ts)`.
- For web research, cite sources in your answers.
- Cross-reference with `openspec/project.md` for project context when relevant.
