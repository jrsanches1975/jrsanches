#!/usr/bin/env python3
"""
Gera o PAINEL DE SELEÇÃO DE PRODUTOS — uma tela self-contained (sem backend)
onde você marca quais produtos do catálogo estão sendo acompanhados pela war
room (produtos_monitorados), quais são só candidatos (produtos_candidatos_manual,
ainda em avaliação) e pode adicionar um produto novo ou remover um que não
interessa mais.

Como este projeto não tem servidor (é tudo script + HTML estático), o painel
não escreve direto em config.json. Em vez disso: você mexe nos toggles/campos
na tela e clica em "Exportar config.json atualizado" — isso baixa um
config.json novo (o mesmo de entrada, só com produtos_monitorados/
produtos_candidatos_manual recalculados a partir do que você marcou). Você
salva esse arquivo por cima do seu scripts/config.json e roda o war_room.py
normalmente na próxima rodada.

Uso:
    python gerar_painel_produtos.py --config config.example.json \
        --out ../outputs/painel-produtos.html
"""
import argparse
import json
import os

from _fonts import FONT_ORBITRON_B64, FONT_SHARETECH_B64

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def montar_catalogo(config):
    """Devolve a lista unificada de produtos (monitorados + candidatos) que
    alimenta o painel — cada item carrega monitorando=True/False conforme de
    qual lista do config ele veio."""
    catalogo = []
    for p in config.get("produtos_monitorados", []):
        item = dict(p)
        item["monitorando"] = True
        catalogo.append(item)
    for p in config.get("produtos_candidatos_manual", []):
        item = dict(p)
        item["monitorando"] = False
        catalogo.append(item)
    return catalogo


def render_painel(config, catalogo, meta, path):
    catalogo_json = json.dumps(catalogo, ensure_ascii=False)
    config_json = json.dumps(config, ensure_ascii=False)
    n_monitorados = sum(1 for p in catalogo if p["monitorando"])

    html = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>War Room — {config.get('marca', '')} · Painel de Produtos</title>
