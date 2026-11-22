FROM python:3.13-slim
WORKDIR /bot
COPY main.py mechfight.py ./
COPY bot ./bot
ENV PYTHONDONTWRITEBYTECODE=1 \
    BOT_NAV_METHOD=legacy \
    BOT_GUN_AIM_CHECK=actual \
    BOT_SUPPLY_DROPS=0
ENTRYPOINT ["python3", "-u", "/bot/main.py"]
