param(
  [string]$RepoPath = "C:\govy\repos\govy-function-current",
  [string]$WorkBranch = "dev"
)

Set-Location $RepoPath
Write-Host "Repo: $RepoPath" -ForegroundColor Cyan

git checkout main | Out-Null
git pull --rebase origin main

git checkout $WorkBranch 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host "Criando branch $WorkBranch..." -ForegroundColor Yellow
  git checkout -b $WorkBranch
} else {
  Write-Host "Branch $WorkBranch encontrada." -ForegroundColor Green
}

git pull --rebase origin $WorkBranch 2>$null

$activate = Join-Path $RepoPath ".venv\Scripts\Activate.ps1"
if (Test-Path $activate) {
  . $activate
  Write-Host "venv ativado (.venv)" -ForegroundColor Green
} else {
  Write-Host ".venv não encontrado. Crie com: py -3.11 -m venv .venv" -ForegroundColor Yellow
}

Write-Host ("Pronto. Branch atual: " + (git branch --show-current)) -ForegroundColor Green
