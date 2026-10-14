# MCP server for usb-rea (stdio). Analysis works on capture files; live capture/replay
# needs USB access on the host (run with --privileged -v /dev/bus/usb:/dev/bus/usb).
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir ".[mcp]"
ENTRYPOINT ["usb-rea", "mcp"]
