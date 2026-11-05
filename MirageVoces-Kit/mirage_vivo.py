"""Mirage Voces en vivo: cura las frases mientras jugais y le cuenta al mod lo que se dice.

Lo arranca solo el mod MirageVoces cuando haces de anfitrion (no hace falta abrirlo a mano):
  1. Al empezar hace lo mismo que Ejecutar.bat (importar, restaurar, sortear la voz rara...).
  2. Despues vigila las grabaciones nuevas (las tuyas de Mirage y las de tus amigos que guarda
     el mod), las pasa por Whisper en cuanto alguien termina de hablar y las deja listas para
     usarlas en la misma partida.
  3. Escribe cada frase entendida en Mirage/Centralizado/Vivo/resultados.jsonl; el mod lo lee
     para responder preguntas, las palabras prohibidas y el Signal Translator.
  4. Se cierra solo cuando el juego deja de dar senales de vida (latido.txt).

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
    c.respuestas_pendientes()
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
            for fuente in list(c.fuentes()):
                # Se procesan en cuanto estan completas (ver Curador._terminado); 'espera' es solo por si acaso.
                espera = 3 if fuente.clave == "yo" else 1
                for f in c.pendientes(fuente, espera=espera):
                    try:
                        mtime = os.path.getmtime(os.path.join(fuente.origen, f))
                    except OSError:
                        continue
                    (nuevas if mtime >= inicio_sesion - 5 else atrasadas).append((mtime, fuente, f))
            if nuevas:
                tanda = sorted(nuevas, key=lambda x: -x[0])
            else:
                tanda = sorted(atrasadas, key=lambda x: -x[0])[:1]
            for mtime, fuente, f in tanda:
                if mtime < inicio_sesion - 5:
                    if c.procesar_archivo(fuente, f, "[atrasada] ") is not None:
                        trabajo = True
                        cambios = True
                    continue
                t0 = time.time()
                copia = os.path.join(sesion, f"{fuente.clave}_{os.path.splitext(f)[0]}.opus")
                fin_habla = os.path.getmtime(os.path.join(fuente.origen, f))  # el archivo se cierra al acabar de hablar
                vol = volumen(os.path.join(fuente.origen, f))
                if subprocess.run(["ffmpeg", "-y", "-loglevel", "fatal", "-i", os.path.join(fuente.origen, f), "-ac", "1",
                                   "-c:a", "libopus", "-b:a", "16k", "-f", "ogg", copia]).returncode != 0:
                    copia = None
                e = c.procesar_archivo(fuente, f, "[vivo] ")
                if e is None:
                    continue
                trabajo = True
                linea = {"clave": fuente.clave, "jugador": fuente.jugador, "texto": e["texto"],
                         "categorias": e.get("categorias", []), "guardada": e["estado"] == "activa",
                         "activa": e.get("activa"), "audio": copia, "dur": e.get("duracion"),
                         "inicio": fin_habla - (e.get("duracion") or 0), "vol_media": vol[0], "vol_pico": vol[1],
                         "t": time.time(), "ms": int((time.time() - t0) * 1000)}
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
