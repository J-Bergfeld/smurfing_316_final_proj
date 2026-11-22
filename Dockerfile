FROM python:3.13-slim
# Practice baseline; experimental policy settings are declared below.
WORKDIR /bot
COPY main.py mechfight.py ./
COPY bot ./bot
ENV PYTHONDONTWRITEBYTECODE=1 \
    BOT_NAV_METHOD=legacy \
    BOT_GUN_AIM_CHECK=actual \
    BOT_SUPPLY_DROPS=0 \
    BOT_CORNER_DUEL=1 \
    BOT_POSITIONAL_FIELD=1 \
    BOT_FINISH_APPROACH=0 \
    BOT_RELOAD_COVER=0 \
    BOT_AIM_MODEL=dev \
    BOT_RELOAD_MODEL=sam \
    BOT_COVER_AIM=off \
    BOT_TARGET_POLICY=baseline \
    BOT_DUEL_SAFETY=off \
    BOT_FINISH_PRIORITY=off \
    BOT_SAFE_RETREAT=off \
    BOT_GUN_TIMING=current
ENTRYPOINT ["python3", "-u", "/bot/main.py"]
