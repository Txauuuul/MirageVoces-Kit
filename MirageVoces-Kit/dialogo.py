"""Dialogo: elige que frase de la Biblioteca contesta mejor a lo que alguien acaba de decir.

1. Cada frase guardada se etiqueta con lo que "hace" (actos): saluda, pregunta si hay alguien, dice donde esta,
   dice que viene, pide ayuda, avisa, pregunta que ha pasado, se rie... y a quien nombra.
2. Lo que se acaba de decir se entiende igual (intencion): "Hola" es un saludo, "¿Hay alguien?" busca a alguien,
   "¿Donde estas?" pregunta por un sitio, "Max" llama a alguien...
3. Para cada intencion hay una lista de actos que la contestan bien, de mejor a peor. Se puntua cada frase:
   acto que encaja, que nombre a quien hablo ("¿Ana, estas ahi?"), que sea corta y que no se haya usado hace poco.
4. Se devuelven las mejores de varias voces distintas: el mod elige la de alguien que no pueda contestar de verdad.
"""
import os
import random
import re

# ---------------------------------------------------------------- actos de cada frase
ACTOS = [
    # (acto, patrones sobre el texto normalizado)
    ("saludo", [r"\b(hola+|buenas|hey|ey|que pasa|que tal)\b"]),
    ("busca", [r"hay alguien", r"\balguien\b.*\?", r"estas? (ahi|por ahi|por aqui)", r"(sigues|seguis) ahi",
               r"me (oyes|ois|escuchas|escuchais)", r"quien (anda|esta|hay|eres)", r"donde (estas|estais|andas|andais)"]),
    ("aqui", [r"\b(estoy|estamos) (aqui|aca|por aqui|dentro|fuera|arriba|abajo|en la|en el)\b", r"^\W*(aqui|aca)\b",
              r"\baqui estoy\b", r"\bsigo aqui\b"]),
    ("sitio", [r"\b(en la|en el) (sala|habitacion|nave|entrada|salida|pasillo|puerta|escalera|ascensor|almacen)",
               r"\b(arriba|abajo|al fondo|a la (izquierda|derecha)|por (la|el) (otra|otro|puerta|pasillo|escalera))\b"]),
    ("voy", [r"\b(ya )?voy\b(?! a )",r"\bya (vamos|llego|vengo|estoy)\b", r"\bespera(me|d)?\b", r"\bun (momento|segundo)\b"]),
    ("ven", [r"\b(ven|venid|vente|venir)\b", r"\b(sigueme|seguidme)\b", r"\bpor aqui\b"]),
    ("oigo", [r"\b(te|os) (oigo|escucho)\b", r"\bse (te|os) (oye|escucha)\b"]),
    ("bien", [r"\b(estoy|estamos) bien\b", r"\btodo bien\b", r"\btranqui(lo|los)?\b"]),
    ("si", []),   # se mira aparte, con las tildes: el "si" de "si no..." no es un "si" de contestar
    ("no", [r"^\W*no\b(?! (se|me|te))"]),
    ("ayuda", [r"\b(ayuda|ayudame|ayudadme|socorro|auxilio|sacadme|sacame)\b", r"no me (dejes|dejeis)", r"no puedo salir"]),
    ("aviso", [r"\b(cuidado|cuida|corre|corred|huye|huid|atras|detras)\b", r"\b(viene|vienen|esta aqui|me sigue|me esta siguiendo)\b"]),
    ("que_pasa", [r"que (ha sido|ha pasado|pasa|es) (eso|esto)", r"que ha sido", r"que ha pasado", r"(has|habeis) oido",
                  r"que (coño|cojones) (es|ha sido)"]),
    ("miedo", [r"\b(miedo|susto|que mal rollo|no me gusta)\b", r"(estoy )?escuchando (pasos|cosas|algo)"]),
    ("risa", [r"\b(ja|je|ha){2,}", r"\bjaja"]),
    ("grito", [r"\ba{3,}h*\b", r"\bah{2,}\b", r"\bno no no\b", r"\bjoder\b", r"\bhostia\b", r"\bmadre mia\b"]),
    ("adios", [r"\b(adios|hasta luego|nos vemos)\b"]),
]
_ACTOS = [(a, [re.compile(p) for p in ps]) for a, ps in ACTOS]


