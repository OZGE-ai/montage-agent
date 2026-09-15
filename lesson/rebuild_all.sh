#!/bin/zsh
# Полная пересборка: плашки → мастер → композиции → субтитры → финал → вжигание.
# Нужна, когда поменялись вырезки (cuts.csv) или цветокор — они живут в мастере.
# Если менялась только вёрстка, плашки, панели или музыка — хватит
# ./tools/finish.sh: он возьмёт готовый мастер и уложится в полчаса.
set -e
setopt null_glob          # пустая маска не ошибка: без этого `rm work/seg/*.mov`
                          # на пустой папке валил весь скрипт (урок 01, 11.09)
cd "$(dirname "$0")/.."
P=.venv/bin/python
echo "=== плашки"
$P tools/plates.py >/dev/null
$P tools/akimat.py | tail -1
echo "=== мастер"
# старая карта времени осталась бы от прошлой сборки, и всё, что ждёт мастер,
# решило бы, что он уже готов — так 10.09 удалили недописанный файл
rm -f work/timemap.json work/clean.mov work/clean_audio.wav
$P -u tools/build_clean.py 2>&1 | grep -v "^frame=" | tail -2
exec ./tools/finish.sh
