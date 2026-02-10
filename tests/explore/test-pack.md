# Test a Pack

Test an OneTool pack — find defects and suggest improvements.

Start with `ot.agent_hints()` then `ot.tools(pattern="{pack}", info="full")`.

Run each tool in the pack with realistic inputs. Note errors, edge cases, and UX issues.

Write findings to ./tmp/fix/{pack}-fix.md

Accepts comma-separated pack names as arguments (e.g., `brave,mem,db`).
