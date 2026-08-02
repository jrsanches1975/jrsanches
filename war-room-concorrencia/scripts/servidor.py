#!/usr/bin/env python3
"""
Backend local do war room. É o que faz o botão "Salvar e rodar agora" funcionar:
sem servidor, o HTML é um arquivo estático e não tem como executar nada nem
gravar o `config.json`.

O que ele faz:
  1. serve o `war-room.html` gerado (para o navegador falar com a mesma origem);
  2. grava a seleção manual de produtos/concorrentes no `config.json`;
  3. dispara uma rodada na hora, sem esperar a janela de cadência;
  4. transmite o log da rodada em andamento, linha por linha.

Rodar:
    cd scripts
    python servidor.py --config config.json

    # abra http://127.0.0.1:8787 no navegador

DECISÕES DE SEGURANÇA (um endpoint que executa comando merece explicação):

- **Escuta em 127.0.0.1** por padrão. Só a sua máquina alcança. Para expor na
  rede (`--host 0.0.0.0`) o script EXIGE `--token`, porque aí qualquer um no
  mesmo Wi-Fi poderia disparar rodadas e queimar seu saldo de API.
- **O comando da rodada nunca vem do navegador.** Ele é montado aqui, a partir
  dos argumentos de linha de comando. Se o `POST` pudesse escolher o comando (ou
  gravar um campo de config que virasse comando), uma aba maliciosa aberta ao
  lado teria execução remota na sua máquina. Por isso `POST /api/selecao` aceita
  **só quatro chaves** e valida campo por campo — o resto do `config.json` fica
  intocado.
- **Nunca `shell=True`.** O subprocesso recebe lista de argumentos.
- **Só aceita `Content-Type: application/json`** nos POSTs e não emite cabeçalho
  CORS. Isso obriga o navegador a fazer preflight num pedido de outra origem, que
  falha — é o que impede uma página aleatória de postar aqui.
- **Backup antes de sobrescrever** o `config.json` (`config.json.bak-<hora>`).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RAIZ = os.path.dirname(os.path.abspath(__file__))

# campos aceitos por tipo de item. Qualquer chave fora desta lista é DESCARTADA
# na gravação — é o que impede o navegador de injetar configuração que o servidor
# leia depois (ex.: um campo que virasse comando de subprocesso).
CAMPOS_PRODUTO = {
    "nome": str, "termo_busca_ml": str, "preco_proprio": float, "ticket_medio": float,
    "campanhas_google_ads": list, "campanhas_meta_ads": list, "atributos": dict,
    "sku": str, "url_propria": str,
}
CAMPOS_CONCORRENTE = {
    "nome": str, "dominio_site": str, "sellers_ml": list,
    "meta_page": str, "google_advertiser": str,
}
LISTAS = {
    "produtos_monitorados": CAMPOS_PRODUTO,
    "produtos_candidatos_manual": CAMPOS_PRODUTO,
    "concorrentes": CAMPOS_CONCORRENTE,
    "candidatos_concorrentes_manual": CAMPOS_CONCORRENTE,
}

LIMITE_CORPO = 512 * 1024      # 512 KB é folgado para catálogo; acima disso é abuso
LIMITE_ITENS = 500
LIMITE_TEXTO = 300
MAX_LINHAS_LOG = 4000


def agora_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


# ------------------------------------------------------------------- validação
class Invalido(Exception):
    pass


def _texto(v, campo):
    if not isinstance(v, str):
        raise Invalido(f"{campo}: esperava texto")
    v = v.strip()
    if len(v) > LIMITE_TEXTO:
        raise Invalido(f"{campo}: texto acima de {LIMITE_TEXTO} caracteres")
    # controle/nulo não tem por que existir em nome de produto e quebra arquivo
    if any(ord(c) < 32 for c in v):
        raise Invalido(f"{campo}: caractere de controle não permitido")
    return v


def _numero(v, campo):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise Invalido(f"{campo}: esperava número")
    if v != v or v in (float("inf"), float("-inf")):
        raise Invalido(f"{campo}: número inválido")
    return float(v)


def validar_item(item, campos, onde):
    """Devolve o item limpo: só chaves conhecidas, tipos conferidos, nome exigido."""
    if not isinstance(item, dict):
        raise Invalido(f"{onde}: esperava objeto")
    limpo = {}
    for chave, valor in item.items():
        if chave not in campos:
            continue          # descarta em silêncio: é a barreira contra injeção
        if valor is None or valor == "" or valor == [] or valor == {}:
            continue
        tipo = campos[chave]
        if tipo is str:
            limpo[chave] = _texto(valor, f"{onde}.{chave}")
        elif tipo is float:
            limpo[chave] = _numero(valor, f"{onde}.{chave}")
        elif tipo is list:
            if not isinstance(valor, list):
                raise Invalido(f"{onde}.{chave}: esperava lista")
            limpo[chave] = [_texto(x, f"{onde}.{chave}[]") for x in valor[:LIMITE_ITENS]]
        elif tipo is dict:
            if not isinstance(valor, dict):
                raise Invalido(f"{onde}.{chave}: esperava objeto")
            limpo[chave] = {_texto(k, f"{onde}.{chave} (chave)"): _texto(str(x), f"{onde}.{chave}.{k}")
                            for k, x in list(valor.items())[:50]}
    if not limpo.get("nome"):
        raise Invalido(f"{onde}: 'nome' é obrigatório")
    return limpo


def validar_selecao(corpo):
    if not isinstance(corpo, dict):
        raise Invalido("corpo: esperava objeto JSON")
    faltando = [k for k in LISTAS if k not in corpo]
    if faltando:
        raise Invalido("corpo: faltam as listas " + ", ".join(faltando))
    saida = {}
    for chave, campos in LISTAS.items():
        bruto = corpo[chave]
        if not isinstance(bruto, list):
            raise Invalido(f"{chave}: esperava lista")
        if len(bruto) > LIMITE_ITENS:
            raise Invalido(f"{chave}: acima de {LIMITE_ITENS} itens")
        saida[chave] = [validar_item(it, campos, f"{chave}[{i}]") for i, it in enumerate(bruto)]
    # nome repetido dentro da MESMA lista quebra o diff (a chave do snapshot é o
    # nome); entre listas não repete porque monitorado e candidato são exclusivos
    for chave, itens in saida.items():
        nomes = [i["nome"].lower() for i in itens]
        dup = {n for n in nomes if nomes.count(n) > 1}
        if dup:
            raise Invalido(f"{chave}: nome repetido — {', '.join(sorted(dup))}")
    for a, b in (("produtos_monitorados", "produtos_candidatos_manual"),
                 ("concorrentes", "candidatos_concorrentes_manual")):
        cruzado = ({i["nome"].lower() for i in saida[a]} & {i["nome"].lower() for i in saida[b]})
        if cruzado:
            raise Invalido(f"'{', '.join(sorted(cruzado))}' está em {a} e em {b} ao mesmo tempo")
    return saida


# ---------------------------------------------------------------------- estado
class Rodada:
    """Estado da rodada corrente/última. Um objeto, um lock: o servidor é
    multi-thread e o log é lido por polling enquanto está sendo escrito."""

    def __init__(self):
        self.lock = threading.Lock()
        self.id = 0
        self.estado = "nunca"        # nunca | rodando | ok | erro
        self.linhas = []
        self.inicio = None
        self.fim = None
        self.fim_epoch = None
        self.codigo = None
        self.motivo = None
        self.disparo = None          # "botao" | "cadencia"

    def instantaneo(self, desde=0):
        with self.lock:
            return {
                "id": self.id, "estado": self.estado, "inicio": self.inicio,
                "fim": self.fim, "codigo": self.codigo, "motivo": self.motivo,
                "disparo": self.disparo, "total_linhas": len(self.linhas),
                "linhas": self.linhas[desde:desde + 400],
            }

    def registrar(self, texto):
        with self.lock:
            self.linhas.append(texto)
            if len(self.linhas) > MAX_LINHAS_LOG:
                # corta o meio, preserva começo e fim: o começo tem o comando e o
                # fim tem o erro, que é o que interessa
                self.linhas = (self.linhas[:200]
                               + [f"… [{len(self.linhas) - 1200} linhas omitidas] …"]
                               + self.linhas[-1000:])


class Servico:
    def __init__(self, args):
        self.args = args
        self.config_path = os.path.abspath(args.config)
        self.html_path = os.path.abspath(args.html)
        self.rodada = Rodada()
        self.lock_disparo = threading.Lock()

    # ---------------------------------------------------------------- config
    def ler_config(self):
        with open(self.config_path, encoding="utf-8") as f:
            return json.load(f)

    def gravar_selecao(self, selecao):
        """Mescla as quatro listas no config existente, preservando todo o resto
        (comentários `_comentario_*`, limiares, metas, actors...) e a ORDEM das
        chaves — o arquivo continua legível para quem edita à mão."""
        config = self.ler_config()
        carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = f"{self.config_path}.bak-{carimbo}"
        shutil.copy2(self.config_path, backup)
        for chave, valor in selecao.items():
            config[chave] = valor
        tmp = self.config_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, self.config_path)   # troca atômica: nunca deixa meio arquivo
        return {"backup": os.path.basename(backup),
                "contagem": {k: len(v) for k, v in selecao.items()}}

    # ---------------------------------------------------------------- rodada
    def comando(self):
        """Montado AQUI, a partir da linha de comando — nunca do corpo do POST."""
        cmd = [sys.executable, os.path.join(RAIZ, "war_room.py"),
               "--config", self.config_path,
               "--out", os.path.abspath(self.args.out),
               "--html", self.html_path]
        cmd += self.args.extra
        return cmd

    def pode_rodar(self, forcar):
        r = self.rodada
        with r.lock:
            if r.estado == "rodando":
                return False, f"rodada #{r.id} ainda está em andamento"
            if not forcar and r.fim and self.args.intervalo_minimo_minutos > 0:
                passou = time.time() - r.fim_epoch
                falta = self.args.intervalo_minimo_minutos * 60 - passou
                if falta > 0:
                    return False, (f"última rodada terminou há {int(passou // 60)}min; "
                                   f"espere {int(falta // 60) + 1}min ou confirme o disparo forçado")
        return True, None

    def disparar(self, disparo="botao", forcar=False):
        # o lock impede que dois cliques simultâneos passem os dois pelo teste
        with self.lock_disparo:
            ok, motivo = self.pode_rodar(forcar)
            if not ok:
                return False, motivo
            r = self.rodada
            with r.lock:
                r.id += 1
                r.estado = "rodando"
                r.linhas = []
                r.inicio = agora_iso()
                r.fim = None
                r.fim_epoch = None
                r.codigo = None
                r.motivo = None
                r.disparo = disparo
            threading.Thread(target=self._executar, daemon=True).start()
            return True, None

    def _executar(self):
        r = self.rodada
        cmd = self.comando()
        r.registrar("$ " + " ".join(cmd))
        try:
            proc = subprocess.Popen(
                cmd, cwd=RAIZ, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, encoding="utf-8", errors="replace",
            )
        except OSError as e:
            with r.lock:
                r.estado, r.codigo, r.motivo = "erro", None, f"não consegui iniciar: {e}"
                r.fim, r.fim_epoch = agora_iso(), time.time()
            return
        try:
            for linha in proc.stdout:
                r.registrar(linha.rstrip("\n"))
            codigo = proc.wait(timeout=self.args.timeout_minutos * 60)
        except subprocess.TimeoutExpired:
            proc.kill()
            codigo = -1
            r.registrar(f"[servidor] rodada abortada: passou de {self.args.timeout_minutos}min")
        with r.lock:
            r.codigo = codigo
            r.estado = "ok" if codigo == 0 else "erro"
            # sem inventar sucesso: se o war_room.py saiu != 0, a rodada FALHOU,
            # mesmo que tenha impresso coisas úteis antes
            r.motivo = None if codigo == 0 else f"war_room.py saiu com código {codigo}"
            r.fim, r.fim_epoch = agora_iso(), time.time()

    # ---------------------------------------------------------------- estado
    def estado(self):
        try:
            config = self.ler_config()
        except (OSError, ValueError) as e:
            return {"ok": False, "erro": f"config ilegível: {e}"}
        html_mtime = (datetime.fromtimestamp(os.path.getmtime(self.html_path)).isoformat(timespec="seconds")
                      if os.path.exists(self.html_path) else None)
        return {
            "ok": True,
            "marca": config.get("marca"),
            "cadencia_horas": config.get("cadencia_sugerida_horas"),
            "intervalo_minimo_minutos": self.args.intervalo_minimo_minutos,
            "config": os.path.basename(self.config_path),
            "html_atualizado_em": html_mtime,
            "contagem": {k: len(config.get(k) or []) for k in LISTAS},
            "rodada": self.rodada.instantaneo(desde=10 ** 9),   # só o cabeçalho
        }


# --------------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    servico = None
    server_version = "WarRoom/1.0"

    def log_message(self, fmt, *a):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % a))

    # ------------------------------------------------------------ utilidades
    def _json(self, codigo, corpo):
        dados = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(dados)

    def _autorizado(self):
        token = self.servico.args.token
        if not token:
            return True
        return self.headers.get("X-War-Room-Token") == token

    def _origem_ok(self):
        """Recusa POST vindo de outra origem. Junto com a exigência de
        Content-Type: application/json (que força preflight), é o que impede uma
        página aberta noutra aba de disparar rodadas na sua máquina."""
        origem = self.headers.get("Origin")
        if not origem:
            return True          # curl/script local não manda Origin
        try:
            host = urllib.parse.urlparse(origem).netloc
        except ValueError:
            return False
        return host == self.headers.get("Host")

    def _corpo_json(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise Invalido("Content-Length inválido")
        if n <= 0:
            raise Invalido("corpo vazio")
        if n > LIMITE_CORPO:
            raise Invalido(f"corpo acima de {LIMITE_CORPO // 1024} KB")
        tipo = (self.headers.get("Content-Type") or "").split(";")[0].strip()
        if tipo != "application/json":
            raise Invalido("Content-Type precisa ser application/json")
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            raise Invalido(f"JSON inválido: {e}")

    # -------------------------------------------------------------------- GET
    def do_GET(self):
        rota = urllib.parse.urlparse(self.path)
        caminho = rota.path
        if caminho in ("/", "/index.html", "/war-room.html"):
            return self._servir_html()
        if caminho == "/favicon.ico":
            # o navegador pede sozinho; 204 evita 404 no log a cada carregamento
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if caminho == "/api/estado":
            if not self._autorizado():
                return self._json(401, {"erro": "token ausente ou incorreto"})
            return self._json(200, self.servico.estado())
        if caminho == "/api/rodada":
            if not self._autorizado():
                return self._json(401, {"erro": "token ausente ou incorreto"})
            q = urllib.parse.parse_qs(rota.query)
            try:
                desde = max(0, int((q.get("desde") or ["0"])[0]))
            except ValueError:
                desde = 0
            return self._json(200, self.servico.rodada.instantaneo(desde))
        return self._json(404, {"erro": "rota inexistente"})

    def _servir_html(self):
        caminho = self.servico.html_path
        if not os.path.exists(caminho):
            return self._json(404, {"erro": f"{os.path.basename(caminho)} ainda não foi gerado — "
                                             "rode o war_room.py uma vez, ou use o botão de rodar agora"})
        with open(caminho, "rb") as f:
            dados = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(dados)

    # ------------------------------------------------------------------- POST
    def do_POST(self):
        caminho = urllib.parse.urlparse(self.path).path
        if not self._autorizado():
            return self._json(401, {"erro": "token ausente ou incorreto"})
        if not self._origem_ok():
            return self._json(403, {"erro": "origem não permitida"})
        try:
            corpo = self._corpo_json()
        except Invalido as e:
            return self._json(400, {"erro": str(e)})

        if caminho == "/api/selecao":
            return self._post_selecao(corpo)
        if caminho == "/api/rodar":
            return self._post_rodar(corpo)
        return self._json(404, {"erro": "rota inexistente"})

    def _post_selecao(self, corpo):
        try:
            selecao = validar_selecao(corpo)
        except Invalido as e:
            return self._json(400, {"erro": str(e)})
        try:
            info = self.servico.gravar_selecao(selecao)
        except (OSError, ValueError) as e:
            return self._json(500, {"erro": f"não consegui gravar o config: {e}"})
        return self._json(200, {"ok": True, **info})

    def _post_rodar(self, corpo):
        salvo = None
        if corpo.get("selecao") is not None:
            try:
                selecao = validar_selecao(corpo["selecao"])
                salvo = self.servico.gravar_selecao(selecao)
            except Invalido as e:
                return self._json(400, {"erro": str(e)})
            except (OSError, ValueError) as e:
                return self._json(500, {"erro": f"não consegui gravar o config: {e}"})
        ok, motivo = self.servico.disparar(forcar=bool(corpo.get("forcar")))
        if not ok:
            # 409: o pedido é válido, o estado é que não permite agora
            return self._json(409, {"erro": motivo, "salvo": salvo})
        return self._json(202, {"ok": True, "salvo": salvo,
                                 "rodada": self.servico.rodada.instantaneo(desde=10 ** 9)})


def main():
    ap = argparse.ArgumentParser(description="Backend local do war room (salvar seleção + rodar na hora).")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--out", default=os.path.join(RAIZ, "..", "outputs", "war-room.xlsx"))
    ap.add_argument("--html", default=os.path.join(RAIZ, "..", "outputs", "war-room.html"))
    ap.add_argument("--host", default="127.0.0.1",
                     help="padrão 127.0.0.1 (só esta máquina). Expor na rede exige --token.")
    ap.add_argument("--porta", type=int, default=8787)
    ap.add_argument("--token", default=os.environ.get("WAR_ROOM_TOKEN"),
                     help="se definido, todo pedido precisa do cabeçalho X-War-Room-Token. "
                          "Também pode vir da variável de ambiente WAR_ROOM_TOKEN.")
    ap.add_argument("--intervalo-minimo-minutos", type=int, default=5,
                     help="trava anti-clique-duplo entre rodadas (0 desliga). O botão pode forçar.")
    ap.add_argument("--timeout-minutos", type=int, default=30,
                     help="mata a rodada se passar disso")
    ap.add_argument("--extra", nargs=argparse.REMAINDER, default=[],
                     help="tudo depois de --extra vai direto para o war_room.py "
                          "(ex.: --extra --ga4-json ../outputs/ga4-jornada.json)")
    ap.add_argument("--sem-navegador", action="store_true",
                     help="não abre o navegador sozinho ao subir (útil rodando como serviço/tarefa "
                          "agendada, onde não tem sessão gráfica pra abrir nada)")
    args = ap.parse_args()

    args.config = os.path.abspath(args.config)
    if not os.path.exists(args.config):
        print(f"ERRO: config não encontrado: {args.config}", file=sys.stderr)
        sys.exit(1)

    local = args.host in ("127.0.0.1", "localhost", "::1")
    if not local and not args.token:
        print("ERRO: --host fora de 127.0.0.1 expõe um endpoint que EXECUTA comando na sua\n"
              "máquina. Isso exige --token (ou a variável WAR_ROOM_TOKEN). Sem token, qualquer\n"
              "um na mesma rede poderia disparar rodadas e queimar seu saldo de API.",
              file=sys.stderr)
        sys.exit(2)

    Handler.servico = Servico(args)
    servidor = ThreadingHTTPServer((args.host, args.porta), Handler)
    print(f"war room de pé em http://{args.host}:{args.porta}", file=sys.stderr)
    print(f"  config: {args.config}", file=sys.stderr)
    print(f"  html:   {os.path.abspath(args.html)}", file=sys.stderr)
    print(f"  comando da rodada: {' '.join(Handler.servico.comando())}", file=sys.stderr)
    if args.token:
        print("  token exigido em todo pedido (X-War-Room-Token)", file=sys.stderr)
    if not local:
        print(f"  ATENÇÃO: escutando em {args.host} — alcançável pela rede", file=sys.stderr)
    if local and not args.sem_navegador:
        # o socket já está aberto (ThreadingHTTPServer acima faz bind no construtor),
        # então é seguro abrir o navegador antes de serve_forever() — sem isso o
        # usuário precisaria copiar a URL à mão toda vez que subisse o servidor.
        threading.Timer(0.4, lambda: webbrowser.open(f"http://{args.host}:{args.porta}")).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nencerrando", file=sys.stderr)
        servidor.server_close()


if __name__ == "__main__":
    main()
