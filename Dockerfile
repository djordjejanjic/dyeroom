# Dyeroom web app for a Linux server.
#   docker build -t dyeroom .
#   docker run -p 8000:8000 -v dyeroom-data:/data --tmpfs /work:size=8g dyeroom
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 libimage-exiftool-perl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md LICENSE SOURCES.md ./
COPY dyeroom ./dyeroom
COPY samples ./samples
RUN pip install ".[web,colourise]"

# The emulsion fit and the spectral lattices ship with the code (data/cache); this makes any that
# are missing or out of date, once, at build time.
RUN python -c "from dyeroom import film, spectra; film.load(); [spectra.reflectance_lattice(cct=k) for k in (None, *spectra.LATTICE_LIGHTS)]"

RUN useradd --create-home dyeroom && mkdir /data /work && chown dyeroom /data /work
USER dyeroom
ENV DYEROOM_DATA=/data DYEROOM_WORK=/work DYEROOM_SAMPLE=/app/samples/sample-olympus-e-p7.orf HOST=0.0.0.0 PORT=8000
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["dyeroom-web"]
