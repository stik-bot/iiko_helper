$python = "$env:LocalAppData\Programs\Python\Python312\python.exe"

if (-not (Test-Path $python)) {
    Write-Error "Python 3.12 not found at $python"
    exit 1
}

Set-Location $PSScriptRoot
Remove-Item Env:HTTP_PROXY -ErrorAction SilentlyContinue
Remove-Item Env:HTTPS_PROXY -ErrorAction SilentlyContinue
Remove-Item Env:ALL_PROXY -ErrorAction SilentlyContinue
Remove-Item Env:http_proxy -ErrorAction SilentlyContinue
Remove-Item Env:https_proxy -ErrorAction SilentlyContinue
Remove-Item Env:all_proxy -ErrorAction SilentlyContinue
& $python main.py
