"""Mirage Voces: cura las grabaciones de Mirage con Whisper.

Fuentes que procesa (todas en <juego>/Mirage):
  - Tu voz: Recording/*.opus, que es lo que Mirage reproduce cuando te imitan.
  - La voz de tus amigos: Centralizado/Entrantes/<steamId>/*.wav, que graba el mod
    MirageVoces en el PC del anfitrion. Las frases buenas se convierten a
    Centralizado/Activas/<steamId>/*.opus y el mod las usa cuando un monstruo imita a ese amigo.

Para cada grabacion nueva:
  1. La transcribe con Whisper (en local, sin internet).
  2. La clasifica (nombre, ayuda, llamada, seguir, aviso, botin, nave, risa...).
  3. Si es util la deja activa; si es basura la borra (para no gastar disco).
  4. Recorta las respuestas cortas que contenga ("Si", "Estoy aqui", "Ya voy"...) para que
     los monstruos contesten bien a las preguntas (ver respuestas.py).
  5. Guarda una copia de las utiles en Biblioteca/<jugador>/<categoria>/, con indice y resumen.
Ademas importa audios que metas en Mirage/Importar como frases tuyas, y en Mirage/Importar/Bracken
las frases del Bracken con tu voz (ver monstruos.py).

Uso:  python mirage_voces.py [--simular] [--config ruta]
"""
import argparse
import datetime as dt
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import warnings

from monstruos import MONSTRUOS, importar_monstruos, resumen_monstruos
from respuestas import Respuestas

# Sin el kit de CUDA completo Whisper avisa en cada frase de que alinea las palabras algo mas lento: da igual.
warnings.filterwarnings("ignore", message="Failed to launch Triton kernels")

AQUI = os.path.dirname(os.path.abspath(__file__))
EXT_IMPORT = (".wav", ".mp3", ".m4a", ".ogg", ".opus", ".flac", ".aac", ".webm")
# Mismo formato que escribe Mirage: Ogg Opus, 48 kHz, mono, 24 kbps, tramas de 20 ms.
FFMPEG_OPUS = ["-ac", "1", "-ar", "48000", "-c:a", "libopus", "-b:a", "24k", "-frame_duration", "20"]


def normalizar(texto):
    texto = unicodedata.normalize("NFD", texto.lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9ñ ]", " ", texto)).strip()


def contiene(texto_norm, frase):
    return re.search(r"(?<![a-z])" + re.escape(normalizar(frase)) + r"(?![a-z])", texto_norm) is not None


# Palabras a las que Whisper pega el nombre que va detras ("correleo" = "corre, Leo"; "oyeana" = "oye, Ana").
PEGADAS = {"corre", "ven", "vente", "oye", "ay", "eh", "ey", "hola", "vamos", "venga", "mira", "espera", "cuidado",
           "dale", "sal", "quieto", "tira", "vete", "ayuda", "socorro", "tio", "y", "que", "adios"}


# Lo que delata que se habla del propio mod o de tecnologia, no de la partida.
META = re.compile(r"\b(mods?|whisper|prueba de voces|pruebas de voces|funciona|funcionar|bots?|discord|configuracion|"
                  r"config|thunderstore|instalar|instalado|servidor|ordenador|micro|microfono|grabando|grabacion|"
                  r"grabar|audios?|programa|script|virus|antivirus|subtitul\w*|suscrib\w*|intensidad|actualiza\w*|"
                  r"descarga\w*|calibr\w*|mirage)\b")


def cargar_apodos(ruta=os.path.join(AQUI, "apodos.txt")):
    """apodos.txt: 'NombreDeSteam: apodo1, apodo2' por linea -> {apodo: NombreDeSteam}."""
    alias = {}
    try:
        with open(ruta, encoding="utf-8-sig") as f:
            for linea in f:
                linea = linea.strip()
                if not linea or linea.startswith("#") or ":" not in linea:
                    continue
                steam, apodos = linea.rsplit(":", 1)
                for apodo in apodos.split(","):
                    if apodo.strip():
                        alias[apodo.strip()] = steam.strip()
    except OSError:
        pass
    return alias


def nombre_carpeta(texto):
    return re.sub(r'[<>:"/\\|?*]', "_", texto).strip() or "sin_nombre"


def a_opus(src, dst, normalizar_volumen, efecto=None):
    filtros = [f for f in (efecto, "loudnorm=I=-18:TP=-1.5" if normalizar_volumen else None) if f]
    filtro = ["-af", ",".join(filtros)] if filtros else []
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    # Se escribe aparte y se reemplaza al final, para no dejar nunca un archivo a medias.
    # La extension .tmp evita que Mirage lo elija mientras se escribe.
    tmp = dst + ".tmp"
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "fatal", "-i", src] + filtro + FFMPEG_OPUS + ["-f", "ogg", tmp])
    try:
        if r.returncode != 0:
            return False
        os.replace(tmp, dst)  # falla si el juego lo esta leyendo justo ahora: se deja como estaba
        return True
    except OSError:
        return False
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


class Fuente:
    """Un origen de grabaciones: tu voz (Recording) o la de un amigo (Entrantes/<steamId>)."""

    def __init__(self, clave, jugador, origen, ext, activas, convertir):
        self.clave, self.jugador, self.origen, self.ext = clave, jugador, origen, ext
        self.activas = activas        # carpeta donde quedan las frases que se reproducen
        self.convertir = convertir    # True: wav -> opus en 'activas'; False: ya estan en su sitio


