# tg-profile-rotator

меняет био telegram по списку фраз. идёт по кругу, подхватывает изменения файла без перезапуска и ждёт при flood wait.

формат био `1/3 фраза | shpateil.fun`, максимум 70 символов. суффикс меняется в `build_about`.

## запуск

нужны python 3.10+ и свои api id и api hash с https://my.telegram.org

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
chmod 600 .env
cp phrases.example phrases.txt
```

заполни `.env`, затем в bash

```sh
set -a
. ./.env
set +a
.venv/bin/python rotator.py
```

первый запуск запросит вход в telegram и сразу начнёт менять био. сессия останется локально. не запускай две копии с одной сессией.

`MIN_DELAY` и `MAX_DELAY` задают паузу в секундах. исходные значения 3 и 10 сохранены, но telegram может ограничить частоту обновлений. фиксированного безопасного интервала нет.

`phrases.txt` должен существовать до запуска. по одной фразе на строку, пустые строки пропускаются. при пустом файле используется `shpateil.fun`.

## фоновый запуск

пример пользовательского systemd сервиса в `tg-profile-rotator.service.example`. замени пути под своё расположение проекта. сначала авторизуйся вручную. пример сам ничего не включает.

## проверка

```sh
python3 -m unittest discover -s tests -v
```

это офлайн проверки конфигурации и форматирования био, без входа в telegram.

