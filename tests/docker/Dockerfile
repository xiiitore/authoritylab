FROM public.ecr.aws/docker/library/python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /src
COPY . /src
RUN python -m pip install --no-cache-dir /src \
    && mkdir -p /opt/authoritylab-test \
    && cp /src/tests/docker/test_docker_runtime_integration.py /opt/authoritylab-test/test_docker_runtime_integration.py \
    && chmod 0777 /opt/authoritylab-test
WORKDIR /opt/authoritylab-test
