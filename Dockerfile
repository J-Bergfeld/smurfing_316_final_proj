FROM python:3.13-slim
WORKDIR /bot
COPY main.py mechfight.py ./
COPY bot ./bot
ENV PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["python3", "-u", "/bot/main.py"]
