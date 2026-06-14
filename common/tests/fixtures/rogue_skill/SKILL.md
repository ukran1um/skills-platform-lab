---
name: rogue_skill
version: 0.1.0
owner: egor
blast_radius: low
allowed_mcp_servers: [data_mcp]
required_scopes: [prices:read]
eval:
  golden_set: evals/golden.yaml
  threshold: 0.8
---

# Rogue Skill

Its frontmatter declares only data_mcp, but its code reaches an undeclared MCP server.
