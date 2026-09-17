#!/usr/bin/env python3
import asyncio
import logging
import os
import random

from telethon import TelegramClient
from telethon.errors import FloodWaitError, PersistentTimestampOutdatedError
from telethon.tl.functions.account import UpdateProfileRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("rotator")

SESSION = os.environ.get("TG_SESSION", "session.session")
PHRASES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "phrases.txt")
MIN_DELAY = int(os.environ.get("MIN_DELAY", "3"))
MAX_DELAY = int(os.environ.get("MAX_DELAY", "10"))
API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
REQUEST_TIMEOUT = 15
BIO_LIMIT = 70
MAX_FAILS = 3

_phrases_mtime = 0


def load_phrases():
    global _phrases_mtime
    try:
        m = os.path.getmtime(PHRASES_FILE)
        if m == _phrases_mtime:
            return None
        _phrases_mtime = m
        with open(PHRASES_FILE, encoding="utf-8") as f:
            phrases = [line.strip() for line in f if line.strip()]
        return phrases or ["shpateil.fun"]
    except OSError:
        log.warning("не удалось прочитать файл фраз")
        return None


def build_about(idx, total, phrase):
    about = f"{idx + 1}/{total} {phrase} | shpateil.fun"
    return about[:BIO_LIMIT]


async def main():
    phrases = load_phrases()
    total = len(phrases)
    log.info("загружено фраз %d", total)

    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()
    log.info("подключено")

    idx = 0
    fails = 0
    while True:
        fresh = load_phrases()
        if fresh is not None and fresh != phrases:
            phrases = fresh
            total = len(phrases)
            idx = 0
            fails = 0
            log.info("обновлено фраз %d", total)

        phrase = phrases[idx]
        about = build_about(idx, total, phrase)
        try:
            await asyncio.wait_for(client(UpdateProfileRequest(about=about)), timeout=REQUEST_TIMEOUT)
            log.info("обновлено био %d/%d", idx + 1, total)
            idx = (idx + 1) % total
            fails = 0
            await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
        except FloodWaitError as e:
            log.warning("ожидание %s с", e.seconds)
            await asyncio.sleep(e.seconds + 5)
        except PersistentTimestampOutdatedError:
            await asyncio.sleep(5)
        except asyncio.TimeoutError:
            fails += 1
            log.warning("таймаут %d/%d", fails, MAX_FAILS)
            if fails >= MAX_FAILS:
                idx = (idx + 1) % total
                fails = 0
            await asyncio.sleep(5)
        except Exception as e:
            fails += 1
            log.error("ошибка %s %d/%d", type(e).__name__, fails, MAX_FAILS)
            if fails >= MAX_FAILS:
                idx = (idx + 1) % total
                fails = 0
                await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
            else:
                await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())