def actos_de(norm, crudo=""):
    """Actos de una frase. Las preguntas sobre el sitio ("¿donde estas?") son 'busca', no 'sitio'."""
    res = {a for a, ps in _ACTOS if any(p.search(norm) for p in ps)}
    # "Si." / "Vale, vale" / "Claro": solo si la frase es corta y empieza asi (y "si" con tilde).
    bajo = crudo.lower().strip(" ¡!¿?.,")
    if len(norm.split()) <= 5 and re.match(r"(sí|vale|claro|ok|okey|venga|dale|por supuesto)\b", bajo):
        res.add("si")
    if "?" in crudo or "¿" in crudo:
        res.add("pregunta")
        if "busca" in res:
            res -= {"aqui", "sitio"}
    return res


# ---------------------------------------------------------------- que contesta a que
# intencion -> actos que la contestan, de mejor a peor (y si conviene que nombre a quien hablo)
# (Que la respuesta nombre a quien hablo -"¿Ana, estas ahi?"- siempre suma puntos; nunca es obligatorio.)
RESPUESTAS = {
    "saludo":   ["saludo", "busca", "aqui"],
    "busca":    ["aqui", "busca", "oigo", "saludo", "si"],
    "donde":    ["aqui", "sitio", "ven", "voy"],
    "oir":      ["oigo", "si", "aqui", "busca"],
    "llamada":  ["aqui", "busca", "saludo", "si", "voy"],
    "estado":   ["bien", "si", "ayuda"],
    "venir":    ["voy", "si", "ven"],
    "ayuda":    ["voy", "busca", "aviso", "ven"],
    "que_pasa": ["aviso", "miedo", "que_pasa", "grito"],
    "aviso":    ["que_pasa", "grito", "miedo", "voy"],
    "grito":    ["que_pasa", "busca", "voy"],
    "adios":    ["adios", "no", "ayuda"],
}
MAX_PALABRAS = 10   # una respuesta larga se va del tema


def intencion(norm, crudo, es_nombre):
    """Que se busca con lo que se ha dicho. es_nombre(palabra) dice si una palabra es el nombre de alguien."""
    a = actos_de(norm, crudo)
    palabras = norm.split()
    if not palabras or len(palabras) > 20:
        return None
    pregunta = "pregunta" in a
    if re.search(r"donde (\w+ ){0,2}(estas|estais|andas|andais|te has metido)", norm):
        return "donde"
    if re.search(r"(me|nos) (oyes|ois|escuchas|escuchais|copias)", norm):
        return "oir"
    if re.search(r"(estas|estais|sigues) (bien|vivos?)|te ha pasado algo|todo bien", norm) and (pregunta or len(palabras) <= 6):
        return "estado"
    if re.search(r"\b(vienes|venis|te vienes|vas a venir|me sigues)\b", norm) and (pregunta or len(palabras) <= 6):
        return "venir"
    if "que_pasa" in a:
        return "que_pasa"
    if "busca" in a:
        return "busca"
    if "ayuda" in a and len(palabras) <= 10:
        return "ayuda"
    if "grito" in a and len(palabras) <= 4:
        return "grito"
    if "aviso" in a and len(palabras) <= 6:
        return "aviso"
    resto = [w for w in palabras if not es_nombre(w)]
    relleno = {"eh", "oye", "ey", "hey", "tio", "tia", "hola", "y", "que", "a"}
    if len(resto) < len(palabras) and all(w in relleno for w in resto):
        return "llamada"            # "¿Leo?", "Max, Max", "Eh, Ana"
    if "saludo" in a and len(palabras) <= 4:
        return "saludo"
    if "adios" in a and len(palabras) <= 4:
        return "adios"
    return None


