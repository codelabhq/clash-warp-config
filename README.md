# clash-warp-config

Готовые конфигурации Clash / Mihomo (Clash Meta) с Cloudflare WARP через WireGuard и обфускацией AmneziaWG. Конфиги собраны под разные типы устройств, содержат набор WARP-эндпоинтов и правила маршрутизации по сервисам (Telegram, Discord, YouTube, Netflix, AI, WhatsApp, Twitch, игры, обход блокировок).

Цель проекта — не настраивать конфиг с нуля, а открыть готовый файл под своё устройство и скачать его в одно нажатие.

## Готовые конфиги

| Устройство | Что внутри | Просмотр и скачивание |
|------------|------------|-----------------------|
| Компьютер | гео + origin + default эндпоинты | [Computer.yaml](https://github.com/codelabhq/clash-warp-config/blob/main/config/Computer.yaml) |
| Телефон | гео + origin эндпоинты | [Mobile.yaml](https://github.com/codelabhq/clash-warp-config/blob/main/config/Mobile.yaml) |
| Роутер | гео + origin эндпоинты | [Router.yaml](https://github.com/codelabhq/clash-warp-config/blob/main/config/Router.yaml) |

## Типы WARP-эндпоинтов

- Гео — серверы по странам: Нидерланды, Польша, Россия, Финляндия, Германия, Латвия, LTE-узлы.
- Origin — оригинальные эндпоинты Cloudflare WARP (`engage.cloudflareclient.com` и IP).
- Default — диапазоны IP Cloudflare.

## Перед использованием

В конфигах поле `private-key` пустое (`# вставьте ваш ключ`) — подставьте свой приватный ключ WARP, иначе подключение не заработает.

## Структура репозитория

```
config/      готовые конфиги под устройства (Computer, Mobile, Router)
proxies/     списки WARP-эндпоинтов по типам (geo, origin, default)
settings/    редактируемые источники: amnezia.yaml, rule-providers.json, proxy-groups.json, rules.json
scripts/     build_config.py — сборка источников в конфиги
.github/     workflow для автоматической пересборки
```

## Сборка

Эндпоинты хранятся отдельно в `proxies/*.yaml` и вставляются в `config/*.yaml` между маркерами `BEGIN WARP PROXIES` / `END WARP PROXIES`. Какие типы попадут в конкретный конфиг, задаёт директива `# warp-types:` в его заголовке.

Параметры обфускации AmneziaWG (base + `i1` для `default`/`alt1`/`alt2`/`alt3` и `i2` для `alt3`) лежат в `settings/amnezia.yaml`. Сборка объявляет их якорями в блоке `BEGIN AMNEZIA ANCHORS` / `END AMNEZIA ANCHORS` вверху каждого конфига (`&amnezia-common`, `&i1-default`, `&i1-alt1` …). `warp-common` ссылается на них через `&amnezia-base` (`<<: *amnezia-common` + `i1: *i1-default`); ноды без переопределения наследуют его через `<<: *warp-common`. Первые три origin-эндпоинта с `:4500` в имени дублируются записями `(Alt N)`, где `amnezia-wg-option` — это `<<: *amnezia-base` с переопределением `i1`/`i2` через алиасы.

### Правила, провайдеры и группы прокси

`rule-providers`, `proxy-groups` и `rules` редактируются в `settings/*.json` и вставляются в каждый конфиг между маркерами `BEGIN/END RULE-PROVIDERS`, `BEGIN/END PROXY-GROUPS`, `BEGIN/END RULES`. Порядок записей в `rules.json` сохраняется как есть.

В какой конфиг попадёт запись, задаёт директива `# device:` в заголовке конфига (`pc`, `mobile`, `router`) и необязательное поле `"devices"` у записи:

```json
{ "rule": "RULE-SET,ru-apps,DIRECT", "devices": ["mobile"] }
```

Без поля `"devices"` запись попадает во все три конфига; со списком — только в указанные устройства. Это работает одинаково для `rule-providers.json`, `proxy-groups.json` и `rules.json`.

Детали формата `settings/*.json`:

- `rule-providers.json` — список провайдеров; `interval` можно опустить (тогда используется якорь `*default-interval`).
- `proxy-groups.json` — список групп; ключи записи выводятся как есть, `*health-url` / `*check-interval` ссылаются на якоря из заголовка. Поле `"overrides"` задаёт значения ключей для отдельных устройств — например, маркер `☁️` (default-эндпоинты) в фильтре только на `pc`:

  ```json
  { "name": "YouTube", "filter": "⭐", "overrides": { "pc": { "filter": "⭐|☁️" } } }
  ```
- `rules.json` — упорядоченный список; `{ "comment": "..." }` рендерится комментарием-разделителем, `{ "rule": "..." }` — правилом.

```
pip install pyyaml
python scripts/build_config.py
```

При изменении файлов в `proxies/`, `settings/` или скрипта сборки GitHub Actions пересобирает конфиги и коммитит результат автоматически.

## Лицензия

См. [LICENSE](LICENSE).
