# scripts/end.ps1
param(
  [string]$RepoPath = "C:\govy\repos\govy-function-current",
  [string]$Message = ""
)

Set-Location $RepoPath

# Se não houver mudanças, não tenta commitar
$changes = git status --porcelain
if (-not $changes) {
  Write-Host "✅ Nada para commitar. Repo limpo." -ForegroundColor Green
  exit 0
}

if ([string]::IsNullOrWhiteSpace($Message)) {
  $Message = "wip: sync"
}

git add .
git commit -m $Message
git push

Write-Host "✅ Commit + push feitos: $Message" -ForegroundColor Green
