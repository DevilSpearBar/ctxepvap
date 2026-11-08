# Невеста — 10-секундный мульт в стиле «Трупа невесты»

Сцена нарисована в SVG и анимируется функцией `renderFrame(t)` (`scene.html` + `*.js`).
`render.mjs` снимает кадры через headless Chrome и собирает mp4 в ffmpeg, `audio.mjs` синтезирует музыку.

    node audio.mjs                    # out/music.wav
    node render.mjs                   # out/corpse-bride.mp4 (1280×720, 24 fps, 10 с, со звуком)
    node render.mjs --still 2.5 6 9   # PNG-кадры для проверки в out/stills/
    node render.mjs --sheet           # контактный лист готового ролика в out/sheet.png

Нужны Node 22+, ffmpeg и google-chrome.