<style>
  @font-face {{
    font-family: 'Orbitron'; font-weight: 400 900; font-style: normal; font-display: swap;
    src: url(data:font/woff2;base64,{FONT_ORBITRON_B64}) format('woff2');
  }}
  @font-face {{
    font-family: 'Share Tech Mono'; font-weight: 400; font-style: normal; font-display: swap;
    src: url(data:font/woff2;base64,{FONT_SHARETECH_B64}) format('woff2');
  }}
  :root {{
    --void: #05070a; --panel: #0b121a; --panel-2: #0f1922; --line: rgba(70,255,224,.18);
    --hud: #29ffe0; --hud-soft: rgba(41,255,224,.45); --hud-dim: rgba(41,255,224,.08);
    --text: #d8f7f0; --text-dim: #6f8f97;
    --alta: #ff3b52; --alta-bg: rgba(255,59,82,.1);
    --media: #ffb02e; --media-bg: rgba(255,176,46,.1);
    --baixa: #39ff9d; --baixa-bg: rgba(57,255,157,.08);
    color-scheme: dark;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ background: var(--void); }}
  body {{
    margin: 0; color: var(--text); min-height: 100vh;
    font-family: 'Share Tech Mono', ui-monospace, "Roboto Mono", monospace;
    background-image:
      linear-gradient(var(--hud-dim) 1px, transparent 1px),
      linear-gradient(90deg, var(--hud-dim) 1px, transparent 1px);
    background-size: 36px 36px;
  }}
  h1, h2, .stat-value {{ font-family: 'Orbitron', sans-serif; }}
  header {{
    padding: 22px 32px; border-bottom: 1px solid var(--line);
    background: linear-gradient(180deg, var(--panel), transparent);
    display: flex; flex-wrap: wrap; gap: 16px; align-items: baseline; justify-content: space-between;
  }}
  .eyebrow {{
    display: block; font-size: .72rem; letter-spacing: .16em; text-transform: uppercase;
    color: var(--hud); font-weight: 600; opacity: .9; margin-bottom: 6px;
  }}
  h1 {{
    margin: 0; font-size: clamp(1.5rem, 3.4vw, 2.1rem); font-weight: 800; letter-spacing: .02em;
    text-transform: uppercase; color: var(--hud); text-shadow: 0 0 10px var(--hud-soft);
  }}
  .stats {{ display: flex; gap: 22px; }}
  .stat {{ text-align: right; }}
  .stat-label {{ font-size: .68rem; text-transform: uppercase; letter-spacing: .08em; color: var(--text-dim); }}
  .stat-value {{ font-size: 1.5rem; color: var(--hud); font-variant-numeric: tabular-nums; }}
  main {{ padding: 24px 32px 60px; max-width: 1100px; margin: 0 auto; }}
  .hint {{
    font-size: .82rem; color: var(--text-dim); line-height: 1.6; max-width: 760px; margin: 0 0 22px;
    padding: 12px 16px; border-left: 2px solid var(--hud-soft); background: var(--panel-2); border-radius: 0 4px 4px 0;
  }}
  .toolbar {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 18px; }}
  button {{
    font-family: 'Share Tech Mono', monospace; font-size: .8rem; cursor: pointer;
    background: var(--panel-2); color: var(--text); border: 1px solid var(--line);
    border-radius: 4px; padding: 9px 14px; letter-spacing: .03em;
  }}
  button:hover {{ border-color: var(--hud-soft); color: var(--hud); }}
  button.primary {{ background: var(--hud-dim); border-color: var(--hud); color: var(--hud); font-weight: 700; }}
  button.danger {{ background: transparent; border-color: transparent; color: var(--text-dim); padding: 4px 8px; font-size: .9rem; }}
  button.danger:hover {{ color: var(--alta); }}
  .catalogo {{ display: flex; flex-direction: column; gap: 10px; margin-bottom: 26px; }}
  .item {{
    position: relative; background: var(--panel); border: 1px solid var(--line); border-left: 3px solid var(--line);
    border-radius: 4px; padding: 14px 16px; display: grid; grid-template-columns: auto 1fr auto; gap: 14px; align-items: center;
    transition: border-color .2s ease;
  }}
  .item.on {{ border-left-color: var(--hud); }}
  .item.off {{ border-left-color: var(--text-dim); opacity: .72; }}
  .toggle {{
    position: relative; width: 42px; height: 22px; flex: none; border-radius: 12px; border: 1px solid var(--line);
    background: var(--panel-2); cursor: pointer; appearance: none; -webkit-appearance: none; outline-offset: 3px;
  }}
  .toggle::after {{
    content: ""; position: absolute; top: 2px; left: 2px; width: 16px; height: 16px; border-radius: 50%;
    background: var(--text-dim); transition: transform .18s ease, background .18s ease;
  }}
  .toggle:checked {{ border-color: var(--hud-soft); background: var(--hud-dim); }}
  .toggle:checked::after {{ transform: translateX(20px); background: var(--hud); box-shadow: 0 0 6px var(--hud-soft); }}
  .fields {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px 14px; }}
  .field label {{
    display: block; font-size: .62rem; text-transform: uppercase; letter-spacing: .06em; color: var(--text-dim); margin-bottom: 3px;
  }}
  .field input {{
    width: 100%; font-family: 'Share Tech Mono', monospace; font-size: .82rem; color: var(--text);
    background: var(--panel-2); border: 1px solid var(--line); border-radius: 3px; padding: 6px 8px;
  }}
  .field input:focus {{ outline: none; border-color: var(--hud-soft); }}
  .field.nome input {{ font-weight: 700; }}
  .status-tag {{
    justify-self: end; font-size: .64rem; text-transform: uppercase; letter-spacing: .06em; padding: 3px 8px;
    border-radius: 3px; border: 1px solid var(--line); color: var(--text-dim); white-space: nowrap;
  }}
  .on .status-tag {{ color: var(--hud); border-color: var(--hud-soft); }}
  .row-actions {{ display: flex; flex-direction: column; align-items: center; gap: 4px; }}
  .empty {{ padding: 40px 20px; text-align: center; color: var(--text-dim); border: 1px dashed var(--line); border-radius: 4px; }}
  .add-form {{
    background: var(--panel); border: 1px dashed var(--hud-soft); border-radius: 4px; padding: 16px; margin-bottom: 24px;
  }}
  .add-form h2 {{ margin: 0 0 12px; font-size: .8rem; text-transform: uppercase; letter-spacing: .06em; color: var(--text-dim); font-weight: 400; }}
  .add-form .fields {{ margin-bottom: 12px; }}
  .export-box {{ margin-top: 18px; }}
  textarea#json-preview {{
    width: 100%; height: 220px; font-family: 'Share Tech Mono', monospace; font-size: .74rem; color: var(--text);
    background: var(--panel-2); border: 1px solid var(--line); border-radius: 4px; padding: 12px; resize: vertical; display: none;
  }}
  .toast {{
    position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%) translateY(12px); opacity: 0;
    background: var(--panel-2); border: 1px solid var(--hud-soft); color: var(--hud); padding: 10px 18px;
    border-radius: 4px; font-size: .78rem; transition: opacity .2s ease, transform .2s ease; pointer-events: none;
  }}
  .toast.show {{ opacity: 1; transform: translateX(-50%) translateY(0); }}
  a:focus-visible, button:focus-visible, input:focus-visible {{ outline: 2px solid var(--hud); outline-offset: 2px; }}
