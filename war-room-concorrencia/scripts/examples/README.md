# Fixtures de exemplo (dados 100% simulados)

Servem para testar o pipeline inteiro sem gastar Apify nem depender de contas
conectadas no Windsor.ai. Nenhum número aqui é real.

- `ml-simulado-rodada1.json` / `ml-simulado-rodada2.json` — dois snapshots de Mercado
  Livre no formato interno de `collect_snapshot()`, prontos para `--simulate-ml`. A
  rodada 2 tem, de propósito, um exemplo de cada tipo de mudança que o playbook cobre:
  queda de preço agressiva + novo desconto (Faciderm/Black Skull), novo entrante
  (Faciderm/Growth Supplements), concorrente sumiu (Amaze/Growth Supplements), salto de
  visibilidade (Amaze/Black Skull) e aumento de preço do concorrente (Linha Joie
  Fit/Black Skull).
- `meta-ads-simulado.json` — desempenho de Meta Ads simulado, no formato que
  `own_performance.py` espera (`{"connector": "facebook", "registros": [...]}`), para
  combinar com um export real de Google Ads (via Windsor.ai) num teste de ponta a ponta.

Uso:
```bash
cd ..
python war_room.py --config config.example.json --simulate-ml examples/ml-simulado-rodada1.json \
  --history-dir /tmp/wr-demo --out /tmp/war-room.xlsx --html /tmp/war-room.html
python war_room.py --config config.example.json --simulate-ml examples/ml-simulado-rodada2.json \
  --history-dir /tmp/wr-demo --out /tmp/war-room.xlsx --html /tmp/war-room.html
```
