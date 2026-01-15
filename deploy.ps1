# 家具報價單系統 - 部署腳本
# 目標伺服器: 192.168.0.83
# 使用者: ai-user

$SERVER = "192.168.0.83"
$USER = "ai-user"
$REMOTE_DIR = "/home/ai-user/Fairmont"
$LOCAL_DIR = $PSScriptRoot

Write-Host "=== 家具報價單系統部署腳本 ===" -ForegroundColor Cyan
Write-Host "目標伺服器: $USER@$SERVER" -ForegroundColor Yellow
Write-Host ""

# Step 1: 上傳專案檔案
Write-Host "[1/4] 上傳專案檔案..." -ForegroundColor Green
scp -r "$LOCAL_DIR/backend" "$LOCAL_DIR/skills" "$LOCAL_DIR/docker-compose.yml" "$LOCAL_DIR/.env.example" "${USER}@${SERVER}:${REMOTE_DIR}/"

# Step 2: SSH 進入伺服器並執行部署
Write-Host "[2/4] SSH 連線到伺服器..." -ForegroundColor Green
Write-Host "請在 SSH 終端中執行以下命令：" -ForegroundColor Yellow
Write-Host ""
Write-Host @"
# === 在伺服器上執行 ===

# 1. 安裝 Docker (如果尚未安裝)
sudo apt update && sudo apt install -y docker.io docker-compose
sudo usermod -aG docker `$USER
# 如果剛加入 docker 群組，需要重新登入

# 2. 設定環境變數
cd ~/Fairmont
cp .env.example .env
nano .env  # 填入 GEMINI_API_KEY

# 3. 啟動服務
docker-compose up -d --build

# 4. 驗證
curl http://localhost:8000/api/v1/health
"@ -ForegroundColor White

Write-Host ""
Write-Host "現在開啟 SSH 連線..." -ForegroundColor Green
ssh "${USER}@${SERVER}"
