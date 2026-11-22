FROM python:3.13-slim
WORKDIR /bot
COPY main.py mechfight.py ./
COPY bot ./bot
ENV PYTHONDONTWRITEBYTECODE=1 \
    BOT_CORNERED_BOOST=1 \
    BOT_SQUAD_RECOVERY=cover \
    BOT_NAV_METHOD=spacing
ENTRYPOINT ["python3", "-u", "/bot/main.py"]
