FROM python:3.12-slim
RUN pip install "onetool-mcp[all]" && onetool init --config /onetool/onetool.yaml
ENTRYPOINT ["onetool", "--config", "/onetool/onetool.yaml"]
