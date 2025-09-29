param(
    [Parameter(Mandatory=$true)][string]$id,
    [Parameter(Mandatory=$true)][string]$payload
)

# --- Cargar config.json con fallback a IP LAN ---
$scriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$configPath = Join-Path $scriptDir "..\config.json"

$backendUrl = $null
if (Test-Path -LiteralPath $configPath) {
    try {
        $configRaw = Get-Content -LiteralPath $configPath -Raw
        $config    = $configRaw | ConvertFrom-Json    # <- (arreglado)
        if ($config -and $config.backend_url) {
            $backendUrl = "$($config.backend_url)".TrimEnd('/')
        }
    } catch {
        Write-Host "⚠️  No se pudo leer/parsing config.json, usando fallback LAN." -ForegroundColor DarkYellow
    }
}
if (-not $backendUrl) {
    # Fallback duro a tu IP local
    $backendUrl = "http://192.168.0.106:5000"
}
$backendUrl = $backendUrl.TrimEnd('/')

# --- Endpoint absoluto ---
$url = "$backendUrl/dispositivos/$id"

Write-Host "🔧 Modificando dispositivo con ID: $id"
Write-Host "🌍 Endpoint: $url"
Write-Host "📤 Payload (texto):"
Write-Host $payload

# --- Validación rápida del JSON antes de enviar (opcional pero útil) ---
try {
    $null = $payload | ConvertFrom-Json
} catch {
    Write-Host "❌ El payload NO es un JSON válido. Revisa comillas/comas." -ForegroundColor Red
    exit 1
}

# --- Envío ---
try {
    $response = Invoke-RestMethod -Uri $url `
                                  -Method Put `
                                  -Body $payload `
                                  -ContentType "application/json; charset=utf-8"
    Write-Host "✅ Respuesta del servidor:"
    $response | ConvertTo-Json -Depth 10
}
catch {
    Write-Host "❌ Error al modificar dispositivo: $_"
}