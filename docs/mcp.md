# MCP server

`pip install usb-rea` then add `usb-rea mcp` as a stdio server. The tools are `capture_start`, `capture_stop`, `mark_action`, `diff_actions`, `report`, `scaffold_driver`, `hid_descriptor` (decode a HID report descriptor / report payloads), `lookup_device` (is this VID:PID already documented? offline, OpenDeviceDB optional), `wireshark_dissector`, and `replay_packet` (refuses unless the human confirmed). Analysis tools accept the same `labels` argument as the CLI for marker-free captures.

With [uv](https://docs.astral.sh/uv/) no install step is needed:

```json
{"mcpServers": {"usb-rea": {"command": "uvx", "args": ["--from", "usb-rea", "usb-rea", "mcp"]}}}
```

For Claude Code: `claude mcp add usb-rea -- uvx --from usb-rea usb-rea mcp`. The server is also listed on the [official MCP Registry](https://registry.modelcontextprotocol.io/v0/servers?search=io.github.emirmrkaljevic/usb-rea) as `io.github.emirmrkaljevic/usb-rea` and on [Glama](https://glama.ai/mcp/servers/emirmrkaljevic/usb-rea), which builds it from the repo's `Dockerfile` and checks that it starts and lists its tools.

