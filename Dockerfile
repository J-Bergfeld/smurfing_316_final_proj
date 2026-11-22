FROM python:3.13-slim
WORKDIR /bot
COPY main.py mechfight.py ./
COPY bot ./bot
ENV PYTHONDONTWRITEBYTECODE=1 BOT_CORNERED_BOOST=1
ENTRYPOINT ["python3", "-u", "/bot/main.py"]
