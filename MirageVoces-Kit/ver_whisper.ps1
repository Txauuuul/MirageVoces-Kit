# Ver Whisper en vivo: muestra lo que entiende Whisper mientras jugais, y lo que hace el mod (respuestas,
# sustos, invocaciones). Solo lee archivos de texto: no afecta al rendimiento del juego.
# Se abre con "Ver Whisper en vivo.bat". Ciérralo cuando quieras.

param([string]$vivo = "")
if (-not $vivo) {
    $cfg = Get-Content (Join-Path $PSScriptRoot "config.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    $vivo = Join-Path $cfg.carpeta_juego "Mirage\Centralizado\Vivo"
}
$resultados = Join-Path $vivo "resultados.jsonl"
$eventos = Join-Path $vivo "eventos.jsonl"

$Host.UI.RawUI.WindowTitle = "Whisper en vivo - MirageVoces"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Write-Host "Whisper en vivo  (blanco = se guarda, gris = se descarta, amarillo = cosas del mod)" -ForegroundColor Cyan
Write-Host "Esperando a que empiece la partida...`n" -ForegroundColor DarkGray

$textos = @{
    "respuesta" = "le contesta algo con la voz de"; "solo" = "esta solo y oye a"; "muerte" = "MUERE"
    "invocacion" = "invoca"; "ultimas" = "ultimas palabras de"; "altavoz" = "altavoz de la nave:"
    "bracken" = "Bracken:"; "bracken_enfado" = "el Bracken se enfada"; "luna" = "aterrizais en"
    "imita" = "un monstruo imita a"; "cadaver" = "susurra el cadaver de"; "walkie" = "walkie falso con la voz de"
    "puerta" = "voz tras una puerta:"; "despegue" = "despegais:"
}

$monstruos = @{ "Flowerman" = "Bracken"; "Crawler" = "Thumper"; "Spring" = "Coil-head"; "Blob" = "Hygrodere";
    "Centipede" = "Snare flea"; "MouthDog" = "perro sin ojos"; "ForestGiant" = "gigante"; "Masked" = "enmascarado";
    "Girl" = "nina fantasma"; "Puffer" = "Spore lizard"; "Jester" = "Jester"; "Hoarding bug" = "Hoarding bug" }

$pos = @{ $resultados = 0L; $eventos = 0L }
# Empieza por el final: solo lo nuevo (si el archivo se vacia, es que ha empezado otra partida).
foreach ($f in @($resultados, $eventos)) { if (Test-Path $f) { $pos[$f] = (Get-Item $f).Length } }

function Leer($archivo) {
    if (-not (Test-Path $archivo)) { return @() }
    $largo = (Get-Item $archivo).Length
    if ($largo -lt $pos[$archivo]) { $pos[$archivo] = 0L; Write-Host "`n--- partida nueva ---`n" -ForegroundColor Cyan }
    if ($largo -eq $pos[$archivo]) { return @() }
    $fs = [System.IO.File]::Open($archivo, 'Open', 'Read', 'ReadWrite, Delete')
    try {
        $fs.Seek($pos[$archivo], 'Begin') | Out-Null
        $buf = New-Object byte[] ($largo - $pos[$archivo])
        $n = $fs.Read($buf, 0, $buf.Length)
    } finally { $fs.Close() }
    $texto = [System.Text.Encoding]::UTF8.GetString($buf, 0, $n)
    $fin = $texto.LastIndexOf("`n")
    if ($fin -lt 0) { return @() }   # linea a medio escribir: la proxima vez
    $pos[$archivo] += [System.Text.Encoding]::UTF8.GetByteCount($texto.Substring(0, $fin + 1))
    return $texto.Substring(0, $fin).Split("`n") | Where-Object { $_.Trim() }
}

while ($true) {
    foreach ($l in Leer $resultados) {
        try { $x = $l.TrimStart([char]0xFEFF) | ConvertFrom-Json } catch { continue }
        if (-not $x.texto) { continue }
        $hora = (Get-Date "1970-01-01").AddSeconds($x.t).ToLocalTime().ToString("HH:mm:ss")
        $quien = if ($x.jugador -eq "Tu") { "Tu" } else { $x.jugador }
        $texto = if ($x.texto.Length -gt 140) { $x.texto.Substring(0, 140) + "..." } else { $x.texto }
        Write-Host "$hora " -NoNewline -ForegroundColor DarkGray
        Write-Host "$($quien): " -NoNewline -ForegroundColor Green
        Write-Host $texto -ForegroundColor $(if ($x.guardada) { "White" } else { "DarkGray" })
        if ($x.respuestas) {
            $r = $x.respuestas[0]
            Write-Host "           (si toca, contestaria $($r.voz): `"$($r.texto)`")" -ForegroundColor DarkCyan
        }
    }
    foreach ($l in Leer $eventos) {
        try { $e = $l.TrimStart([char]0xFEFF) | ConvertFrom-Json } catch { continue }
        if ($e.tipo -eq "bracken") { continue }  # demasiadas: solo cuando se enfada
        $hora = (Get-Date "1970-01-01").AddSeconds($e.t).ToLocalTime().ToString("HH:mm:ss")
        $que = $textos[$e.tipo]; if (-not $que) { $que = $e.tipo }
        $partes = @($e.otro, $que, $e.jugador, $e.detalle) | Where-Object { $_ }
        if ($e.tipo -eq "respuesta") { $partes = @($e.otro, $que, $e.jugador) | Where-Object { $_ } }
        if ($e.tipo -eq "solo") { $partes = @($e.jugador, $que, $e.otro) | Where-Object { $_ } }
        $bicho = $monstruos[[string]$e.otro]; if (-not $bicho) { $bicho = $e.otro }
        if ($e.tipo -eq "muerte") { $partes = @("MUERE", $e.jugador, $(if ($bicho) { "($bicho)" } else { "($($e.detalle))" })) }
        if ($e.tipo -eq "invocacion") {
            $m = $monstruos[[string]$e.detalle]; if (-not $m) { $m = $e.detalle }
            $partes = @($e.jugador, "invoca:", $m)
        }
        Write-Host "$hora " -NoNewline -ForegroundColor DarkGray
        Write-Host ("  >> " + ($partes -join " ")) -ForegroundColor $(if ($e.tipo -eq "muerte") { "Red" } else { "Yellow" })
    }
    Start-Sleep -Milliseconds 700
}
