$env:DATABASE_URL = 'sqlite:///D:/React Native Project/DataViz_App/infrastructure/tmp/live-demo.db'
$env:CORS_ORIGINS = 'http://127.0.0.1:3000,http://localhost:3000'
$env:APP_PUBLIC_URL = 'http://127.0.0.1:3000'
$env:JWT_SECRET_KEY = 'local-demo-jwt-secret-key-1234567890'
Set-Location 'D:\React Native Project\DataViz_App\apps\api'
& 'C:\Users\rahul\AppData\Local\Programs\Python\Python311\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8000
