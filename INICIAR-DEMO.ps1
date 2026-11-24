# HelpDesk TI - inicialização local sem Docker
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'

if (-not (Test-Path $python)) {
    Write-Host 'Não encontrei o ambiente .venv na pasta do projeto.' -ForegroundColor Red
    Read-Host 'Pressione Enter para sair'
    exit 1
}

$services = @(
    @{ Port = 8001; Name = 'Usuarios'; Command = "Set-Location '$root\services\users'; `$env:PYTHONPATH='$root\services\shared'; `$env:JWT_SECRET_KEY='chave-local-de-teste-com-mais-de-32-caracteres'; & '$python' -m uvicorn main:app --reload --port 8001" },
    @{ Port = 8002; Name = 'Inventario'; Command = "Set-Location '$root\services\inventory'; `$env:PYTHONPATH='$root\services\shared'; `$env:JWT_SECRET_KEY='chave-local-de-teste-com-mais-de-32-caracteres'; & '$python' -m uvicorn main:app --reload --port 8002" },
    @{ Port = 8003; Name = 'Chamados'; Command = "Set-Location '$root\services\tickets'; `$env:PYTHONPATH='$root\services\shared'; `$env:JWT_SECRET_KEY='chave-local-de-teste-com-mais-de-32-caracteres'; `$env:INVENTORY_URL='http://127.0.0.1:8002'; `$env:USERS_URL='http://127.0.0.1:8001'; & '$python' -m uvicorn main:app --reload --port 8003" },
    @{ Port = 8000; Name = 'Gateway'; Command = "Set-Location '$root\gateway'; `$env:USERS_URL='http://127.0.0.1:8001'; `$env:INVENTORY_URL='http://127.0.0.1:8002'; `$env:TICKETS_URL='http://127.0.0.1:8003'; & '$python' -m uvicorn main:app --reload --port 8000" }
)

foreach ($service in $services) {
    $listener = Get-NetTCPConnection -LocalPort $service.Port -State Listen -ErrorAction SilentlyContinue
    if (-not $listener) {
        Write-Host "Iniciando $($service.Name) na porta $($service.Port)..."
        Start-Process powershell.exe -ArgumentList @('-NoExit', '-NoProfile', '-Command', $service.Command)
    } else {
        Write-Host "$($service.Name) já está ativo na porta $($service.Port)."
    }
}

$healthUrls = @('http://127.0.0.1:8001/health', 'http://127.0.0.1:8002/health', 'http://127.0.0.1:8003/health', 'http://127.0.0.1:8000/health')
$allReady = $false
Write-Host 'Aguardando os quatro serviços...'
for ($attempt = 0; $attempt -lt 45; $attempt++) {
    $allReady = $true
    foreach ($url in $healthUrls) {
        try { Invoke-RestMethod -Uri $url -TimeoutSec 2 | Out-Null }
        catch { $allReady = $false; break }
    }
    if ($allReady) { break }
    Start-Sleep -Seconds 2
}

if (-not $allReady) {
    Write-Host 'Algum serviço não iniciou. Confira as janelas abertas.' -ForegroundColor Red
    Read-Host 'Pressione Enter para sair'
    exit 1
}

Write-Host 'Serviços ativos. Preparando os dados de demonstração...'
& $python (Join-Path $root 'demo_data.py')
if ($LASTEXITCODE -ne 0) { Read-Host 'A preparação falhou. Pressione Enter'; exit 1 }
Start-Process 'http://localhost:8000/'
Write-Host 'Pronto! O HelpDesk foi aberto no navegador.' -ForegroundColor Green
Read-Host 'Pressione Enter para fechar esta janela (os serviços continuam abertos)'
