param(
    [Parameter(Mandatory=$true)][string]$id,
    [Parameter(Mandatory=$true)][string]$payloadPath
)

# --- Cargar config.json ---
$scriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$configPath = Join-Path $scriptDir "..\config.json"

if (-not (Test-Path -LiteralPath $configPath)) {
    Write-Host "❌ No se encontró config.json en $configPath" -ForegroundColor Red
    exit 1
}
$configRaw = Get-Content -LiteralPath $configPath -Raw
$config    = $configRaw | ConvertFrom-Json
$backendUrl = "$($config.backend_url)".TrimEnd('/')

# --- Leer payload desde archivo ---
if (-not (Test-Path -LiteralPath $payloadPath)) {
    Write-Host "❌ No existe el archivo de payload: $payloadPath" -ForegroundColor Red
    exit 1
}
$payloadJson = Get-Content -LiteralPath $payloadPath -Raw

# Validación rápida del JSON
try {
    $null = $payloadJson | ConvertFrom-Json
} catch {
    Write-Host "❌ El payload NO es un JSON válido. Revisa comillas/comas." -ForegroundColor Red
    exit 1
}

# --- Endpoint absoluto ---
$url = "$backendUrl/dispositivos/$id"
Write-Host "🔧 Modificando dispositivo con ID: $id"
Write-Host "🌍 Endpoint: $url"
Write-Host "📤 Payload:"
Write-Host $payloadJson

# --- Envío ---
try {
    $response = Invoke-RestMethod -Uri $url `
                                  -Method Put `
                                  -Body $payloadJson `
                                  -ContentType "application/json; charset=utf-8"
    Write-Host "✅ Respuesta del servidor:"
    $response | ConvertTo-Json -Depth 10
}
catch {
    Write-Host "❌ Error al modificar dispositivo: $_" -ForegroundColor Red
    exit 1
}