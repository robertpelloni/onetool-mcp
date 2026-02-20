# Tool path configuration for skill stub installation
# Used by scaffold.skills() to determine where to write stub files.
# {name} is substituted with the skill name at install time.
#
# All tools follow the Agent Skills standard:
# skills live at {tool-config-dir}/skills/{name}/SKILL.md
# and are loaded on-demand — no slash commands required.
#
# Sources:
#   Claude Code:  platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
#   Codex:        developers.openai.com/codex/skills/
#   OpenCode:     opencode.ai/docs/skills/

tools:
  claude:
    stub_path: ".claude/skills/{name}/SKILL.md"
    description: "Claude Code"

  codex:
    # Codex searches .agents/skills/ (repo-level) and ~/.agents/skills/ (user-level)
    stub_path: ".agents/skills/{name}/SKILL.md"
    description: "OpenAI Codex CLI"

  opencode:
    # OpenCode also recognises .agents/skills/ and .claude/skills/ as fallbacks
    stub_path: ".opencode/skills/{name}/SKILL.md"
    description: "OpenCode (opencode.ai)"
