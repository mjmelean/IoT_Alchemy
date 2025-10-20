param(
    [Parameter(Mandatory = $true)]
    [string]$payloadPath
)

# Cargar config.json
$configPath = Join-Path $PSScriptRoot "..\config.json"
$config     = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$backendUrl = $config.backend_url.TrimEnd('/')

# Leer payload desde archivo
if (-not (Test-Path -LiteralPath $payloadPath)) {
    Write-Host "❌ No existe el archivo de payload: $payloadPath" -ForegroundColor Red
    exit 1
}
$payloadJson = Get-Content -LiteralPath $payloadPath -Raw

Write-Host "📤 Enviando payload al backend..."
Write-Host $payloadJson
Write-Host "🌍 Usando backend: $backendUrl"

try {
    $response = Invoke-RestMethod -Uri "$backendUrl/dispositivos/reclamar" `
                                  -Method POST `
                                  -Body $payloadJson `
                                  -ContentType 'application/json; charset=utf-8'
    Write-Host "✅ Respuesta del backend:"
    $response | ConvertTo-Json -Depth 10
}
catch {
    Write-Host "❌ Error al enviar request: $_" -ForegroundColor Red
    exit 1
}