#!/bin/zsh
# Досборка от готового мастера: композиции → финал → субтитры → вжигание.
# Мастер work/clean.mov НЕ удаляется — он нужен, чтобы правки вёрстки,
# плашек и панелей считались 30 минут, а не два часа. Пересчитывать его
# заново приходится, только когда меняются вырезки (cuts.csv) или цветокор.
set -e
setopt null_glob
cd "$(dirname "$0")/.."
P=.venv/bin/python
ffprobe -v error -show_entries format=duration -of csv=p=0 work/clean.mov >/dev/null 2>&1 \
  || { echo "нет мастера work/clean.mov — сначала tools/build_clean.py"; exit 1; }
NB=$(ffprobe -v error -select_streams v:0 -show_entries stream=nb_frames -of csv=p=0 work/clean.mov)
DU=$(ffprobe -v error -show_entries format=duration -of csv=p=0 work/clean.mov)
python3 -c "import sys;sys.exit(0 if abs(int('$NB')-float('$DU')*25)<3 else 1)" \
  || { echo "мастер битый: $NB кадров при $DU с"; exit 1; }
echo "=== мастер: $NB кадров, $DU с"
[ -f work/clean_audio.wav ] || ffmpeg -nostdin -v error -y -i work/clean.mov -vn \
  -c:a pcm_s16le -ar 48000 work/clean_audio.wav
echo "=== композиции"
mkdir -p work/seg; rm -f work/seg/*.mov 2>/dev/null || true
$P -u tools/compose.py > work/compose.log 2>&1
N=$(ls work/seg/*.mov | wc -l | tr -d ' ')
# сколько кусков ждём — по строкам листа с таймкодами (без заставки и плашки);
# в уроке 02 здесь было зашито 24, и на уроке 03 сборка встала бы на ровном месте
NR=$(python3 -c "import csv;print(sum(1 for r in csv.DictReader(open('montage.csv',encoding='utf-8')) if r['начало']!='—'))")
echo "кусков: $N из $NR"
[ "$N" -eq "$NR" ] || { tail -6 work/compose.log; exit 1; }
echo "=== финал"
$P -u tools/assemble.py 2>&1 | grep -viE "^frame=|^\[in#|Guessed|infe" | tail -2
# субтитры считаются ПОСЛЕ сборки: только у готового ролика известна реальная
# длительность тела, а по ней subs.py обрезает хвост, чтобы последняя реплика
# не заехала на плашку акимата (урок 05)
echo "=== субтитры"
$P tools/subs.py kk 2>&1 | tail -2
$P tools/subs.py ru 2>&1 | tail -2
echo "=== вжигание"
$P -u tools/burn_subs.py 2>&1 | grep -viE "^frame=|^\[in#|Guessed|infe" | tail -1
SLUG=$(python3 -c "import json;print(json.load(open('lesson.json'))['slug'])")
NF=$(ffprobe -v error -select_streams v:0 -show_entries stream=nb_frames -of csv=p=0 final/$SLUG.mp4)
DF=$(ffprobe -v error -show_entries format=duration -of csv=p=0 final/$SLUG.mp4)
echo "финал: $NF кадров, $DF с"
python3 -c "import sys;sys.exit(0 if abs(int('$NF')-float('$DF')*25)<3 else 1)" \
  || { echo "ФИНАЛ БИТЫЙ: кадры не сходятся с длительностью"; exit 1; }
ls -lh final/
