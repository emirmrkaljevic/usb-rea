# Stdio MCP server for Glama / local Docker use.
# Build: docker build -t usb-rea .
# Run:   docker run --rm -i usb-rea          (analysis of capture files)
# Live capture/replay needs host USB access: add --privileged -v /dev/bus/usb:/dev/bus/usb
FROM python:3.12-slim-bookworm

# libusb is needed by pyusb for replay/scaffolded drivers; analysis works without it
RUN apt-get update && apt-get install -y --no-install-recommends libusb-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir ".[mcp]"

RUN useradd --create-home --uid 1000 app
USER app
WORKDIR /home/app

ENTRYPOINT ["usb-rea", "mcp"]
