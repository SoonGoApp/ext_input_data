ARG PYTHON_VERSION="3.12-slim"

FROM python:${PYTHON_VERSION} AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    clang \
    lld \
    libssl-dev \
    libcurl4-openssl-dev \
    libsasl2-dev \
    git \
    wget \
    python3-dev \
    cmake \
    ninja-build \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV CC=clang
ENV CXX=clang++

WORKDIR /tmp/librdkadka
RUN git clone \ 
        --depth=1 \
        --branch v2.11.0 \
        https://github.com/confluentinc/librdkafka.git . && \
    mkdir build && \
    cd build && \
    cmake .. \
        -G Ninja \
        -DCMAKE_C_COMPILER=clang \
        -DCMAKE_CXX_COMPILER=clang++ \
        -DCMAKE_INSTALL_PREFIX=/usr/local \
        -DWITH_SASL=ON \
        -DWITH_SSL=ON \
        -DBUILD_SHARED_LIBS=OFF && \
    ninja && \
    ninja install

RUN pip install \
    --no-cache-dir \
    --no-binary :all: \
    --prefix=/install \
    confluent-kafka~=2.1.1

FROM python:${PYTHON_VERSION} AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsasl2-2 \
    libcurl4 \
    libssl3 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local /usr/local
COPY --from=builder /install /usr/local

ENV LD_LIBRARY_PATH="/usr/local/lib"


WORKDIR /app
COPY . .