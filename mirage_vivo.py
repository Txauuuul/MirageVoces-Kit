"""Mirage Voces en vivo: cura las frases mientras jugais y le cuenta al mod lo que se dice.

Lo arranca solo el mod MirageVoces cuando haces de anfitrion (no hace falta abrirlo a mano):
  1. Al empezar hace lo mismo que Ejecutar.bat (importar, restaurar, sortear la voz rara...).
  2. Despues vigila las grabaciones nuevas (las tuyas de Mirage y las de tus amigos que guarda
     el mod), las pasa por Whisper en cuanto alguien termina de hablar y las deja listas para
     usarlas en la misma partida.
  3. Escribe cada frase entendida en Mirage/Centralizado/Vivo/resultados.jsonl; el mod lo lee
     para responder preguntas, las palabras prohibidas y el Signal Translator.
  4. Se cierra solo cuando el juego deja de dar senales de vida (latido.txt).
  5. Solo escucha lo que puede hacer reaccionar al mod: lo que dice la gente viva en una luna. Lo que se dice en
     la nave (entre lunas) o estando muerto se tira sin pasar por Whisper (asi no se satura con mucha gente).

Uso manual (para probar):  python mirage_vivo.py [--config ruta] [--sin-latido]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

from dialogo import Repertorio
from mirage_voces import AQUI, Curador, normalizar
from resumen_noche import generar as generar_resumen


class Fase:
    """Cuando sirve escuchar: en una luna (desde que aterriza hasta que despega) y a quien sigue vivo, que es cuando
    el mod puede reaccionar. Lo sabe por el diario que escribe el mod (eventos.jsonl: luna, despegue, muerte)."""
    GRACIA_MUERTE = 6     # lo que se graba justo al morir (el grito) aun cuenta: sale en el resumen
    GRACIA_DESPEGUE = 3

    def __init__(self, ruta):
        self.ruta, self.pos, self.resto = ruta, 0, b""
        self.lunas = []    # [aterriza, despega o None]
        self.muertes = []  # (t, nombre normalizado)

    def leer(self):
        try:
            tam = os.path.getsize(self.ruta)
        except OSError:
            return
        if tam < self.pos:  # archivo nuevo
            self.__init__(self.ruta)
        if tam == self.pos:
            return
        with open(self.ruta, "rb") as f:
            f.seek(self.pos)
            datos = f.read()
        self.pos += len(datos)
        *lineas, self.resto = (self.resto + datos).split(b"\n")
        for linea in lineas:
            try:
                e = json.loads(linea.decode("utf-8-sig", errors="replace"))
            except ValueError:
                continue
            tipo, t = e.get("tipo"), e.get("t", 0)
            if tipo == "luna":
                if self.lunas and self.lunas[-1][1] is None:
                    self.lunas[-1][1] = t
                self.lunas.append([t, None])
            elif tipo == "despegue" and self.lunas and self.lunas[-1][1] is None:
                self.lunas[-1][1] = t
            elif tipo == "muerte" and e.get("jugador"):
                self.muertes.append((t, normalizar(e["jugador"])))

    def sirve(self, t, jugador):
        """(True, "") si lo dicho en el momento t por 'jugador' puede hacer reaccionar al mod; si no, (False, motivo)."""
        luna = next((l for l in reversed(self.lunas) if l[0] <= t), None)
        if luna is None or (luna[1] is not None and t > luna[1] + self.GRACIA_DESPEGUE):
            return False, "nave"
        j = normalizar(jugador or "")
        if any(mj == j and luna[0] <= mt and mt + self.GRACIA_MUERTE < t for mt, mj in self.muertes):
            return False, "muerto"
        return True, ""


def pistas(ruta):
    """(duracion, volumen medio, medio segundo mas fuerte) sin pasar por Whisper: para elegir que escuchar."""
    import numpy as np
    from respuestas import cargar_audio
    audio = cargar_audio(ruta, 16000)
    dur = len(audio) / 16000
    if len(audio) < 1600:
        return dur, None, None
    db = lambda x: float(20 * np.log10(max(np.sqrt(np.mean(x ** 2)), 1e-6)))
    ventana = 8000  # 0,5 s
    trozos = [audio[i:i + ventana] for i in range(0, max(1, len(audio) - ventana + 1), ventana // 2)]
    return dur, round(db(audio), 1), round(max(db(t) for t in trozos), 1)


def importancia(dur, media, pico):
    """Lo que mas interesa entender a tiempo: gritos y frases cortas (preguntas, llamadas, avisos).
    Un rollo largo casi nunca hace reaccionar a nadie."""
    p = 0
    if pico is not None and (pico - media >= 8 or pico > -12):
        p += 3  # grito: mucho mas fuerte que el resto de la frase, o muy fuerte
    if 0.6 <= dur <= 4:
        p += 2
    elif dur <= 8:
        p += 1
    else:
        p -= 2
    return p


def repartir(nuevas, apartadas, datos_de, saturado, max_retraso, ahora):
    """Elige la siguiente frase de 'nuevas' [(mtime, fuente, f)]. Sin retraso, la mas nueva. Con retraso, de cada
    persona solo su frase mas importante (lo demas que tenga pendiente va a 'apartadas' y se tira), y de esas la mas nueva:
    asi se escucha un poco a todos en vez de todo de uno."""
    if not saturado:
        return max(nuevas, key=lambda x: x[0])
    por_persona = {}
    for x in nuevas:
        por_persona.setdefault(x[1].clave, []).append(x)
    elegidas = []
    for xs in por_persona.values():
        frescas = [x for x in xs if ahora - x[0] <= max_retraso] or xs
        mejor = max(frescas, key=lambda x: (importancia(*datos_de(x)), x[0]))
        elegidas.append(mejor)
        apartadas.update((x[1].clave, x[2]) for x in xs if x is not mejor)
    return max(elegidas, key=lambda x: x[0])


def volumen(ruta):
    """(volumen medio, medio segundo mas fuerte) en dB. Un grito suena mucho mas fuerte que lo normal en esa
    persona, aunque vaya dentro de una frase larga ("bueno pues... ¡AAAH!")."""
    import numpy as np
    from respuestas import cargar_audio
    audio = cargar_audio(ruta, 16000)
    if len(audio) < 1600:
        return None, None
    db = lambda x: float(20 * np.log10(max(np.sqrt(np.mean(x ** 2)), 1e-6)))
    ventana = 8000  # 0,5 s
    trozos = [audio[i:i + ventana] for i in range(0, max(1, len(audio) - ventana + 1), ventana // 2)]
    return round(db(audio), 1), round(max(db(t) for t in trozos), 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=os.path.join(AQUI, "config.json"))
    ap.add_argument("--latido", type=float, default=30, help="segundos sin latido del juego antes de cerrarse")
    ap.add_argument("--sin-latido", action="store_true", help="no esperar al juego (pruebas)")
    ap.add_argument("--log", help="escribir el registro en este archivo (asi sigue aunque el juego ya se haya cerrado)")
    args = ap.parse_args()
    # El juego lo arranca sin ventana: entonces Python no tiene donde escribir (sys.stdout es None) y cualquier
    # print lo tumbaria. Todo va al archivo de registro.
    if args.log:
        registro = open(args.log, "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = registro
    elif sys.stdout is None:
        sys.stdout = sys.stderr = open(os.devnull, "w", encoding="utf-8")
    else:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    with open(args.config, encoding="utf-8") as f:
        cfg = json.load(f)

    c = Curador(cfg, simular=False)
    c.en_vivo = True
    vivo = os.path.join(c.central, "Vivo")
    os.makedirs(vivo, exist_ok=True)
    ruta_resultados = os.path.join(vivo, "resultados.jsonl")
    ruta_latido = os.path.join(vivo, "latido.txt")

    # Inicio de sesion: lo mismo que Ejecutar.bat, para no tener que acordarse.
    importadas = c.importar()
    c.restaurar()
    # Solo los audios importados ahora; las grabaciones atrasadas se curan durante la partida, en los ratos libres
    # (si se hiciera aqui, con cientos atrasadas el mod tardaria minutos en empezar a entender lo que decis).
    for fuente in c.fuentes():
        for f in sorted(importadas.get(fuente.clave, ())):
            c.procesar_archivo(fuente, f)
    c._guardar_indice()
    c.limitar()
    c.voz_rara()
    c.preparar_efectos()
    c.purgar_descartadas()
    c.resumen()
    c._whisper()  # cargar el modelo ya, para que la primera frase no tarde

    repertorio = Repertorio(c, normalizar)
    mi_nombre = cfg.get("mi_nombre_steam", "Tu")
    nombre_de_clave = lambda k: mi_nombre if k == "yo" else c.jugadores.get(k)
    presentes_ahora = [mi_nombre]
    inicio_sesion = time.time()
    with open(os.path.join(vivo, "estado.json"), "w", encoding="utf-8") as f:
        json.dump({"pid": os.getpid(), "dispositivo": c.dispositivo, "inicio": inicio_sesion}, f)
    print(f"En vivo ({'grafica' if c.dispositivo == 'cuda' else 'procesador'}). Esperando frases...")

    # Cada sesion empieza con el archivo vacio; el mod lo detecta y vuelve a leer desde el principio.
    salida = open(ruta_resultados, "w", encoding="utf-8")
    # Lo que se entiende demasiado tarde para reaccionar va aparte: el mod no lo lee, el resumen de la noche si.
    tarde = open(os.path.join(vivo, "tarde.jsonl"), "w", encoding="utf-8")
    max_retraso = cfg.get("retraso_max_vivo", 20)
    # Con este retraso (o esta cola) se empieza a escuchar solo lo importante de cada uno.
    retraso_saturado = cfg.get("retraso_saturado_vivo", 6)
    # Solo se escucha a la gente viva en una luna (con --sin-latido, para pruebas, se escucha todo).
    fase = Fase(os.path.join(vivo, "eventos.jsonl"))
    sin_escuchar = {"nave": 0, "muerto": 0}
    ultimo_aviso_fase = time.time()
    apartadas = set()  # (clave, archivo) que no se van a escuchar por ir con retraso
    tiradas = 0
    datos = {}  # ruta -> (duracion, volumen medio, pico)
    avisado = 0
    open(os.path.join(vivo, "eventos.jsonl"), "w").close()  # el diario de la noche tambien empieza vacio
    # Copia ligera de todo lo que se dice (aunque luego se descarte), para el resumen de la noche:
    # asi se oyen las preguntas, los gritos y las ultimas palabras. Se vacia en cada partida.
    sesion = os.path.join(vivo, "sesion")
    shutil.rmtree(sesion, ignore_errors=True)
    os.makedirs(sesion, exist_ok=True)
    cambios = False
    ultimo_efectos = ultimo_jugadores = time.time()
    ruta_presentes = os.path.join(vivo, "presentes.json")
    presentes_visto = None
    try:
        ruta_parar = os.path.join(vivo, "parar.txt")
        if os.path.exists(ruta_parar):
            os.remove(ruta_parar)
        while True:
            ahora = time.time()
            if os.path.exists(ruta_parar):  # el mod nos pide cerrar porque se cierra el juego
                os.remove(ruta_parar)
                print("El juego se cierra: cierro.")
                break
            if not args.sin_latido:
                try:
                    if ahora - os.path.getmtime(ruta_latido) > args.latido:
                        print("El juego ya no da senales: cierro.")
                        break
                except OSError:
                    if ahora - ultimo_jugadores > args.latido:
                        break
            if ahora - ultimo_jugadores > 10:
                c.recargar_jugadores()
                ultimo_jugadores = ahora
            # Frases que nombran a alguien que no esta jugando: fuera hasta que vuelva.
            try:
                if os.path.getmtime(ruta_presentes) != presentes_visto:
                    presentes_visto = os.path.getmtime(ruta_presentes)
                    with open(ruta_presentes, encoding="utf-8") as f:
                        presentes = json.load(f)
                    presentes_ahora = list(presentes)
                    fuera, dentro = c.aparcar_ausentes(presentes)
                    if fuera or dentro:
                        print(f"Jugando: {', '.join(presentes)} -> apartadas {fuera}, devueltas {dentro}")
                        cambios = True
            except (OSError, ValueError):
                pass

            trabajo = False
            # Primero lo que se acaba de decir (lo mas nuevo antes); lo atrasado de otras partidas, de uno en uno
            # y solo cuando no hay nada nuevo, y sin avisar al mod (no es de esta partida: no debe reaccionar).
            nuevas, atrasadas = [], []
            fase.leer()
            for fuente in list(c.fuentes()):
                # Se procesan en cuanto estan completas (ver Curador._terminado); 'espera' es solo por si acaso.
                espera = 3 if fuente.clave == "yo" else 1
                for f in c.pendientes(fuente, espera=espera):
                    try:
                        mtime = os.path.getmtime(os.path.join(fuente.origen, f))
                    except OSError:
                        continue
                    if mtime < inicio_sesion - 5:
                        atrasadas.append((mtime, fuente, f))
                        continue
                    sirve, motivo = (True, "") if args.sin_latido else fase.sirve(mtime, nombre_de_clave(fuente.clave))
                    if not sirve:  # en la nave o muerto: el mod no puede reaccionar, ni se escucha
                        try:
                            os.remove(os.path.join(fuente.origen, f))
                            sin_escuchar[motivo] += 1
                        except OSError:
                            pass
                        continue
                    nuevas.append((mtime, fuente, f))
            ahora = time.time()
            if ahora - ultimo_aviso_fase > 60 and any(sin_escuchar.values()):
                print(f"  (sin escuchar: {sin_escuchar['nave']} en la nave, {sin_escuchar['muerto']} de muertos)")
                ultimo_aviso_fase = ahora

            def datos_de(x):
                ruta = os.path.join(x[1].origen, x[2])
                if ruta not in datos:
                    try:
                        datos[ruta] = pistas(ruta)
                    except Exception:
                        datos[ruta] = (0, None, None)
                return datos[ruta]
            # De una en una: asi entre frase y frase se mira si ha llegado algo mas nuevo y si el juego sigue abierto.
            # Orden: lo de ahora; lo de otras partidas.
            if nuevas:
                saturado = len(nuevas) > 4 or ahora - min(x[0] for x in nuevas) > retraso_saturado
                tanda = [repartir(nuevas, apartadas, datos_de, saturado, max_retraso, ahora)]
                # Lo que no se escucha por ir con retraso se tira: no se mira luego.
                por_ruta = {(x[1].clave, x[2]): os.path.join(x[1].origen, x[2]) for x in nuevas}
                for k in apartadas:
                    try:
                        os.remove(por_ruta[k])
                        datos.pop(por_ruta[k], None)
                    except (OSError, KeyError):
                        pass
                tiradas += len(apartadas)
                apartadas.clear()
                if tiradas and time.time() - avisado > 30:
                    print(f"  (mucho retraso: de cada uno escucho solo lo mas importante; {tiradas} sin escuchar)")
                    avisado = time.time()
            else:
                tanda = sorted(atrasadas, key=lambda x: -x[0])[:1]
            if not tanda and any(e.get("resp", 0) < 2 for e in c.indice.values()):
                c.respuestas_pendientes(limite=1)  # rato libre: respuestas cortas de lo guardado deprisa
                trabajo = cambios = True
            for mtime, fuente, f in tanda:
                if mtime < inicio_sesion - 5:
                    if c.procesar_archivo(fuente, f, "[atrasada] ") is not None:
                        trabajo = True
                        cambios = True
                    continue
                t0 = time.time()
                # Si ya ha pasado mucho desde que se dijo, el mod no debe reaccionar (contestaria a destiempo).
                llega_tarde = t0 - mtime > max_retraso
                # Con cola, deprisa: lo importante es entender lo que se dice ahora.
                rapido = len(nuevas) > 1 or llega_tarde
                if len(nuevas) > 3:
                    print(f"  (cola: {len(nuevas)} frases, retraso {t0 - mtime:.0f} s)")
                copia = os.path.join(sesion, f"{fuente.clave}_{os.path.splitext(f)[0]}.opus")
                fin_habla = os.path.getmtime(os.path.join(fuente.origen, f))  # el archivo se cierra al acabar de hablar
                vol = datos_de((mtime, fuente, f))[1:]
                datos.pop(os.path.join(fuente.origen, f), None)
                if subprocess.run(["ffmpeg", "-y", "-loglevel", "fatal", "-i", os.path.join(fuente.origen, f), "-ac", "1",
                                   "-c:a", "libopus", "-b:a", "16k", "-f", "ogg", copia]).returncode != 0:
                    copia = None
                e = c.procesar_archivo(fuente, f, "[tarde] " if llega_tarde else "[vivo] ", rapido=rapido)
                if e is None:
                    continue
                trabajo = True
                linea = {"clave": fuente.clave, "jugador": fuente.jugador, "texto": e["texto"],
                         "categorias": e.get("categorias", []), "guardada": e["estado"] == "activa",
                         "activa": e.get("activa"), "audio": copia, "dur": e.get("duracion"),
                         "inicio": fin_habla - (e.get("duracion") or 0), "vol_media": vol[0], "vol_pico": vol[1],
                         "t": time.time(), "ms": int((time.time() - t0) * 1000),
                         "retraso": round(time.time() - fin_habla, 1)}
                if llega_tarde:
                    tarde.write(json.dumps(linea, ensure_ascii=False) + "\n")
                    tarde.flush()
                    cambios = cambios or e["estado"] == "activa"
                    continue
                # Que frase de la Biblioteca contestaria a esto (el mod elige la de alguien que no pueda contestar).
                try:
                    intent, cand = repertorio.elegir(e["texto"], nombre_de_clave(fuente.clave) or "", presentes_ahora,
                                                     nombre_de_clave)
                    if cand:
                        linea["intencion"] = intent
                        linea["respuestas"] = [{k: x[k] for k in ("voz", "wav", "opus", "texto")} for x in cand]
                        repertorio.usada(cand[0]["wav"])
                        print(f"    respuesta ({intent}): {cand[0]['voz']}: \"{cand[0]['texto']}\"")
                except Exception as ex:
                    print(f"    (no se pudo elegir respuesta: {ex})")
                salida.write(json.dumps(linea, ensure_ascii=False) + "\n")
                salida.flush()
                cambios = cambios or e["estado"] == "activa"

            # Las frases nuevas pasan a los efectos (cadaveres, walkies, puertas) cada pocos segundos.
            if cambios and time.time() - ultimo_efectos > 5:
                c._guardar_indice()
                c.preparar_efectos()
                repertorio.recargar()  # las frases nuevas tambien pueden contestar
                cambios = False
                ultimo_efectos = time.time()
            if not trabajo:
                time.sleep(0.3)
    except KeyboardInterrupt:
        pass
    finally:
        salida.close()
        tarde.close()
        c.aparcar_ausentes(None)  # al cerrar, todo vuelve a su sitio
        c._guardar_indice()
        c.limitar()
        c.preparar_efectos()
        c.resumen()
        try:
            pagina = generar_resumen(c.base, nombres=dict(c.jugadores, Tu=cfg.get("mi_nombre_steam", "Tu")))
            if pagina:
                print(f"Resumen de la noche: {pagina}")
        except Exception as ex:  # que un fallo aqui no impida guardar la sesion
            print(f"No se pudo hacer el resumen de la noche: {ex}")
        print("Sesion guardada.")


if __name__ == "__main__":
    main()
