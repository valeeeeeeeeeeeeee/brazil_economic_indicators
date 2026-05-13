@echo off
python brazil_economic_indicators.py
git add imagens/indicadores.png
git commit -m "atualiza dashboard"
git push
