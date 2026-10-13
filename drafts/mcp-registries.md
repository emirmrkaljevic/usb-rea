<!-- DRAFTS — submissions need Emir's OK. Prereq for the official registry and Smithery: a PyPI release
     (`pip install usb-rea`), which also needs Emir's OK. -->

## 1. Official MCP Registry (registry.modelcontextprotocol.io) via `mcp-publisher`
Requires PyPI package with `<!-- mcp-name: io.github.emirmrkaljevic/usb-rea -->` in the README.
`server.json`:
```json
{
  "$schema": "https://static.modelcontextprotocol.io/schemas/2025-09-29/server.schema.json",
  "name": "io.github.emirmrkaljevic/usb-rea",
  "description": "Reverse engineer USB gadgets: capture traffic, infer the protocol with evidence, generate a pyusb driver.",
  "repository": {"url": "https://github.com/emirmrkaljevic/usb-rea", "source": "github"},
  "version": "0.1.0",
  "packages": [{
    "registryType": "pypi", "identifier": "usb-rea", "version": "0.1.0",
    "transport": {"type": "stdio"}, "runtimeHint": "uvx",
    "packageArguments": [{"type": "positional", "value": "mcp"}]
  }]
}
```

## 2. Glama (glama.ai/mcp/servers) — "Add server" with the GitHub URL. Needed for the score badge that punkpeye/awesome-mcp-servers entries carry.
## 3. Smithery (smithery.ai) — add `smithery.yaml`:
```yaml
startCommand:
  type: stdio
  configSchema: {type: object, properties: {}}
  commandFunction: |-
    (config) => ({command: "uvx", args: ["--from", "usb-rea[mcp]", "usb-rea", "mcp"]})
```
## 4. mcp.so — "Submit" form: name `usb-rea`, URL repo, category Developer Tools / Hardware.
## 5. PulseMCP — submit form with repo URL.

**Common blurb (≤200 chars):** Reverse engineer Windows-only USB gadgets: capture vendor-app traffic, infer the protocol with frame-level evidence, and generate an open Python/pyusb driver. Replay needs human confirmation.
**Tools:** capture_start, capture_stop, mark_action, diff_actions, report, scaffold_driver, replay_packet
