#!/usr/bin/env bash
# Весь конвейер «интервью» одной командой.
#   ./run_interview.sh ~/Projects/my-interview analyze   # шаги 1–5: синхронизация, расшифровка, голоса, взгляд, запинки
#   ./run_interview.sh ~/Projects/my-interview build     # шаги 6–9: вырезки, камеры, графика, сборка (после того как агент заполнил project.json)
set -euo pipefail
export MONTAGE_PROJECT="$(cd "${1:?укажите папку проекта}" && pwd)"
STAGE="${2:-analyze}"
PY="${PYTHON:-$(dirname "$0")/.venv/bin/python}"
cd "$(dirname "$0")/interview"

step() { echo; echo "── $1"; shift; "$PY" "$@"; }

if [[ "$STAGE" == "analyze" ]]; then
  step "1. Синхронизация камер"        sync.py
  step "2a. Расшифровка"                transcribe.py
  step "2b. Дословная расшифровка"      transcribe.py verbatim
  step "3. Кто говорит"                 speakers_f0.py
  step "4a. Взгляд на крупных"          gaze.py close
  step "4b. Взгляд на общем"            gaze.py wide
  step "4c. Чтение с листа"             gaze.py eyes
  step "5. Запинки «э-э»"               hesitations.py
  echo
  echo "Дальше агент читает work/words_verbatim.json и заполняет в project.json: host_segments, edits, triggers."
  echo "После утверждения монтажного листа: ./run_interview.sh \"$MONTAGE_PROJECT\" build"
elif [[ "$STAGE" == "build" ]]; then
  step "6. Вырезки"                     edit.py
  step "7. Выбор камер"                 shots.py
  step "8a. Плашки ФИО"                 lower_thirds.py
  step "8b. Перебивка, заставка, финал" graphics.py
  [[ -f "$MONTAGE_PROJECT/assets/sfx/chuh.wav" ]] || step "8c. Звук перехода" sfx.py
  step "9. Сборка"                      render.py
else
  echo "этап: analyze или build"; exit 1
fi