# ---------------------------------------------------------------- eleccion
class Repertorio:
    """Las frases que se pueden usar para contestar, con sus actos y a quien nombran."""

    def __init__(self, curador, normalizar):
        self.c, self.norm = curador, normalizar
        self.frases = []          # dicts: clave, texto, actos, nombra, dur, wav, opus
        self.usadas = []          # ultimas usadas (no repetir)
        self.recargar()

    def recargar(self):
        c, raiz = self.c, os.path.join(self.c.central, "Efectos")
        frases = []
        for k, e in c.indice.items():
            if e.get("estado") != "activa" or e["duracion"] > 6:
                continue
            jugador = k.split("/", 1)[0]
            wav = os.path.join(raiz, jugador, f"{e['categorias'][0]}__{os.path.splitext(os.path.basename(e['copia']))[0]}.wav")
            opus = c._abs(e["activa"])
            if not (os.path.exists(wav) and os.path.exists(opus)):
                continue
            n = self.norm(e["texto"])
            frases.append(dict(clave=jugador, texto=e["texto"], actos=actos_de(n, e["texto"]), nombra=c.mencionados(e["texto"]),
                               dur=e["duracion"], wav=wav, opus=opus))
        # Las respuestas cortas recortadas ("¡Aqui!", "Te oigo", "Vale") tambien valen.
        tipo_a_acto = {"aqui": "aqui", "oigo": "oigo", "hola": "saludo", "bien": "bien", "voy": "voy", "si": "si"}
        for clave, items in c.resp.indice.items():
            for archivo, e in items.items():
                acto = tipo_a_acto.get(e["tipo"])
                base = os.path.join(c.resp.raiz, clave, archivo)
                if acto and os.path.exists(base + ".wav") and os.path.exists(base + ".opus"):
                    frases.append(dict(clave=clave, texto=e["texto"], actos={acto}, nombra=set(), dur=1.0,
                                       wav=base + ".wav", opus=base + ".opus"))
        self.frases = frases

    def elegir(self, texto, quien_habla, presentes, nombre_de_clave, max_voces=16):
        """Candidatas para contestar a 'texto' dicho por 'quien_habla' (nombre de Steam). presentes: nombres de Steam
        en la partida. nombre_de_clave: clave de fuente ('yo' o steamId) -> nombre de Steam."""
        norm = self.norm(texto)
        es_nombre = lambda w: any(self.c.mencionados(w))
        intent = intencion(norm, texto, es_nombre)
        if intent is None:
            return None, []
        presentes_n = {self.norm(p) for p in presentes}
        nombrados = {self.norm(s) for s in self.c.mencionados(texto)}
        habla_n = self.norm(quien_habla)
        candidatas = []
        for f in self.frases:
            voz = nombre_de_clave(f["clave"])
            voz_n = self.norm(voz or "")
            if not voz or voz_n == habla_n or voz_n not in presentes_n:
                continue                       # ni el que habla ni gente que no esta jugando
            if nombrados and voz_n not in nombrados and intent in ("llamada", "donde", "oir", "estado", "venir"):
                continue                       # "¿Leo, donde estas?": contesta la voz de Leo
            nombra_n = {self.norm(s) for s in f["nombra"]}
            if nombra_n - presentes_n:
                continue                       # nunca nombrar a quien no juega
            if nombra_n and habla_n not in nombra_n:
                continue                       # que no conteste nombrando a un tercero
            if len(self.norm(f["texto"]).split()) > MAX_PALABRAS or f["dur"] > 4.5:
                continue
            mejor = next((i for i, acto in enumerate(RESPUESTAS[intent]) if acto in f["actos"]), None)
            if mejor is None:
                continue
            p = 10 - 2 * mejor
            if habla_n in nombra_n:
                p += 3                         # "¿Ana, estas ahi?" contestando a Ana: lo mas creible
            p -= max(0, f["dur"] - 3) * 0.7    # mejor cortas
            if f["wav"] in self.usadas:
                p -= 6                         # no repetir
            p += random.random() * 1.5         # un poco de variedad
            candidatas.append((p, voz, f))
        candidatas.sort(key=lambda x: -x[0])
        res, voces = [], set()
        for p, voz, f in candidatas:
            if voz in voces:
                continue                       # una por voz: el mod elige la de quien no pueda contestar
            voces.add(voz)
            res.append(dict(voz=voz, clave=f["clave"], texto=f["texto"], wav=f["wav"], opus=f["opus"], puntos=round(p, 1)))
            if len(res) >= max_voces:
                break
        return intent, res

    def usada(self, wav):
        self.usadas = (self.usadas + [wav])[-40:]
