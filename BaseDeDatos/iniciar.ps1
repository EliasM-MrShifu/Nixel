$ErrorActionPreference = "Stop"

$raizProyecto = Split-Path -Parent $PSScriptRoot
$pythonVirtual = Join-Path $raizProyecto ".venv\Scripts\python.exe"

if (Test-Path -LiteralPath $pythonVirtual) {
    $python = $pythonVirtual
} else {
    $pythonComando = Get-Command python.exe -ErrorAction Stop
    $python = $pythonComando.Source
}

$configuracionLocal = Join-Path $env:LOCALAPPDATA "Nexo"
$clavePrivada = Join-Path $configuracionLocal "vapid_private.pem"
$clavePublica = Join-Path $configuracionLocal "vapid_public.txt"
$correoVapid = Join-Path $configuracionLocal "vapid_claims_email.txt"
if ((Test-Path -LiteralPath $clavePrivada) -and (Test-Path -LiteralPath $clavePublica)) {
    $env:VAPID_PRIVATE_KEY_PATH = $clavePrivada
    $env:VAPID_PUBLIC_KEY = (Get-Content -LiteralPath $clavePublica -Raw).Trim()
}
if (Test-Path -LiteralPath $correoVapid) {
    $env:VAPID_CLAIMS_EMAIL = (Get-Content -LiteralPath $correoVapid -Raw).Trim()
}
$githubConfig = Join-Path $configuracionLocal "github_oauth.json"
if (Test-Path -LiteralPath $githubConfig) {
    $github = Get-Content -LiteralPath $githubConfig -Raw | ConvertFrom-Json
    if ([string]::IsNullOrWhiteSpace($github.client_id) -or [string]::IsNullOrWhiteSpace($github.client_secret)) {
        throw "La configuración OAuth local de GitHub está incompleta: $githubConfig"
    }
    $env:GITHUB_CLIENT_ID = $github.client_id
    $env:GITHUB_CLIENT_SECRET = $github.client_secret
    $env:GITHUB_REDIRECT_URI = "http://127.0.0.1:5000/api/github/callback"
}

Write-Host "Iniciando la API y conectando con MySQL (base aplicacion)..."
& $python (Join-Path $PSScriptRoot "api.py")
exit $LASTEXITCODE