class Curador:
    def __init__(self, cfg, simular):
        self.cfg = cfg
        self.simular = simular
        self.base = os.path.join(cfg["carpeta_juego"], "Mirage")
        self.rec = os.path.join(self.base, "Recording")
        self.central = os.path.join(self.base, "Centralizado")
        self.bib = os.path.join(self.base, "Biblioteca")
        self.desc = os.path.join(self.base, "Descartadas")
        self.imp = os.path.join(self.base, "Importar")
        self.ruta_indice = os.path.join(self.bib, "indice.json")
        for d in (self.rec, self.bib, self.imp, os.path.join(self.central, "Entrantes")):
            os.makedirs(d, exist_ok=True)
        self.indice = self._cargar_indice()
        self.modelo = None
        self.cats = {c: [normalizar(p) for p in ps] for c, ps in cfg["categorias"].items()}
        self.basura = [normalizar(p) for p in cfg["frases_basura"]]
        self.recargar_jugadores()
        self.resp = Respuestas(self)

    def recargar_jugadores(self):
        """Lee jugadores.json (lo escribe el mod) y apodos.txt, y actualiza los nombres que cuentan como 'nombre'."""
        self.jugadores = self._cargar_jugadores()
        self.alias = dict(self.cfg.get("alias_amigos") or {})
        self.alias.update(cargar_apodos())
        nombres = list(self.cfg.get("nombres_amigos", [])) + list(self.jugadores.values()) + list(self.alias.keys())
        self.nombres = sorted({normalizar(n) for n in nombres if normalizar(n)})

    # ---------- datos ----------
    def _cargar_indice(self):
        try:
            with open(self.ruta_indice, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _guardar_indice(self):
        if self.simular:
            return
        tmp = self.ruta_indice + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.indice, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.ruta_indice)

    def _cargar_jugadores(self):
        try:
            with open(os.path.join(self.central, "jugadores.json"), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def fuentes(self):
        yield Fuente("yo", "Tu", self.rec, ".opus", self.rec, False)
        entrantes = os.path.join(self.central, "Entrantes")
        for sid in sorted(os.listdir(entrantes)):
            if os.path.isdir(os.path.join(entrantes, sid)):
                nombre = nombre_carpeta(self.jugadores.get(sid, sid))
                yield Fuente(sid, nombre, os.path.join(entrantes, sid), ".wav",
                             os.path.join(self.central, "Activas", sid), True)

    # ---------- whisper ----------
    def _whisper(self):
        if self.modelo is None:
            import torch
            import whisper
            # La grafica si hay una version de Whisper que la sepa usar; si no, el procesador.
            self.dispositivo = "cuda" if torch.cuda.is_available() else "cpu"
            nombre = self.cfg.get("modelo_whisper_cpu", "base") if self.dispositivo == "cpu" and self.en_vivo \
                else self.cfg["modelo_whisper"]
            print(f"Cargando Whisper ({nombre}) en {'la grafica' if self.dispositivo == 'cuda' else 'el procesador'}...")
            self.modelo = whisper.load_model(nombre, device=self.dispositivo)
        return self.modelo

    en_vivo = False
    dispositivo = "cpu"

    _vocab_cache = (0, None, set())

    def vocabulario(self):
        """Texto que se le da a Whisper como contexto para que escriba bien vuestros nombres y las palabras del
        juego ("Bracken" y no "braquen", y vuestros nombres). Sale de diccionario.txt y de los nombres y apodos."""
        ruta = os.path.join(AQUI, "diccionario.txt")
        try:
            cambio = os.path.getmtime(ruta)
        except OSError:
            cambio = 0
        if self._vocab_cache[0] == cambio and self._vocab_cache[1] is not None and cambio:
            return self._vocab_cache[1], self._vocab_cache[2]
        palabras = []
        try:
            with open(ruta, encoding="utf-8-sig") as f:
                for linea in f:
                    linea = linea.strip()
                    if linea and not linea.startswith("#"):
                        palabras += [p.strip() for p in linea.split(",") if p.strip()]
        except OSError:
            pass
        # Los nombres (los del diccionario y los de apodos.txt / jugadores) van aparte, al final del texto.
        de_personas = {normalizar(n) for n in list(self.alias.keys()) + list(self.alias.values())
                       + list(self.jugadores.values())}
        nombres = [w for w in palabras if normalizar(w) in de_personas]
        palabras = [w for w in palabras if normalizar(w) not in de_personas]
        ya = {normalizar(x) for x in nombres}
        nombres += sorted({n for n in list(self.alias.keys()) + list(self.jugadores.values())
                           if n and "[" not in n and normalizar(n) not in ya})
        # Al hablar os llamais por el apodo, no por el nombre de Steam ("xX_Pro_Gamer_Xx"):
        # el de Steam solo se queda si esa persona no tiene apodos (o si tambien es su apodo).
        apodos = {normalizar(a) for a in self.alias.keys()}
        steam_con_apodo = {normalizar(st) for st in self.alias.values()}
        nombres = [n for n in nombres if normalizar(n) in apodos or normalizar(n) not in steam_con_apodo]
        nombres = [n for n in nombres if not any(ch.isdigit() for ch in n) and max(len(w) for w in n.split()) <= 12]
        # Whisper solo usa los ultimos 223 "tokens" del texto: entran todos los nombres y, despues, las palabras
        # del diccionario por orden (lo de arriba del archivo es lo mas importante) mientras quepan.
        def armar(pal):
            return ("Partida de Lethal Company. Hablan de: " + ", ".join(pal) + ". Se llaman: " + ", ".join(nombres) + ".")
        try:
            import whisper
            tok = whisper.tokenizer.get_tokenizer(multilingual=True, language=self.cfg["idioma"], task="transcribe")
            cabe = lambda t: len(tok.encode(" " + t)) <= 220
        except Exception:
            cabe = lambda t: len(t) <= 600
        entran = []
        for w in palabras:
            if cabe(armar(entran + [w])):
                entran.append(w)
        palabras = entran
        texto = armar(palabras) if nombres or palabras else None
        conocidas = {normalizar(x) for x in nombres + palabras}
        conocidas = {w for x in conocidas for w in x.split()}
        self._vocab_cache = (cambio, texto, conocidas)
        return texto, conocidas

    def transcribir(self, ruta):
        import whisper
        audio = whisper.load_audio(ruta)
        dur = len(audio) / whisper.audio.SAMPLE_RATE
        if dur < self.cfg["duracion_minima_seg"]:
            return {"texto": "", "dur": dur, "confianza": -9, "silencio": 1}
        modelo = self._whisper()
        prompt, conocidas = self.vocabulario()
        opciones = dict(language=self.cfg["idioma"], fp16=self.dispositivo == "cuda", condition_on_previous_text=False,
                        temperature=0, word_timestamps=True, initial_prompt=prompt)
        if self.dispositivo == "cuda":
            opciones["beam_size"] = self.cfg.get("beam_size", 3)  # compara varias opciones: mas preciso
        # Un "jajaja" o un ruido pueden hacer que Whisper escriba sin parar: una frase de 15 s cabe de sobra en 120.
        opciones["sample_len"] = 120
        r = modelo.transcribe(audio, **opciones)
        segs = r.get("segments") or []
        palabras = [w for s in segs for w in s.get("words") or []]
        conf = sum(s["avg_logprob"] for s in segs) / len(segs) if segs else -9
        sil = max((s["no_speech_prob"] for s in segs), default=1)
        texto = r["text"].strip()
        # Con el diccionario, en un ruido Whisper a veces "lee" palabras de la lista: si casi seguro no hay voz
        # y todo lo que escribe sale de la lista, no se cuenta.
        dichas = normalizar(texto).split()
        if dichas and sil > 0.5 and all(w in conocidas for w in dichas):
            texto, palabras = "", []
        # Una risa o un ruido largo lo "rellena" repitiendo una palabra de la lista ("Max, max, max..."): eso no es
        # que nombren a nadie. Se queda como risa para que no cuente como nombre.
        seguidas = max((sum(1 for _ in g) for _, g in itertools.groupby(dichas)), default=0)
        if seguidas >= 4 and any(w in conocidas and dichas.count(w) >= 4 for w in set(dichas)):
            texto, palabras = "jajaja", []
        return {"texto": texto, "dur": dur, "confianza": conf, "silencio": sil, "palabras": palabras}

    # ---------- clasificacion ----------
    def clasificar(self, t):
        n = normalizar(t["texto"])
        if any(b in n for b in self.basura):
            return [], "frase inventada por Whisper"
        if t["dur"] < self.cfg["duracion_minima_seg"]:
            return [], "demasiado corta"
        if t["dur"] > self.cfg["duracion_maxima_seg"]:
            return [], "demasiado larga"
        if not n:
            return [], "sin voz"
        if t["silencio"] > 0.6 and t["confianza"] < -1.0:
            return [], "ruido o silencio"
        cats = [c for c, ps in self.cats.items() if any(contiene(n, p) for p in ps)]
        palabras = n.split()
        # Hablar del mod, de Discord, de grabar... no lo diria nadie en plena partida: un monstruo no lo usaria.
        if META.search(n) and not set(cats) & {"grito", "risa", "ayuda"}:
            return [], "habla del mod / de tecnologia"
        # Risas y gritos se escriben de mil formas ("jajajaja", "aaaah", "ayyy"): se reconocen por su forma.
        if "risa" not in cats and any(re.fullmatch(r"(ja|je|ji|ha){2,}j?", w) for w in palabras):
            cats.append("risa")
        if "grito" not in cats and any(re.fullmatch(r"a{2,}h*|ah{2,}|ay+|a+y+", w) for w in palabras):
            cats.append("grito")
        if any(contiene(n, nm) for nm in self.nombres):
            cats.insert(0, "nombre")
        # Whisper convierte murmullos en palabras repetidas ("emay emay emay")
        repetitiva = len(set(palabras)) <= len(palabras) / 2
        if not cats and len(palabras) >= 3 and t["confianza"] > -0.8 and not repetitiva:
            cats = ["frase"]
        # "si"/"vale" sueltos solo valen si se entienden bien
        if cats == ["afirmacion"] and t["confianza"] < -0.6:
            return [], "poco clara"
        if not cats:
            return [], "no aporta"
        return cats, ""

    def puntuar(self, t, cats):
        bonus = {"nombre": 3, "ayuda": 3, "grito": 2, "llamada": 2, "seguir": 2, "aviso": 2, "risa": 1}
        return round(sum(bonus.get(c, 1) for c in cats) + t["confianza"], 3)

    # ---------- acciones ----------
    def _mover(self, src, dst):
        if not self.simular:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)

    def _copiar(self, src, dst):
        if not self.simular:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)

    def _rel(self, ruta):
        return os.path.relpath(ruta, self.base)

    def _abs(self, rel):
        return os.path.join(self.base, rel)

    def _es_anfitrion(self, carpeta):
        """La carpeta es tuya si se llama como tu nombre de Steam (config 'mi_nombre_steam') o uno de tus apodos."""
        yo = normalizar(self.cfg.get("mi_nombre_steam", ""))
        if not yo:
            return False
        n = normalizar(carpeta)
        return n == yo or normalizar(self.alias.get(carpeta, "")) == yo or any(
            normalizar(k) == n and normalizar(v) == yo for k, v in self.alias.items())

    def _buscar_amigo(self, carpeta):
        """Steam id del amigo de una carpeta de Importar: por alias, por id o por su nombre de Steam."""
        alias = {normalizar(k): v for k, v in self.alias.items()}
        objetivo = alias.get(normalizar(carpeta), carpeta)
        if str(objetivo).isdigit() and str(objetivo) in self.jugadores:
            return str(objetivo)
        n = normalizar(str(objetivo))
        exactos = [sid for sid, nom in self.jugadores.items() if normalizar(nom) == n]
        parecidos = [sid for sid, nom in self.jugadores.items() if n and (n in normalizar(nom) or normalizar(nom) in n)]
        # "Ana" -> "xX_AnaXP_Xx": alguna palabra del nombre de Steam empieza igual que la carpeta.
        def palabras(nom):
            return [w for w in re.split(r"[^a-z0-9ñ]+", normalizar(nom).replace(" ", "_")) if len(w) >= 4]
        por_palabra = [sid for sid, nom in self.jugadores.items() if n
                       and any(n.replace(" ", "").startswith(w) or w.startswith(n.replace(" ", "")) for w in palabras(nom))]
        for opciones in (exactos, parecidos, por_palabra):
            if len(opciones) == 1:
                return opciones[0]
        return None

    def importar(self):
        """Convierte los audios de Importar. Sueltos = frases tuyas; en Importar/<amigo>/ = de ese amigo.
        Devuelve {clave de fuente: nombres creados} para procesarlos ya, sin esperar."""
        creados = {}
        importar_monstruos(self, normalizar)  # Importar/Bracken/...: voces para un monstruo, no frases de nadie

        def lote(carpeta, clave, destino_de, normalizar_volumen):
            for f in sorted(os.listdir(carpeta)):
                src = os.path.join(carpeta, f)
                if not (os.path.isfile(src) and f.lower().endswith(EXT_IMPORT)):
                    continue
                base, ext = os.path.splitext(f)
                destino = destino_de("imp_" + re.sub(r"[^\w-]", "_", base))
                print(f"Importando {os.path.relpath(src, self.imp)}")
                if self.simular:
                    continue
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                if destino.endswith(".opus"):
                    ok = a_opus(src, destino, normalizar_volumen)
                else:  # wav para el flujo de amigos, igual que lo que graba el mod
                    tmp = destino + ".tmp"
                    ok = subprocess.run(["ffmpeg", "-y", "-loglevel", "fatal", "-i", src, "-ac", "1", "-ar", "48000",
                                         "-c:a", "pcm_s16le", "-f", "wav", tmp]).returncode == 0
                    if ok:
                        os.replace(tmp, destino)
                if ok:
                    self._mover(src, os.path.join(self.imp, "hechos", os.path.relpath(src, self.imp)))
                    creados.setdefault(clave, set()).add(os.path.basename(destino))
                else:
                    print(f"  No se pudo convertir {f} (¿ffmpeg instalado?)")

        lote(self.imp, "yo", lambda b: os.path.join(self.rec, b + ".opus"), False)
        for carpeta in sorted(os.listdir(self.imp)):
            ruta = os.path.join(self.imp, carpeta)
            if not os.path.isdir(ruta) or carpeta.lower() == "hechos" or normalizar(carpeta) in MONSTRUOS:
                continue
            if not any(f.lower().endswith(EXT_IMPORT) for f in os.listdir(ruta)):
                continue
            if self._es_anfitrion(carpeta):
                # Tu propia carpeta: van a Recording, que es lo que Mirage usa cuando un monstruo te imita.
                print(f"'{carpeta}' eres tú")
                lote(ruta, "yo", lambda b: os.path.join(self.rec, b + ".opus"), True)
                continue
            sid = self._buscar_amigo(carpeta)
            if sid is None:
                conocidos = ", ".join(f"{n}" for n in self.jugadores.values()) or "ninguno todavia"
                print(f"\n¡OJO! No sé quién es '{carpeta}'. Jugadores conocidos: {conocidos}.")
                print("  Renombra la carpeta con su nombre de Steam, o añádelo en 'alias_amigos' de config.json.")
                print("  (Tiene que haber jugado al menos una vez contigo de anfitrión con el mod.)\n")
                continue
            print(f"'{carpeta}' es {self.jugadores[sid]}")
            lote(ruta, sid, lambda b, sid=sid: os.path.join(self.central, "Entrantes", sid, b + ".wav"), True)
        return creados

    def pendientes(self, fuente, importadas=(), espera=15):
        """Grabaciones de una fuente que aun no estan en el indice.
        Lo que se acaba de escribir puede estar a medias: se deja para la proxima vez."""
        if not os.path.isdir(fuente.origen):
            return []
        archivos = sorted(f for f in os.listdir(fuente.origen) if f.lower().endswith(fuente.ext))
        return [f for f in archivos if f"{fuente.clave}/{f}" not in self.indice
                and (f in importadas or self._terminado(os.path.join(fuente.origen, f), espera))]

    @staticmethod
    def _terminado(ruta, espera):
        """Un .opus de Mirage esta completo cuando su ultima pagina Ogg marca el final (asi no hay que
        esperar segundos de mas en vivo). Los .wav del mod se escriben aparte y se renombran: estan
        completos en cuanto aparecen. Si algo falla, se espera 'espera' segundos sin cambios."""
        try:
            edad = time.time() - os.path.getmtime(ruta)
            if edad > espera:
                return True
            if ruta.lower().endswith(".opus"):
                with open(ruta, "rb") as f:
                    f.seek(max(0, os.path.getsize(ruta) - 65536))
                    cola = f.read()
                i = cola.rfind(b"OggS")
                return i >= 0 and i + 5 < len(cola) and bool(cola[i + 5] & 4)
            return edad > 0.3
        except OSError:
            return False

    def procesar_archivo(self, fuente, f, etiqueta=""):
        """Transcribe, clasifica y guarda o descarta una grabacion. Devuelve su entrada del indice (o None)."""
        ruta = os.path.join(fuente.origen, f)
        try:
            t = self.transcribir(ruta)
        except Exception as e:  # archivo corrupto o a medio escribir
            print(f"  {etiqueta}{f}: no se pudo leer ({e})")
            return None
        cats, motivo = self.clasificar(t)
        # Antes de guardarla o tirarla: los "Si", "Estoy aqui"... que tenga sirven para contestar.
        if motivo not in ("frase inventada por Whisper", "ruido o silencio", "demasiado larga"):
            self.resp.extraer(fuente.clave, ruta, t, os.path.splitext(f)[0])
        importada = f.startswith("imp_")
        # Lo que se grabo a proposito se guarda aunque Whisper no lo entienda (un susurro, un grito raro).
        if importada and not cats and t["dur"] >= self.cfg["duracion_minima_seg"] and t["dur"] <= self.cfg["duracion_maxima_seg"]:
            cats = ["frase"]
        entrada = {"jugador": fuente.jugador, "texto": t["texto"], "duracion": round(t["dur"], 2),
                   "confianza": round(t["confianza"], 3), "fecha": dt.datetime.now().isoformat(timespec="seconds"),
                   "resp": 2}
        if cats:
            opus = os.path.splitext(f)[0] + ".opus"
            activa = os.path.join(fuente.activas, opus)
            copia = os.path.join(self.bib, fuente.jugador, cats[0], opus)
            if fuente.convertir:
                if not self.simular:
                    if not a_opus(ruta, activa, normalizar_volumen=True):
                        print(f"  {etiqueta}{f}: no se pudo convertir (¿ffmpeg?)")
                        return None
                    os.remove(ruta)
            else:
                activa = ruta
            self._copiar(activa, copia)
            # Las grabadas a proposito valen mas: no se retiran antes que las pilladas en partida.
            entrada.update(estado="activa", categorias=cats, puntos=self.puntuar(t, cats) + (5 if importada else 0),
                           activa=self._rel(activa), copia=self._rel(copia), importada=importada)
            print(f"  {etiqueta}GUARDADA  {cats[0]:<10} \"{t['texto']}\"")
        else:
            if not self.simular:
                os.remove(ruta)
            entrada.update(estado="descartada", motivo=motivo)
            print(f"  {etiqueta}descartada ({motivo}) \"{t['texto']}\"")
        self.indice[f"{fuente.clave}/{f}"] = entrada
        return entrada

    def procesar(self, fuente, importadas=()):
        nuevas = self.pendientes(fuente, importadas)
        if not nuevas:
            return 0, 0
        print(f"\n== {fuente.jugador}: {len(nuevas)} grabaciones nuevas ==")
        guardadas = descartadas = 0
        for i, f in enumerate(nuevas, 1):
            e = self.procesar_archivo(fuente, f, f"[{i}/{len(nuevas)}] ")
            if e is not None:
                if e["estado"] == "activa":
                    guardadas += 1
                else:
                    descartadas += 1
            if i % 20 == 0:
                self._guardar_indice()
        self._guardar_indice()
        return guardadas, descartadas

    def restaurar(self):
        """Si Mirage borro su carpeta (o falta alguna frase activa), la vuelve a poner desde la biblioteca."""
        if not self.cfg.get("restaurar_biblioteca", True):
            return 0
        n = 0
        for e in self.indice.values():
            if e.get("estado") != "activa" or os.path.exists(self._abs(e["activa"])):
                continue
            if os.path.exists(self._abs(e["copia"])):
                self._copiar(self._abs(e["copia"]), self._abs(e["activa"]))
                n += 1
        return n

    def limitar(self):
        """Cada jugador tiene como maximo N frases activas: se retiran las de menos puntos (siguen en la biblioteca)."""
        por_jugador = {}
        for clave, e in self.indice.items():
            if e.get("estado") == "activa" and os.path.exists(self._abs(e["activa"])):
                por_jugador.setdefault(clave.split("/", 1)[0], []).append((e["puntos"], e["fecha"], clave))
        retiradas = 0
        for activas in por_jugador.values():
            sobran = len(activas) - self.cfg["max_grabaciones_activas"]
            for _, _, clave in sorted(activas)[:max(0, sobran)]:
                if not self.simular:
                    os.remove(self._abs(self.indice[clave]["activa"]))
                self.indice[clave]["estado"] = "retirada"
                retiradas += 1
        self._guardar_indice()
        return retiradas

    def voz_rara(self):
        """Da un efecto sutil (grave, eco, temblor, metalico) a unas pocas frases activas.

        En cada pasada se vuelve a sortear cuales: las que eran raras vuelven a sonar normal
        y otras pasan a ser raras. La copia de la biblioteca siempre queda limpia.
        """
        cfg = self.cfg.get("voz_rara") or {}
        prob = float(cfg.get("probabilidad", 0))
        efectos = cfg.get("efectos") or {}
        import random
        raras = limpiadas = 0
        for e in self.indice.values():
            if e.get("estado") != "activa":
                continue
            activa, copia = self._abs(e["activa"]), self._abs(e["copia"])
            if not os.path.exists(copia):
                continue
            nuevo = random.choice(sorted(efectos)) if efectos and random.random() < prob else None
            if nuevo is None and not e.get("efecto"):
                continue  # sigue normal, no hay nada que tocar
            if self.simular:
                raras += nuevo is not None
                continue
            if nuevo:
                # Las frases de amigos ya se normalizaron al curarlas; la copia limpia sirve de base.
                if not a_opus(copia, activa, normalizar_volumen=False, efecto=efectos[nuevo]):
                    print(f"  No se pudo aplicar '{nuevo}' a {os.path.basename(activa)}")
                    continue
                raras += 1
            else:
                self._copiar(copia, activa)
                limpiadas += 1
            e["efecto"] = nuevo
        self._guardar_indice()
        return raras, limpiadas

    def mencionados(self, texto):
        """Nombres de Steam de los jugadores conocidos que salen en una frase (por nombre o apodo)."""
        n = normalizar(texto)
        quien = {}
        for steam in self.jugadores.values():
            quien[normalizar(steam)] = steam
        for apodo, steam in self.alias.items():
            quien[normalizar(apodo)] = steam
        palabras = n.split()

        def sale(nombre):
            if " " in nombre:
                return contiene(n, nombre)
            # "Robertito" cuenta como "Robert", "Anita" como "Ana" (4 letras o mas); los cortos, exactos.
            # Whisper a veces pega el nombre a la palabra de antes: "corre, Leo" -> "correleo".
            return any(w == nombre or (len(w) >= 4 and len(nombre) >= 4 and (w.startswith(nombre) or nombre.startswith(w)))
                       or (w.endswith(nombre) and w[:-len(nombre)] in PEGADAS)
                       for w in palabras)

        return {steam for nombre, steam in quien.items() if len(nombre) >= 2 and sale(nombre)}

    def nombre_solo(self, norm):
        """Si la frase es solo el nombre (o apodo) de un jugador, con alguna muletilla ("eh", "oye"), devuelve
        su nombre de Steam: "leo leo" -> Leo_Gamer, "eh ana" -> AnaXP. Si no, None."""
        if not norm or norm == "?":
            return None
        quien = {normalizar(steam): steam for steam in self.jugadores.values()}
        quien.update({normalizar(apodo): steam for apodo, steam in self.alias.items()})
        resto, encontrados = " " + norm + " ", set()
        for nombre in sorted(quien, key=len, reverse=True):  # primero los largos ("juan pedro")
            if len(nombre) >= 2 and f" {nombre} " in resto:
                encontrados.add(quien[nombre])
                while f" {nombre} " in resto:
                    resto = resto.replace(f" {nombre} ", " ")
        muletillas = {"eh", "oye", "ey", "hey", "tio", "tia", "hola", "a", "y", "que", "e", "o", "ah"}
        if len(encontrados) != 1 or any(w not in muletillas for w in resto.split()):
            return None
        return encontrados.pop()

    def aparcar_ausentes(self, presentes):
        """Aparta (sin borrar) las frases activas que nombran a alguien que no esta jugando, y devuelve
        las aparcadas cuyos nombrados ya estan. presentes = nombres de Steam en la partida, o None
        para devolverlo todo (al cerrar)."""
        aparcadas = os.path.join(self.central, "Aparcadas")
        presentes_n = None if presentes is None else {normalizar(p) for p in presentes}
        apartadas = devueltas = 0
        for clave, e in self.indice.items():
            if e.get("estado") not in ("activa", "aparcada"):
                continue
            nombrados = {normalizar(s) for s in self.mencionados(e.get("texto", ""))}
            falta = presentes_n is not None and bool(nombrados - presentes_n)
            activa = self._abs(e["activa"])
            parking = os.path.join(aparcadas, clave.replace("/", os.sep))
            try:
                if falta and e["estado"] == "activa" and os.path.exists(activa):
                    self._mover(activa, parking)
                    e["estado"] = "aparcada"
                    apartadas += 1
                elif not falta and e["estado"] == "aparcada":
                    if os.path.exists(parking):
                        self._mover(parking, activa)
                    elif os.path.exists(self._abs(e["copia"])):
                        self._copiar(self._abs(e["copia"]), activa)
                    e["estado"] = "activa"
                    devueltas += 1
            except OSError:
                continue  # el juego lo esta leyendo justo ahora: se intenta en la siguiente vuelta
        if apartadas or devueltas:
            self._guardar_indice()
        return apartadas, devueltas

    def preparar_efectos(self):
        """Copias ligeras (WAV 16 kHz mono, max 6 s) de las frases activas para los efectos del mod
        (cadaveres, walkies, puertas). Van en Centralizado/Efectos/<jugador>/<categoria>__<nombre>.wav;
        el mod las envia a todos cuando toca. Siempre salen de la copia limpia, sin voz rara."""
        raiz = os.path.join(self.central, "Efectos")
        deseados = {}
        for clave, e in self.indice.items():
            if e.get("estado") != "activa" or e["duracion"] > 6 or not os.path.exists(self._abs(e["copia"])):
                continue
            jugador = clave.split("/", 1)[0]
            nombre = f"{e['categorias'][0]}__{os.path.splitext(os.path.basename(e['copia']))[0]}.wav"
            deseados[os.path.join(raiz, jugador, nombre)] = self._abs(e["copia"])
        if not self.simular and os.path.isdir(raiz) or deseados:
            os.makedirs(raiz, exist_ok=True)
            with open(os.path.join(raiz, "nombres.txt"), "w", encoding="utf-8") as fh:
                for clave, e in self.indice.items():
                    if e.get("estado") != "activa" or e["duracion"] > 6:
                        continue
                    jugador = clave.split("/", 1)[0]
                    nombre = f"{e['categorias'][0]}__{os.path.splitext(os.path.basename(e['copia']))[0]}.wav"
                    for steam in self.mencionados(e.get("texto", "")):
                        fh.write(f"{jugador}/{nombre}|{steam}\n")
        creados = borrados = 0
        for destino, origen in deseados.items():
            if os.path.exists(destino) or self.simular:
                continue
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            tmp = destino + ".tmp"
            r = subprocess.run(["ffmpeg", "-y", "-loglevel", "fatal", "-i", origen, "-af", "loudnorm=I=-18:TP=-1.5",
                                "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-f", "wav", tmp])
            if r.returncode == 0:
                os.replace(tmp, destino)
                creados += 1
        if os.path.isdir(raiz):
            for carpeta, _, archivos in os.walk(raiz):
                for f in archivos:
                    p = os.path.join(carpeta, f)
                    if p not in deseados and f != "nombres.txt":
                        if not self.simular:
                            os.remove(p)
                        borrados += 1
        return creados, borrados

    def respuestas_pendientes(self):
        """Saca las respuestas cortas de las grabaciones curadas antes de que existiera esto (una sola vez),
        incluidas las descartadas que aun queden en disco."""
        hechas = 0
        for clave, e in list(self.indice.items()):
            hecho = e.get("resp", 0)
            if hecho >= 2:
                continue
            jugador, f = clave.split("/", 1)
            rutas = [self._abs(e[k]) for k in ("activa", "copia") if e.get(k)]
            rutas.append(os.path.join(self.desc, jugador, f))
            ruta = next((r for r in rutas if os.path.exists(r)), None)
            if ruta and not self.simular:
                try:
                    t = self.transcribir(ruta)
                    if t["texto"]:
                        # resp 1 = ya se sacaron las respuestas; ahora solo faltan los nombres sueltos.
                        hechas += self.resp.extraer(jugador, ruta, t, os.path.splitext(f)[0], solo_nombres=hecho == 1)
                except Exception as ex:
                    print(f"  {f}: no se pudo leer ({ex})")
            e["resp"] = 2
        self._guardar_indice()
        if hechas:
            self.resp.guardar()
        return hechas

    def recalibrar(self):
        """Vuelve a transcribir las frases guardadas con el modelo y el diccionario actuales (p. ej. al pasar de
        "small" a "turbo"), y las reclasifica. Las que ahora no se entienden se quedan como estaban.
        Cada frase se hace una vez por modelo: se puede parar y seguir otro dia."""
        modelo = self.cfg["modelo_whisper"]
        lista = [(k, e) for k, e in self.indice.items()
                 if e.get("estado") in ("activa", "retirada", "aparcada") and e.get("recalibrada") != modelo
                 and e.get("copia") and os.path.exists(self._abs(e["copia"]))]
        print(f"Recalibrando {len(lista)} frases con '{modelo}'...")
        cambiadas = movidas = 0
        for i, (k, e) in enumerate(lista, 1):
            try:
                t = self.transcribir(self._abs(e["copia"]))
            except Exception as ex:
                print(f"  {k}: no se pudo leer ({ex})")
                continue
            cats, _ = self.clasificar(t)
            if cats and t["texto"]:
                if t["texto"] != e.get("texto"):
                    print(f"  [{i}/{len(lista)}] \"{e.get('texto', '')[:60]}\"  ->  \"{t['texto'][:60]}\"")
                    cambiadas += 1
                viejo = e.get("categorias") or ["frase"]
                e.update(texto=t["texto"], confianza=round(t["confianza"], 3), categorias=cats,
                         puntos=self.puntuar(t, cats) + (5 if e.get("importada") else 0))
                if cats[0] != viejo[0]:
                    # Su copia de la Biblioteca pasa a la carpeta de su tipo nuevo.
                    nueva = os.path.join(self.bib, e.get("jugador", "Tu"), cats[0], os.path.basename(e["copia"]))
                    try:
                        self._mover(self._abs(e["copia"]), nueva)
                        e["copia"] = self._rel(nueva)
                        movidas += 1
                    except OSError:
                        e["categorias"] = viejo  # no se pudo mover: mejor que todo siga cuadrando
            e["recalibrada"] = modelo
            if i % 50 == 0:
                self._guardar_indice()
                print(f"  ... {i}/{len(lista)}")
        self._guardar_indice()
        return len(lista), cambiadas, movidas

    def purgar_descartadas(self):
        """Las descartadas ya no se guardan: se borra lo que quede de versiones anteriores."""
        n = 0
        if os.path.isdir(self.desc) and not self.simular:
            n = sum(len(a) for _, _, a in os.walk(self.desc))
            shutil.rmtree(self.desc, ignore_errors=True)
        return n

    def resumen(self):
        arbol = {}
        for e in self.indice.values():
            if e.get("estado") in ("activa", "retirada"):
                arbol.setdefault(e.get("jugador", "Tu"), {}).setdefault(e["categorias"][0], []).append(e)
        lineas = [f"Biblioteca de Mirage - {dt.datetime.now():%d/%m/%Y %H:%M}", ""]
        totales = {}
        for jugador in sorted(arbol):
            cats = arbol[jugador]
            totales[jugador] = sum(len(v) for v in cats.values())
            lineas.append(f"######## {jugador} ({totales[jugador]} frases) ########")
            for c in sorted(cats, key=lambda c: -len(cats[c])):
                lineas.append(f"== {c} ({len(cats[c])}) ==")
                for e in sorted(cats[c], key=lambda e: -e["puntos"]):
                    marca = "" if e["estado"] == "activa" else "  [retirada]"
                    lineas.append(f"  \"{e['texto']}\"{marca}")
                lineas.append("")
        lineas += resumen_monstruos(self)
        lineas += self.resp.resumen(lambda k: "Tu" if k == "yo" else self.jugadores.get(k, k))
        if not self.simular:
            with open(os.path.join(self.bib, "resumen.txt"), "w", encoding="utf-8") as fh:
                fh.write("\n".join(lineas))
        return totales


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--simular", action="store_true", help="analiza pero no mueve ni borra nada")
    ap.add_argument("--recalibrar", action="store_true",
                    help="vuelve a transcribir y clasificar las frases guardadas con el modelo actual")
    ap.add_argument("--config", default=os.path.join(AQUI, "config.json"))
    args = ap.parse_args()
    with open(args.config, encoding="utf-8") as f:
        cfg = json.load(f)
    if not os.path.isdir(cfg["carpeta_juego"]):
        sys.exit(f"No encuentro el juego en {cfg['carpeta_juego']}. Cambia 'carpeta_juego' en config.json.")

    c = Curador(cfg, args.simular)
    if args.recalibrar:
        hechas, cambiadas, movidas = c.recalibrar()
        c.preparar_efectos()
        c.resumen()
        print()
        print(f"Recalibradas: {hechas}   Texto mejorado: {cambiadas}   Cambian de tipo: {movidas}")
        return
    if args.simular:
        print("MODO SIMULACION: no se mueve ni se borra nada\n")
    importadas = c.importar()
    restauradas = c.restaurar()
    guardadas = descartadas = 0
    for fuente in c.fuentes():
        g, d = c.procesar(fuente, importadas.get(fuente.clave, ()))
        guardadas += g
        descartadas += d
    respuestas = c.respuestas_pendientes()
    retiradas = c.limitar()
    raras, limpiadas = c.voz_rara()
    efectos_nuevos, efectos_borrados = c.preparar_efectos()
    purgadas = c.purgar_descartadas()
    totales = c.resumen()

    print("\n----- Resultado -----")
    print(f"Guardadas: {guardadas}   Descartadas: {descartadas}   Restauradas: {restauradas}"
          f"   Retiradas por limite: {retiradas}   Descartadas antiguas borradas: {purgadas}")
    print(f"Respuestas cortas nuevas sacadas de frases antiguas: {respuestas}")
    print(f"Voz rara esta vez: {raras} frases (vuelven a sonar normal: {limpiadas})")
    print(f"Frases para efectos de miedo: {efectos_nuevos} nuevas, {efectos_borrados} quitadas")
    print("Biblioteca:", ", ".join(f"{k} {v}" for k, v in totales.items()) or "vacia")
    print(f"Lista completa de frases: {os.path.join(c.bib, 'resumen.txt')}")


if __name__ == "__main__":
    main()