</style></head>
<body>
<header>
  <div>
    <span class="eyebrow">◈ sistema de guerra competitiva · configuração</span>
    <h1>Painel de Seleção de Produtos</h1>
  </div>
  <div class="stats">
    <div class="stat"><div class="stat-label">Monitorando</div><div class="stat-value" id="stat-on">{n_monitorados}</div></div>
    <div class="stat"><div class="stat-label">No catálogo</div><div class="stat-value" id="stat-total">{len(catalogo)}</div></div>
  </div>
</header>
<main>
  <p class="hint">
    Marque o interruptor de cada produto para ativar/desativar o acompanhamento
    dele na próxima rodada da war room. Produtos desligados viram
    <code>produtos_candidatos_manual</code> (o motor de descoberta ainda os
    considera, mas o monitor de preço/visibilidade do Mercado Livre não roda
    para eles). Isto não altera nenhum arquivo sozinho — ao terminar, clique em
    <strong>Exportar config.json atualizado</strong> e salve o download por cima
    do seu <code>scripts/config.json</code>.
  </p>
  <div class="toolbar">
    <button class="primary" id="btn-add-toggle">+ Adicionar produto</button>
    <button id="btn-export">⭳ Exportar config.json atualizado</button>
    <button id="btn-copy">⧉ Copiar JSON</button>
  </div>
  <div class="add-form" id="add-form" style="display:none">
    <h2>// novo produto</h2>
    <div class="fields">
      <div class="field nome"><label>Nome</label><input type="text" id="new-nome" placeholder="ex.: Colágeno Joie"></div>
      <div class="field"><label>Termo de busca (Mercado Livre)</label><input type="text" id="new-termo" placeholder="ex.: colágeno hidrolisado"></div>
      <div class="field"><label>Preço próprio (R$)</label><input type="number" step="0.01" id="new-preco" placeholder="opcional"></div>
    </div>
    <button class="primary" id="btn-add-confirm">Adicionar ao catálogo</button>
    <button id="btn-add-cancel">Cancelar</button>
  </div>
  <div class="catalogo" id="catalogo"></div>
  <div class="export-box">
    <textarea id="json-preview" readonly></textarea>
  </div>
</main>
<div class="toast" id="toast"></div>
<script>
let CATALOGO = {catalogo_json};
const CONFIG_ORIGINAL = {config_json};

const catalogoEl = document.getElementById('catalogo');
const statOn = document.getElementById('stat-on');
const statTotal = document.getElementById('stat-total');
const toast = document.getElementById('toast');

function showToast(msg) {{
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 2200);
}}

function atualizarStats() {{
  statOn.textContent = CATALOGO.filter(p => p.monitorando).length;
  statTotal.textContent = CATALOGO.length;
}}

function renderCatalogo() {{
  if (!CATALOGO.length) {{
    catalogoEl.innerHTML = '<div class="empty">Nenhum produto no catálogo ainda — adicione um acima.</div>';
    atualizarStats();
    return;
  }}
  catalogoEl.innerHTML = CATALOGO.map((p, i) => `
    <div class="item ${{p.monitorando ? 'on' : 'off'}}" data-idx="${{i}}">
      <input type="checkbox" class="toggle" ${{p.monitorando ? 'checked' : ''}}
             aria-label="Monitorar ${{p.nome}}" data-idx="${{i}}">
      <div class="fields">
        <div class="field nome"><label>Nome</label><input type="text" value="${{p.nome || ''}}" data-idx="${{i}}" data-campo="nome"></div>
        <div class="field"><label>Termo de busca (ML)</label><input type="text" value="${{p.termo_busca_ml || ''}}" data-idx="${{i}}" data-campo="termo_busca_ml"></div>
        <div class="field"><label>Preço próprio (R$)</label><input type="number" step="0.01" value="${{p.preco_proprio ?? ''}}" data-idx="${{i}}" data-campo="preco_proprio"></div>
      </div>
      <div class="row-actions">
        <span class="status-tag">${{p.monitorando ? 'monitorando' : 'candidato'}}</span>
        <button class="danger" data-remove="${{i}}" aria-label="Remover ${{p.nome}}" title="Remover">✕</button>
      </div>
    </div>`).join('');
  atualizarStats();
}}

