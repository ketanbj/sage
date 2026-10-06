FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates libgcc-s1 && \
    rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 10001 runner
USER runner
WORKDIR /work
ENTRYPOINT ["/bin/sh", "-c"]
