$ErrorActionPreference = "Stop"

$configuracionLocal = Join-Path $env:LOCALAPPDATA "Nexo"
New-Item -ItemType Directory -Path $configuracionLocal -Force | Out-Null

$clientId = (Read-Host "GitHub OAuth App Client ID").Trim()
if ([string]::IsNullOrWhiteSpace($clientId)) {
    throw "El Client ID de GitHub es obligatorio."
}

$clientSecretSecure = Read-Host "GitHub OAuth App Client Secret" -AsSecureString
$secretPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($clientSecretSecure)
try {
    $clientSecret = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($secretPtr)
    if ([string]::IsNullOrWhiteSpace($clientSecret)) {
        throw "El Client Secret de GitHub es obligatorio."
    }

    $configuracion = @{
        client_id = $clientId
        client_secret = $clientSecret
    } | ConvertTo-Json
    $ruta = Join-Path $configuracionLocal "github_oauth.json"
    [IO.File]::WriteAllText($ruta, $configuracion, [Text.UTF8Encoding]::new($false))

    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    & icacls.exe $ruta /inheritance:r /grant:r "*$($sid):F" '*S-1-5-18:F' | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudieron restringir los permisos de la configuración local."
    }
    Write-Host "Credenciales OAuth guardadas localmente con permisos restringidos."
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($secretPtr)
    $clientSecret = $null
    $clientSecretSecure.Dispose()
}
