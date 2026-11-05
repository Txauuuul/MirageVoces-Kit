using System;
using System.Diagnostics;
using System.IO;
using BepInEx;

namespace MirageVoces.Anfitrion
{
    /// <summary>
    /// Plugin aparte, solo para el PC del anfitrion: arranca mirage_vivo.py (Whisper en vivo) cuando
    /// MirageVoces lo pide y le avisa al salir. No se sube a Thunderstore: el resto de jugadores no lo necesita.
    /// </summary>
    [BepInPlugin("lloreria.miragevoces.anfitrion", "MirageVoces Anfitrion", "1.1.0")]
    [BepInDependency("lloreria.miragevoces")]
    public class Anfitrion : BaseUnityPlugin
    {
        private static Process server;
        private static string vivoDir;

        private void Awake()
        {
            HostBridge.Start = Start;
            HostBridge.IsRunning = () => server != null && !server.HasExited;
            HostBridge.Stop = Stop;
            Logger.LogInfo("Listo: arrancara Whisper en vivo cuando hagas de anfitrion.");
        }

        private static void Start(string python, string script, string vivo)
        {
            vivoDir = vivo;
            var logPath = Path.Combine(vivo, "servidor.log");
            File.WriteAllText(logPath, $"--- {DateTime.Now} ---\n");
            // El registro lo escribe el propio servidor: si el juego se cierra, sigue hasta guardar la sesion
            // y hacer el resumen de la noche.
            var psi = new ProcessStartInfo(python, $"-u \"{script}\" --latido 30 --log \"{logPath}\"")
            {
                WorkingDirectory = Path.GetDirectoryName(script),
                UseShellExecute = false,
                CreateNoWindow = true,
            };
            psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
            server = Process.Start(psi);
        }

        /// <summary>Al cerrar el juego: le pide que guarde y se cierre solo. No se le corta: tarda unos segundos
        /// en hacer el resumen de la noche, y si se cuelga se cierra igual al dejar de recibir el latido.</summary>
        private static void Stop()
        {
            if (server == null || server.HasExited) return;
            try { File.WriteAllText(Path.Combine(vivoDir, "parar.txt"), "1"); } catch { }
        }
    }
}
