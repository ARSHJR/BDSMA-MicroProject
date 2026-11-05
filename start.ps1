# Starts API (8000) and web app (5173) in two windows.
Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$PSScriptRoot\backend'; python -m uvicorn app.main:app --port 8000"
Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$PSScriptRoot\frontend'; npm run dev"
Write-Host "API: http://127.0.0.1:8000/docs   App: http://localhost:5173"
