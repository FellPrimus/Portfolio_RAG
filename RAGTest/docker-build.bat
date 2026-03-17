@echo off
REM RAGTest Docker Build Script
REM Usage: docker-build.bat [tag]

SET TAG=%1
IF "%TAG%"=="" SET TAG=latest

echo ============================================
echo RAGTest Docker Build
echo Tag: %TAG%
echo ============================================

REM Build the image
echo Building Docker image...
docker build -t ragtest:%TAG% .

IF %ERRORLEVEL% NEQ 0 (
    echo Build failed!
    exit /b 1
)

echo.
echo Build successful!
echo.

REM Save the image as tar file for backup
SET BACKUP_FILE=ragtest-%TAG%-%DATE:~0,4%%DATE:~5,2%%DATE:~8,2%.tar
echo Saving image to %BACKUP_FILE%...
docker save -o %BACKUP_FILE% ragtest:%TAG%

IF %ERRORLEVEL% EQU 0 (
    echo Image saved to %BACKUP_FILE%
) ELSE (
    echo Warning: Could not save image to file
)

echo.
echo ============================================
echo To run the container:
echo   docker-compose up -d
echo.
echo Or manually:
echo   docker run -d -p 5000:5000 --name ragtest -v ./data:/app/data ragtest:%TAG%
echo ============================================
