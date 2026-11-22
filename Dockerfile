FROM python:3.13-slim
WORKDIR /bot
COPY main.py mechfight.py ./
COPY bot ./bot
ENV PYTHONDONTWRITEBYTECODE=1 \
    BOT_POLICY=integrated \
    BOT_NAV_METHOD=legacy \
    BOT_GUN_AIM_CHECK=actual \
    BOT_AIM_MODEL=dev \
    BOT_SUPPLY_DROPS=1 \
    BOT_CORNER_DUEL=1 \
    BOT_POSITIONAL_FIELD=1 \
    BOT_FIGHT_CORRIDOR=0 \
    BOT_EARLY_DRONE=0 \
    BOT_SAFE_COMBAT_CUBES=1 \
    BOT_CUBE_UPGRADE_VALUE=1
ENTRYPOINT ["python3", "-u", "/bot/main.py"]