catalogoEl.addEventListener('change', (e) => {{
  const idx = e.target.dataset.idx;
  if (idx === undefined) return;
  const p = CATALOGO[idx];
  if (e.target.classList.contains('toggle')) {{
    p.monitorando = e.target.checked;
    renderCatalogo();
    return;
  }}
  const campo = e.target.dataset.campo;
  if (!campo) return;
  if (campo === 'preco_proprio') {{
    p[campo] = e.target.value === '' ? null : parseFloat(e.target.value);
  }} else {{
    p[campo] = e.target.value;
  }}
}});

catalogoEl.addEventListener('click', (e) => {{
  const idx = e.target.dataset.remove;
  if (idx === undefined) return;
  const p = CATALOGO[idx];
  if (confirm(`Remover "${{p.nome}}" do catálogo?`)) {{
    CATALOGO.splice(idx, 1);
    renderCatalogo();
  }}
}});

const addForm = document.getElementById('add-form');
document.getElementById('btn-add-toggle').addEventListener('click', () => {{
  addForm.style.display = addForm.style.display === 'none' ? 'block' : 'none';
}});
document.getElementById('btn-add-cancel').addEventListener('click', () => {{
  addForm.style.display = 'none';
}});
document.getElementById('btn-add-confirm').addEventListener('click', () => {{
  const nome = document.getElementById('new-nome').value.trim();
  const termo = document.getElementById('new-termo').value.trim();
  const precoRaw = document.getElementById('new-preco').value;
  if (!nome || !termo) {{
    showToast('Preencha nome e termo de busca.');
    return;
  }}
  CATALOGO.push({{
    nome, termo_busca_ml: termo,
    preco_proprio: precoRaw === '' ? null : parseFloat(precoRaw),
    ticket_medio: precoRaw === '' ? null : parseFloat(precoRaw),
    monitorando: true,
  }});
  document.getElementById('new-nome').value = '';
  document.getElementById('new-termo').value = '';
  document.getElementById('new-preco').value = '';
  addForm.style.display = 'none';
  renderCatalogo();
  showToast(`"${{nome}}" adicionado — lembre de exportar o config.json.`);
}});

function montarConfigAtualizado() {{
  const limpo = (p) => {{
    const c = {{...p}};
    delete c.monitorando;
    Object.keys(c).forEach((k) => {{ if (c[k] === null || c[k] === '') delete c[k]; }});
    return c;
  }};
  const novoConfig = {{...CONFIG_ORIGINAL}};
  novoConfig.produtos_monitorados = CATALOGO.filter(p => p.monitorando).map(limpo);
  novoConfig.produtos_candidatos_manual = CATALOGO.filter(p => !p.monitorando).map(limpo);
  return novoConfig;
}}

document.getElementById('btn-export').addEventListener('click', () => {{
  const novoConfig = montarConfigAtualizado();
  const texto = JSON.stringify(novoConfig, null, 2);
  const blob = new Blob([texto], {{type: 'application/json'}});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'config.json';
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showToast('config.json baixado — salve por cima do seu scripts/config.json.');
}});

document.getElementById('btn-copy').addEventListener('click', async () => {{
  const novoConfig = montarConfigAtualizado();
  const texto = JSON.stringify(novoConfig, null, 2);
  const preview = document.getElementById('json-preview');
  preview.value = texto;
  preview.style.display = 'block';
  try {{
    await navigator.clipboard.writeText(texto);
    showToast('JSON copiado para a área de transferência.');
  }} catch (err) {{
    preview.select();
    showToast('Não deu para copiar automático — selecione o texto abaixo.');
  }}
}});

renderCatalogo();
</script>
</body></html>"""

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    ap = argparse.ArgumentParser(description="Gera o painel de seleção de produtos monitorados.")
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default="painel-produtos.html")
    args = ap.parse_args()

    with open(args.config, encoding="utf-8") as f:
        config = json.load(f)
    config.setdefault("produtos_monitorados", [])
    config.setdefault("produtos_candidatos_manual", [])

    catalogo = montar_catalogo(config)
    meta = {}
    render_painel(config, catalogo, meta, args.out)
    print(f"OK -> {args.out} ({sum(1 for p in catalogo if p['monitorando'])} monitorados de {len(catalogo)} no catálogo)")


if __name__ == "__main__":
    main()
