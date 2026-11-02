# Multi-platform image: linux/amd64, linux/arm64 (Pi 4/5, 64-bit OS), linux/arm/v7 (32-bit Pi OS)
FROM python:3.9

WORKDIR /home/admin/mcscale

# Install system packages
RUN apt-get update \
    && apt-get install -y --no-install-recommends iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements-runtime.txt .

# Install dependencies (cached by Docker layer if unchanged)
RUN pip install --no-cache-dir -r requirements-runtime.txt

# Copy app code (.dockerignore keeps .env, caches and dev files out)
COPY . .

CMD ["python", "-u", "main.py"]

# ---------------------------------------------------------------------------
# Build & push for all platforms (works from Windows, Linux or Mac with buildx)
#
# One-time setup (creates a builder that can target other CPUs via QEMU):
#   docker buildx create --name multiarch --driver docker-container --use --bootstrap
#   # Linux hosts only (Docker Desktop already has this):
#   docker run --privileged --rm tonistiigi/binfmt --install all
#
# Build + push a multi-arch image:
#   docker buildx build --platform linux/amd64,linux/arm64,linux/arm/v7 -t mochigome/mcscale:1.2.3v -t mochigome/mcscale:latest --push .
#
# Verify which platforms the pushed tag contains:
#   docker buildx imagetools inspect mochigome/mcscale:1.2.3v
# ---------------------------------------------------------------------------
