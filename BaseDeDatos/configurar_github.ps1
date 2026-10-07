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

    $ruta = Join-Path $configuracionLocal "github_oauth.json"
    $tokenKey = $null
    if (Test-Path -LiteralPath $ruta) {
        $configuracionExistente = Get-Content -LiteralPath $ruta -Raw | ConvertFrom-Json
        $tokenKey = $configuracionExistente.token_encryption_key
    }
    if ([string]::IsNullOrWhiteSpace($tokenKey)) {
        $keyBytes = [byte[]]::new(32)
        $random = [Security.Cryptography.RandomNumberGenerator]::Create()
        try {
            $random.GetBytes($keyBytes)
        }
        finally {
            $random.Dispose()
        }
        $tokenKey = [Convert]::ToBase64String($keyBytes).Replace('+', '-').Replace('/', '_')
        [Array]::Clear($keyBytes, 0, $keyBytes.Length)
    }
    $configuracion = @{
        client_id = $clientId
        client_secret = $clientSecret
        token_encryption_key = $tokenKey
    } | ConvertTo-Json
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
