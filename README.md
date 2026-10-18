# ИТЭФ / М-20, 1966 — шахматная программа снова играет

**ITEP Chess Program (Moscow, 1966) — a working reconstruction.**

*English summary first; полный текст по-русски ниже.*

---

## English summary

In 1966 a group at the Institute of Theoretical and Experimental Physics (ITEP, Moscow) — Georgy Adelson-Velsky, Vladimir Arlazarov, Anatoly Uskov, Alexander Zhivotovsky and chess master Alexander Bitman, in the laboratory of Alexander Kronrod — wrote a chess program for the Soviet M-20 computer (≈20 000 operations per second, 4096 words of 45 bits). In 1966–67 it won the first match between chess programs, 3:1 by telegraph against the Kotok–McCarthy program at Stanford. Its successor became Kaissa, the first world computer chess champion (1974).

The only surviving text of the 1966 program is a 121-page scan of handwritten M-20 coding sheets. This repository makes that text run again:

- the original machine code is executed instruction by instruction on a SIMH-based M-20 emulator ([besm6/m20](https://github.com/besm6/m20), Serge Vakulenko), with the digitization from the same project;
- search, evaluation and move generation are the program's own; the modern code only loads the board, drives the emulator and reads the chosen move;
- a browser interface and a UCI wrapper let you play against it or match it against other engines.

**Verification.** On the 76 positions of the first two match games of 1966–67 the reconstruction chooses the historical move in 55 cases (72%), and in 64 cases (84%) the historical move is one of its two top candidates. Position counters published by the authors in 1970 are reproduced in order of magnitude but not exactly; the surviving sheets appear to be a different revision of the program than the one that played the match (details in `docs/`). Move legality was cross-checked against an independent library (python-chess) over thousands of generated moves.

**Status.** Plays legal chess from any position at search depth 3 (historical default), 4 and 5 half-moves, with the authors' forced-variation extensions. Every reconstructed constant, every emulator patch and every overlay on the digitized listing is documented with its source. Two rules missing from the surviving sheets — the terminal (mate/stalemate) score and a guard in pawn promotion — are restored from the authors' own 1966 report and marked as such.

Run: `./run.sh` (needs Python 3 and a C compiler; python-chess is bundled). Technical documentation in Russian: `docs/TECHNICAL_RU.md`.

---

## Что это

В 1966 году в ИТЭФ, в лаборатории Александра Семёновича Кронрода, была написана первая советская полноценная шахматная программа — для ЭВМ М-20. Её авторы (в порядке, который называет сам В. Л. Арлазаров): Г. М. Адельсон-Вельский, В. Л. Арлазаров, Анатолий Усков, Александр Животовский и мастер Александр Битман; Кронрод — вдохновитель, отказывавшийся от соавторства. В 1966–67 годах программа выиграла по телеграфу первый в истории матч между шахматными программами — у программы Котока–Маккарти из Стэнфорда, 3:1. Из неё выросла «Каисса», первый чемпион мира среди программ (1974).

От программы 1966 года сохранился единственный текст — скан 121 листа рукописных бланков с кодом М-20. Этот репозиторий заставляет его работать:

- машинный код исполняется команда за командой на эмуляторе М-20 (SIMH, модуль Сергея Вакуленко из проекта [besm6/m20](https://github.com/besm6/m20)); оцифровка листинга — оттуда же;
- поиск, оценка и генерация ходов — родные, из листинга; современный код только загружает доску, запускает эмулятор и читает выбранный ход;
- веб-интерфейс для игры и UCI-обёртка для матчей с другими движками.

Первый легальный ход из начальной позиции — **1.Кb1–c3** — программа сделала 1 октября 2026 года, через шестьдесят лет после написания. На него ушло 10 238 727 команд М-20: на настоящей машине — около восьми с половиной минут. Текущая редакция, с исправленными накладками на оцифровку (профиль v11), из той же позиции выбирает **1.e4** (9 682 460 команд, около восьми минут) — оба хода из оценки, дебютной книги в программе нет.

## Запуск

В терминале:

```sh
./run.sh                                   # игра в браузере, профиль v11, глубина 3
./run.sh --pgn examples/itef-game-6.pgn --side black   # продолжить партию из PGN
./run.sh --uci                             # UCI-движок для cutechess и других оболочек
./run.sh --benchmark --workers 1           # замер 20 контрольных позиций
```

Нужны Python 3 и компилятор C (на Mac — Command Line Tools). Первый запуск собирает эмулятор (секунды). Сеть не используется. Подробности, глубины, лимиты команд, варианты форсированной игры, формат PGN с часами М-20 — в `docs/TECHNICAL_RU.md`.

Проверки: `python3 tests/verify.py` (приёмка: генератор, рокировки, превращения, самоигра), `tests/v19_mates.py`, `tests/terminal_cleanup.py`, `tests/terminal_scores.py`, `tests/promotion_regression.py`, `tests/depth_policy_smoke.py`, `tests/v19_uci_smoke.py`, `tests/history_compare.py` (73 исторических решения).

## Что проверено

| Проверка | Результат |
|---|---|
| Легальность ходов: самоигра 131 полуход, 421 позиция, 9322 применения ходов против python-chess | все совпали |
| 76 решений программы в партиях 1–2 матча 1966–67 (глубина 3) | 55 совпали с историей (72,4 %); в 64 случаях (84,2 %) исторический ход — в двух лучших кандидатах |
| 73 ненулевых счётчика позиций из статьи авторов 1970 г. | воспроизводятся по порядку величины, не точно (см. ниже) |
| Правило отбора взятий (6) из отчёта авторов 1966 г. | работает в листинге: 1,79 млн взятий, 34 исключения — все на превращениях |
| Формулы возможностей пешек (16.1–16.3) из того же отчёта | 438 сравнений с растрами листинга, ноль расхождений |
| Маты в один ход (20 позиций, глубины 1–3) | 20/20 после восстановления терминального правила (v18) |

Почему счётчики не совпадают точно: рукопись содержит следы нескольких редакций (две версии блока «Счёт» по одним адресам, коллизия адреса 4231 между двумя процедурами, предел ранга 14 против 16 в статье), а сам Арлазаров в 2024 году вспоминал, что в ИТЭФ писали код для работы с битовыми ячейками, который «покинули место раньше, чем могли использовать». Все описанные авторами варианты форсированной игры и схемы отбора перебраны; ни один не сводит разброс к нулю. Вывод работы: **сохранившаяся редакция верифицирована; матч играла другая редакция, по рукописи не восстановимая.** Полная аргументация — `docs/V17_V18_RESULTS_RU.md`, `docs/V12_PROFILES_RU.md`.

## Что в ней есть и чего нет

Есть: полная ширина на 3 полухода, затем взятия, шахи и ответы на шах до затухания; оценка с материалом, пешками в центре, подвижностью фигур, рокировкой, проходными; родные рокировки и превращения; самостоятельная сдача. Нет: дебютной книги (1.e4 и слон на c4 — из оценки, не из книги), понимания тихих жертв, активности короля в эндшпиле. Тихих ходов за третьим полуходом она не видит — ни жертв, ни матов, ни защит: в `examples/itef-machack.pgn` после 37.Ne2 Rf2+ 38.Kg1 решает тихое 38…e3, и программа этого не считала — это документированное поведение сохранившегося поиска (три полухода полной ширины, затем только взятия и шахи), а не ошибка реконструкции.

Сила по ощущению тренера-кандидата в мастера и по разбору Стокфишем — около 1500–1600; в 1967 году гроссмейстеры оценили программу в третий разряд.

## Эксперименты

- **Телеграфный матч с MacHack VI** (Гринблатт, MIT, 1967; версия OCM на ITS) — протокол в `matches/MACHACK_PROTOCOL_RU.md`, первая партия в `examples/itef-machack.pgn`, переводчик нотаций для ручной передачи ходов — `tools/telegrafist-1967.html` (один файл, работает без сети).
- Партии с людьми — `examples/itef-game-*.pgn`, с часами М-20 на каждый ход программы.

## Что сделано поверх источников

Всё, что отличается от скана и оцифровки, перечислено и обосновано:

- **Эмулятор** (`m20/simh/m20_cpu.c`, diff в `docs/`): обрезка мантиссы при сдвиге; запись порядка в командах сложения порядков; источник порядка в 026/066; ФК (057) и ФА (037) как формирование следующей команды — по «Беседам о программировании» Кронрода; счёт единиц 040 в младшем поле; знак Ω для 053/073; след в РМР после 056/076.
- **Накладки на оцифровку** (адреса 2317, 2133, 3667, 3705, 0704, 7764, 7775; исправление коллизии 4231) — `docs/V11_SEARCH_RU.md`, `docs/RECONSTRUCTION.md`.
- **Восстановленные младшие ячейки** (0077, 0100–0112, стандартные 0121–0137) — `research/`.
- **Терминальное правило** (мат противнику = 2C+1, свой мат = 0, пат = C) по формуле (2′) отчёта авторов — `docs/V18_TERMINAL_RU.md`; **защита при повторном превращении** — `docs/V19_PROMOTION_RU.md`; очистка списка ходов при терминальном возврате (v19.1) — `docs/V19_1_TERMINAL_CLEANUP_RU.md`. Всё это — функциональные восстановления, не найденный машинный текст; отключаются для исследования.

## Источники

- Адельсон-Вельский, Арлазаров, Битман, Животовский, Усков. О программировании игры вычислительной машины в шахматы. *УМН*, 25:2 (1970), 221–260. [mathnet.ru/rm5324](https://www.mathnet.ru/rus/rm5324) — счётчики позиций и партии матча.
- G. M. Adelson-Velskiy, V. L. Arlasarov, A. G. Uskov. *Programme Playing Chess*. Report on the symposium «Theory and Computing Methods in the Upper Mantle Problem» (ITEP, ≈1966). Stanford, Edward A. Feigenbaum papers, SC0340, box 54, folder 3: [purl.stanford.edu/tn736hy2288](https://purl.stanford.edu/tn736hy2288) — описание программы матчевой эпохи, формулы оценки и форсированной игры.
- V. Arlazarov, A. Brudno. *Around Kaissa*. ICGA Journal 46 (2024/25) — две матчевые версии (глубины 3 и 5).
- А. С. Кронрод. *Беседы о программировании* — семантика команд ФК/ФА.
- Скан рукописи: [greko.su/m20-itef.pdf](https://greko.su/m20-itef.pdf). Оцифровка и эмулятор: [besm6/m20](https://github.com/besm6/m20) (Сергей Вакуленко; оцифровку прислал Дмитрий Зарифьян, 2012; сверка с независимой расшифровкой Алексея Мисюрева — rcgoff, 2021). Частичная реконструкция на ассемблере: [rcgoff/itep-chess](https://github.com/rcgoff/itep-chess).
- Интервью В. Л. Арлазарова (Smart Engines, 2024): [habr.com/…/802759](https://habr.com/ru/companies/smartengines/articles/802759/) — состав авторов и история группы. Дополнительно: ролики канала EngineerSpock об истории «Каиссы».

## Авторы реконструкции

**Максим Петров** (Москва) — автор и руководитель проекта: постановка, чтение рукописи, шахматная приёмка, матчи. Работа велась с языковыми моделями как инструментами под его руководством: Claude Opus (стенд v06), Claude «Сказочница» (v07–v08: распаковка, лавина регистрации, патчи эмулятора №7–9; анализ исторической сверки), GPT «Астра» (v09–v19.1: ФК/ФА, первый легальный ход, интерфейс, UCI, глубины, терминальное правило, превращение), Gemini (расшифровки). Приёмка всех результатов — по артефактам и числам.

Все ошибки реконструкции — наши; все заслуги программы — её авторов.

## Лицензии

Код этой реконструкции (`engine/`, `play.py`, `uci.py`, `ui.html`, `tools/`, `tests/`, `benchmarks/`) — GPL-3.0-or-later (`LICENSE`). Эмулятор — SIMH (лицензия MIT, Robert M. Supnik) и модуль М-20 Сергея Вакуленко из besm6/m20. python-chess — GPL-3.0+ (`vendor/LICENSE-chess.txt`). Текст программы ИТЭФ 1966 года (`m20/kaissa/kaissa.m20`, стандартные ячейки) воспроизводится из оцифровки besm6/m20 в целях сохранения и исследования; права на него принадлежат его авторам.
