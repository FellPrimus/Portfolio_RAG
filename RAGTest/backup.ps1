# RAGTest Backup Script
# Creates a zip backup of the project

$date = Get-Date -Format 'yyyyMMdd_HHmmss'
$backupName = "RAGTest_backup_$date.zip"
$sourcePath = 'C:\Users\USER\Desktop\studio\RAGTest'
$backupPath = "C:\Users\USER\Desktop\studio\$backupName"

Write-Host "============================================"
Write-Host "RAGTest Backup Script"
Write-Host "============================================"
Write-Host ""
Write-Host "Source: $sourcePath"
Write-Host "Backup: $backupPath"
Write-Host ""

# Files/folders to exclude
$excludeList = @(
    '*.log',
    'nul',
    '__pycache__',
    'venv*',
    '.git',
    '.playwright-mcp',
    '*.pyc',
    '*.pyo'
)

Write-Host "Creating backup (excluding logs, cache, venv)..."

# Use Compress-Archive with exclusion
$filesToBackup = Get-ChildItem -Path $sourcePath -Recurse -File | Where-Object {
    $file = $_
    $shouldInclude = $true

    # Check against exclude patterns
    foreach ($pattern in $excludeList) {
        if ($file.Name -like $pattern) {
            $shouldInclude = $false
            break
        }
        if ($file.DirectoryName -like "*$pattern*") {
            $shouldInclude = $false
            break
        }
    }

    $shouldInclude
}

# Create temp directory
$tempDir = Join-Path $env:TEMP "ragtest_backup_temp"
if (Test-Path $tempDir) {
    Remove-Item -Path $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

# Copy files maintaining structure
foreach ($file in $filesToBackup) {
    $relativePath = $file.FullName.Substring($sourcePath.Length + 1)
    $destPath = Join-Path $tempDir $relativePath
    $destDir = Split-Path $destPath -Parent

    if (-not (Test-Path $destDir)) {
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    }

    Copy-Item $file.FullName $destPath -Force
}

# Create zip archive
Compress-Archive -Path "$tempDir\*" -DestinationPath $backupPath -Force

# Cleanup temp
Remove-Item -Path $tempDir -Recurse -Force

# Report
$fileInfo = Get-Item $backupPath
$sizeMB = [math]::Round($fileInfo.Length / 1MB, 2)

Write-Host ""
Write-Host "============================================"
Write-Host "Backup Complete!"
Write-Host "============================================"
Write-Host "File: $backupPath"
Write-Host "Size: $sizeMB MB"
Write-Host ""
