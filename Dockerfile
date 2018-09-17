FROM edxops/discovery:latest

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
        graphviz \
    && rm -rf /var/lib/apt/lists/*
