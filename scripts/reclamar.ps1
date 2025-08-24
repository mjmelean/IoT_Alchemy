param(
    [string]$serial_number,
    [string]$nombre,
    [string]$tipo,
    [string]$modelo,
    [string]$descripcion,
    [string]$configuracion
)

# Construir el body como hashtable
$body = @{
    serial_number = $serial_number
    nombre = $nombre
    tipo = $tipo
    modelo = $modelo
    descripcion = $descripcion
    configuracion = (ConvertFrom-Json $configuracion)
}

# Convertir a JSON
$json = $body | ConvertTo-Json -Depth 5 -Compress

Write-Host "Enviando payload al backend..."
Write-Host $json

# Ejecutar POST con Invoke-RestMethod
try {
    $response = Invoke-RestMethod -Uri "http://localhost:5000/dispositivos/reclamar" `
                                  -Method POST `
                                  -Body $json `
                                  -ContentType 'application/json'

    Write-Host "Respuesta del backend:"
    $response | ConvertTo-Json -Depth 5
}
catch {
    Write-Host "Error al enviar request: $_"
}
