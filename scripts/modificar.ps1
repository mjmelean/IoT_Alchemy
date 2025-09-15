param(
    [Parameter(Mandatory=$true)][string]$id,
    [Parameter(Mandatory=$true)][string]$payload
)

# Cargar config.json (igual que reclamar.ps1)
$scriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$configPath = Join-Path $scriptDir "..\config.json"
$config     = Get-Content $configPath | ConvertFrom-Json
$backendUrl = $config.backend_url.TrimEnd('/')

# Endpoint único (parciales / mode-aware)
$url = "$backendUrl/dispositivos/$id"

Write-Host "🔧 Modificando dispositivo con ID: $id"
Write-Host "🌍 Endpoint: $url"
Write-Host "📤 Payload:"
Write-Host $payload

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
