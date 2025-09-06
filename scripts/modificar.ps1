param(
    [string]$id,
    [string]$payload
)

# Cargar config.json
$configPath = Join-Path $PSScriptRoot "..\config.json"
$config = Get-Content $configPath | ConvertFrom-Json
$backendUrl = $config.backend_url.TrimEnd('/')

$url = "$backendUrl/dispositivos/$id/estado"

Write-Host "🔧 Modificando dispositivo con ID: $id"
Write-Host "🌍 Usando backend: $backendUrl"

try {
    $response = Invoke-RestMethod -Uri $url `
                                  -Method Put `
                                  -Body $payload `
                                  -ContentType "application/json; charset=utf-8"

    Write-Host "📡 Respuesta del servidor:"
    $response | ConvertTo-Json -Depth 5
}
catch {
    Write-Host "❌ Error al modificar dispositivo: $_"
}
