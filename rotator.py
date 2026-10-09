#!/usr/bin/env python3
# ротатор био + вечный онлайн, быстро но без флуда
import asyncio
import logging
import os
import random
import time
from pathlib import Path

from telethon import TelegramClient
from telethon.tl.functions.account import UpdateProfileRequest, UpdateStatusRequest
from telethon.errors import FloodWaitError, PersistentTimestampOutdatedError

# тихо, иначе срет got difference по каждому каналу
logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s', datefmt='%H:%M:%S')
logging.getLogger('telethon').setLevel(logging.WARNING)
log = logging.getLogger('rotator')
log.setLevel(logging.INFO)

SESSION = os.environ.get('TG_SESSION', 'session.session')
PHRASES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'phrases.txt')
MIN_DELAY = int(os.environ.get('MIN_DELAY', '5'))
MAX_DELAY = int(os.environ.get('MAX_DELAY', '15'))
API_ID = int(os.environ.get('TG_API_ID', '2040'))
API_HASH = os.environ.get('TG_API_HASH', 'b18441a1ff607e10a989891a5462e627')
REQUEST_TIMEOUT = 15
BIO_LIMIT = 70
MAX_FAILS = 3
ONLINE_INTERVAL = int(os.environ.get('ONLINE_INTERVAL', '180'))
HEALTH_FILE = Path('/tmp/rotator_healthy')
IDX_FILE = Path(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.idx'))

_phrases_mtime = 0
_crash_count = 0
_last_crash_alert = 0.0


def _touch_health():
    try:
        HEALTH_FILE.write_text(str(int(time.time())))
    except Exception:
        pass


def load_phrases():
    global _phrases_mtime
    try:
        m = os.path.getmtime(PHRASES_FILE)
        if m == _phrases_mtime:
            return None
        _phrases_mtime = m
        with open(PHRASES_FILE, encoding='utf-8') as f:
            phrases = [line.strip() for line in f if line.strip()]
        return phrases or ['shpateil.fun']
    except OSError as e:
        log.warning('фразы не читаются: %s', e)
        return None


def build_about(idx, total, phrase):
    about = f'{idx + 1}/{total} {phrase} | shpateil.fun'
    return about[:BIO_LIMIT]


async def online_keeper(client):
    # вечный онлайн: дергаем статус каждые 3 мин
    while True:
        try:
            await asyncio.sleep(ONLINE_INTERVAL)
            await asyncio.wait_for(client(UpdateStatusRequest(offline=False)), timeout=REQUEST_TIMEOUT)
            log.info('онлайн подтвержден')
            _touch_health()
        except asyncio.CancelledError:
            break
        except FloodWaitError as e:
            log.warning('онлайн флудвейт %sс', e.seconds)
            await asyncio.sleep(e.seconds + 5)
        except Exception as e:
            log.warning('онлайн ошибка: %s', e)
            await asyncio.sleep(30)


async def run_rotator():
    phrases = load_phrases()
    if not phrases:
        phrases = ['shpateil.fun']
    total = len(phrases)
    log.info('загружено %d фраз', total)

    client = TelegramClient(SESSION, API_ID, API_HASH)
    client.flood_sleep_threshold = 10
    await client.start()
    me = await client.get_me()
    log.info('зашел как %s id=%s', me.username or me.first_name, me.id)

    # стартовый онлайн сразу
    try:
        await asyncio.wait_for(client(UpdateStatusRequest(offline=False)), timeout=REQUEST_TIMEOUT)
        log.info('онлайн включен')
    except Exception as e:
        log.warning('стартовый онлайн не встал: %s', e)

    keeper = asyncio.create_task(online_keeper(client))
    # продолжаем с места рестарта чтоб не крутить первые фразы по кругу
    try:
        idx = int(IDX_FILE.read_text().strip())
    except Exception:
        idx = 0
    if idx < 0 or idx >= total:
        idx = 0
    fails = 0
    def _save_idx():
        try:
            IDX_FILE.write_text(str(idx))
        except Exception:
            pass
    try:
        while True:
            fresh = load_phrases()
            if fresh is not None and fresh != phrases:
                phrases = fresh
                total = len(phrases)
                idx = 0
                fails = 0
                log.info('перечитал %d фраз', total)
            phrase = phrases[idx]
            about = build_about(idx, total, phrase)
            try:
                await asyncio.wait_for(client(UpdateProfileRequest(about=about)), timeout=REQUEST_TIMEOUT)
                log.info('%s [%d/%d]', phrase, idx + 1, total)
                idx = (idx + 1) % total
                _save_idx()
                fails = 0
                _touch_health()
                await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
            except FloodWaitError as e:
                wait = e.seconds + 5
                log.warning('флудвейт %sс, жду %sс', e.seconds, wait)
                # критикал алерт в лс если флуд долгий
                if e.seconds > 300:
                    try:
                        await client.send_message('me', f'ротатор флудвейт {e.seconds}с')
                    except Exception:
                        pass
                await asyncio.sleep(wait)
            except PersistentTimestampOutdatedError:
                await asyncio.sleep(5)
            except asyncio.TimeoutError:
                fails += 1
                log.warning('таймаут (%d/%d)', fails, MAX_FAILS)
                if fails >= MAX_FAILS:
                    log.warning('скип фразы после %d фейлов', fails)
                    idx = (idx + 1) % total
                    fails = 0
                await asyncio.sleep(5)
            except Exception as e:
                msg = str(e).lower()
                if 'disconnect' in msg or 'connected' in msg or 'connection' in msg:
                    log.error('дисконнект: %s', e)
                    raise
                fails += 1
                log.error('ошибка: %s (%d/%d)', e, fails, MAX_FAILS)
                if fails >= MAX_FAILS:
                    log.warning('скип фразы после %d фейлов', fails)
                    idx = (idx + 1) % total
                    fails = 0
                    await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
                else:
                    await asyncio.sleep(10)
    finally:
        keeper.cancel()
        try:
            await keeper
        except asyncio.CancelledError:
            pass


async def main():
    global _crash_count, _last_crash_alert
    delay = 10
    while True:
        try:
            await run_rotator()
            log.warning('выход из цикла, рестарт через 10с')
            await asyncio.sleep(10)
            delay = 10
        except Exception as e:
            _crash_count += 1
            log.error('краш: %s, рестарт через %sс', e, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 120)
            # алерт в лс только если сыпется подряд чтоб не спамить
            if _crash_count >= 3 and time.time() - _last_crash_alert > 3600:
                _last_crash_alert = time.time()
                try:
                    tmp = TelegramClient(SESSION, API_ID, API_HASH)
                    await tmp.start()
                    await tmp.send_message('me', f'ротатор падал {_crash_count} раз, посл: {e}')
                    await tmp.disconnect()
                except Exception:
                    pass


if __name__ == '__main__':
    asyncio.run(main())
