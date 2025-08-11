FROM mambaorg/micromamba:1.5.8

ARG MAMBA_DOCKERFILE_ACTIVATE=1
WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN micromamba install -y -n base -c conda-forge python=3.11 && \
    pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

ENV DJANGO_SETTINGS_MODULE=bioai_platform.settings

EXPOSE 8000