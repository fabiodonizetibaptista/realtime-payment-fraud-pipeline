# Instala a Confluent CLI para o usuario atual (Windows x64), sem privilegios administrativos.
# Fonte: releases oficiais github.com/confluentinc/cli; verifica o SHA-256 do release.
$ErrorActionPreference = 'Stop'

if (-not $IsWindows -and $PSVersionTable.PSEdition -eq 'Core') {
    throw 'Este instalador e exclusivo do Windows. Consulte o README para Linux/macOS.'
}
if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {
    throw 'Este instalador aceita apenas Windows AMD64. Consulte o README para outra arquitetura.'
}

$release = Invoke-RestMethod -Uri 'https://api.github.com/repos/confluentinc/cli/releases/latest' -Headers @{ 'User-Agent' = 'fraud-pipeline-bootstrap' }
$assets = @($release.assets | Where-Object { $_.name -match '^confluent_[0-9][^/]*_windows_amd64\.zip$' })
if ($assets.Count -ne 1) { throw 'Release oficial nao possui um unico ZIP Windows AMD64. Instale pela documentacao oficial.' }
$asset = $assets[0]

# A API do GitHub expõe o digest SHA-256 em release assets. Nunca instalar sem verificar integridade.
if (-not $asset.digest -or $asset.digest -notmatch '^sha256:([0-9a-fA-F]{64})$') {
    throw 'Release sem digest SHA-256 verificavel. Instalacao interrompida; consulte a pagina oficial.'
}
$expectedHash = $Matches[1].ToLowerInvariant()

$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ('confluent-cli-' + [guid]::NewGuid().ToString('N'))
$archive = Join-Path $tempRoot 'cli.zip'
$extract = Join-Path $tempRoot 'extract'
New-Item -ItemType Directory -Path $extract -Force | Out-Null
try {
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $archive
    $actualHash = (Get-FileHash -Path $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $expectedHash) { throw 'SHA-256 nao confere. Instalacao interrompida.' }
    Expand-Archive -Path $archive -DestinationPath $extract
    $executables = @(Get-ChildItem $extract -Filter 'confluent.exe' -File -Recurse)
    if ($executables.Count -ne 1) { throw 'Arquivo confluent.exe ausente ou duplicado no ZIP.' }

    $installDir = Join-Path $env:LOCALAPPDATA 'Programs\ConfluentCLI'
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
    $target = Join-Path $installDir 'confluent.exe'
    Copy-Item -LiteralPath $executables[0].FullName -Destination $target -Force

    # PATH persistente do usuario e PATH desta sessao, sem exigir reinicializacao.
    $existingUserPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $entryList = @($existingUserPath -split ';' | Where-Object { $_ })
    if ($entryList -notcontains $installDir) {
        $entryList += $installDir
        [Environment]::SetEnvironmentVariable('Path', ($entryList -join ';'), 'User')
    }
    if (($env:Path -split ';') -notcontains $installDir) { $env:Path = "$installDir;$env:Path" }
    Write-Host "CONFLUENT_CLI_INSTALLED=$target"
    & $target version
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao executar a CLI instalada.' }
}
finally {
    if (Test-Path $tempRoot) { Remove-Item $tempRoot -Recurse -Force }
}
