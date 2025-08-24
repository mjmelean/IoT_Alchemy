param(
    [string]$id,
    [string]$payload
)

Write-Host "🔧 Modificando dispositivo con ID: $id"

try {
    $url = "http://localhost:5000/dispositivos/$id/estado"

    $response = curl -Uri $url `
                     -Method Put `
                     -Body $payload `
                     -ContentType "application/json"

    Write-Host "📡 Respuesta del servidor:"
    Write-Host $response
}
catch {
    Write-Host "❌ Error al modificar dispositivo: $_"
}
