# ВАЖНО ДЛЯ СЛЕДУЮЩЕГО АГЕНТА

Вся работа происходит в WSL: `/home/exerczz1/ios-agate`.
После каждого изменения обновляй .md файлы (`NOTES.md`, `AGENT-READ-IT.md`) в WSL.

## Текущий статус проекта (2026-10-21, поздний вечер)
1. **Milestone 1 — Framebuffer Format & Early Console Synchronization (24-bit RGB888, Stride 3240) ЗАВЕРШЕН:**
   - `tools/mkadt.py`: установлены `FB_STRIDE = 1080 * 3` (3240), `sweet-fbcon` обновлен с `row-bytes = 3240` и `depth = 24`, в `/chosen/memory-map` добавлен узел `Framebuffer`.
   - `shim/console.h` & `shim/console.c`: `FB_STRIDE = (FB_W * 3)` и дефолтный `con_bpp = 3`.
   - `shim/host_test.c`: адаптирован под 24-bit RGB888 буфер.
   - `xnu/patches/0003-sweet-framebuffer-serial-console.patch`: `fbcon` переведен на `volatile uint8_t*`, очистка строк по 3240 байт, отрисовка глифов по 3 байта на пиксель.
   - `xnu/patches/0010-sweet-early-framebuffer-debug.patch`: маркер Stage 0 в `start.s` обновлен на базу `0x7E020000 + 2368 * 3240`, шаг строки 3240, 24 quadword stores (192 байта/строка); `sweet_early.c` переведен на `volatile uint8_t*`, stride 3240, 3 Bpp, побайтовая математика и отрисовка RGB.
   - `xnu/patches/0012-sweet-keep-debug-console-after-ttbr0.patch`: `sweet_early.c` и `pe_serial.c` синхронизированы с 24-bit RGB888 и `volatile uint8_t*` relocation.
2. **Milestone 2 — Command Mode AMOLED Background Flusher Stabilization & Race-Free Handoff ЗАВЕРШЕН:**
   - `shim/loader.c`: устранен race condition одновременной записи в регистры DSI между CPU 0 и CPU 1. Вызов `smc(PSCI_CPU_ON, 0x100, (uintptr_t)dsi_flush_loop, 0)` перенесен непосредственно перед прыжком в XNU (после всех `con_hex` и `con_str`). CPU 0 больше не вызывает `con_flush()`.
   - `shim/start.S`: проверен и подтвержден пейсинг `dsi_flush_loop` по `cntpct_el0` с шагом `0x100000` тиков на 13 МГц (~80.66 мс / ~12.4 Гц) для предотвращения коллизий с DSC-декомпрессором AMOLED.
   - `tools/mkadt.py`: проверено и подтверждено ограничение `MEM_SIZE = 0x3e000000`, исключающее фреймбуфер `0x7E020000` из пула памяти XNU.
3. **Готовые бинарники собраны и подписаны:**
   - Образ для прошивки: `shim/out/shim-boot.img` (также скопирован в `c:\Users\exerczz1\Documents\ios-agate\shim\out\shim-boot.img`).
   - Команда прошивки: `fastboot flash boot shim/out/shim-boot.img`.
4. **Правила разработки пользователя:**
   - Не оставлять комментарии в коде (`//`, `/* */`, `#`).
   - Делать все просто, не усложнять код/решения.
   - Всегда коммитить с флагами `-s -S`.
   - Проверять работу перед ответом.
