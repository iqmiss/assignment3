# syntax=docker/dockerfile:1
#
# HODE container image.
#
#   docker build -t hode:local .
#   docker run --rm hode:local                          # synthetic k = 2, 3 sweep + verify + plot
#   docker run --rm hode:local hode --version
#   docker run --rm -v "$PWD/out:/app/results" hode:local   # keep the results on the host
#
# Three stages:
#   builder  - builds the wheel from the source tree
#   test     - installs the wheel with dev tools and runs lint + the test suite
#              (docker build --target test .  fails if any test fails)
#   runtime  - small image with only the wheel and the pinned runtime libraries
#
# The runtime libraries are pinned in requirements.lock, so the image built
# today and the image built in a year contain the same numpy/scipy/pandas
# (and matplotlib, which hode plot uses to draw the heatmaps).

ARG PYTHON_VERSION=3.13

# ---------------------------------------------------------------- builder
FROM python:${PYTHON_VERSION}-slim AS builder
WORKDIR /src
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN pip install "build>=1.2"
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m build --wheel --outdir /dist

# ---------------------------------------------------------------- test
FROM python:${PYTHON_VERSION}-slim AS test
WORKDIR /src
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
COPY requirements.lock ./
RUN pip install -r requirements.lock "pytest>=8" "pytest-cov>=5" "ruff>=0.6"
COPY . .
RUN pip install -e . --no-deps \
 && ruff check . \
 && pytest -q --cov

# ---------------------------------------------------------------- runtime
FROM python:${PYTHON_VERSION}-slim AS runtime

LABEL org.opencontainers.image.title="hode" \
      org.opencontainers.image.description="Higher-order determinant discovery on count tables" \
      org.opencontainers.image.source="https://github.com/iqmiss/assignment3" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MPLCONFIGDIR=/tmp/matplotlib

WORKDIR /app
COPY requirements.lock ./
COPY --from=builder /dist/*.whl /tmp/
RUN pip install -r requirements.lock \
 && pip install --no-deps /tmp/*.whl \
 && rm -f /tmp/*.whl

COPY configs ./configs
COPY docker/entrypoint.sh /usr/local/bin/hode-pipeline

# Run as an unprivileged user; results/ is the only writable place.
RUN useradd --create-home --uid 10001 hode \
 && mkdir -p /app/results \
 && chown -R hode:hode /app \
 && sed -i 's/\r$//' /usr/local/bin/hode-pipeline \
 && chmod 755 /usr/local/bin/hode-pipeline
USER 10001

VOLUME ["/app/results"]
# Default: the reproducible synthetic sweep, the hash check, then the heatmaps.
CMD ["hode-pipeline", "configs/synthetic.toml"]
