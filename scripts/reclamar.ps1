param(
    [string]$serial_number,
    [string]$nombre,
    [string]$tipo,
    [string]$modelo,
    [string]$descripcion,
    [string]$configuracion
)

# Cargar config.json
$configPath = Join-Path $PSScriptRoot "..\config.json"
$config = Get-Content $configPath | ConvertFrom-Json
$backendUrl = $config.backend_url.TrimEnd('/')

# Construir el body como hashtable
$body = @{
    serial_number = $serial_number
    nombre        = $nombre
    tipo          = $tipo
    modelo        = $modelo
    descripcion   = $descripcion
    configuracion = (ConvertFrom-Json $configuracion)
}

# Convertir a JSON
$json = $body | ConvertTo-Json -Depth 5 -Compress

Write-Host "📤 Enviando payload al backend..."
Write-Host $json
Write-Host "🌍 Usando backend: $backendUrl"

# Ejecutar POST
try {
    $response = Invoke-RestMethod -Uri "$backendUrl/dispositivos/reclamar" `
                                  -Method POST `
                                  -Body $json `
                                  -ContentType 'application/json; charset=utf-8'

    Write-Host "✅ Respuesta del backend:"
    $response | ConvertTo-Json -Depth 5
}
catch {
    Write-Host "❌ Error al enviar request: $_"
}
