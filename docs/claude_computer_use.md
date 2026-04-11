# Claude Computer Use VRM Pipeline

## 架構

```
單張圖片 → TripoSR/CharacterGen → 3D 網格 (GLB)
                                      ↓
                    Claude Computer Use 自動操作
                            ↙            ↘
                   Mesh2Motion 網站      Blender
                   (自動套動畫)        (匯出VRM)
                            ↘            ↙
                         VRM + 動畫 GLB
```

## 需要安裝

```bash
# Claude Computer Use 依賴
pip install anthropic

# 螢幕操作工具
sudo apt install xdotool scrot xclip

# Headless 環境 (伺服器)
sudo apt install xvfb

# 啟動虛擬顯示
Xvfb :99 -screen 0 1280x720x24 &
export DISPLAY=:99
```

## 執行

```bash
# 設定 API Key
export ANTHROPIC_API_KEY="sk-ant-..."

# 執行完整 pipeline
python scripts/claude_computer_use_pipeline.py ~/Pictures/your_character.jpeg
```

## Claude 會自動做什麼

1. **截圖分析** — 看到當前螢幕畫面
2. **操作 Mesh2Motion** — 打開瀏覽器、上傳模型、選動畫、匯出
3. **操作 Blender** — 打開 Blender、匯入模型、安裝 VRM addon、匯出 VRM
4. **驗證結果** — 確認檔案正確生成

## 成本估算

| 任務 | 步驟數 | 預估成本 (Sonnet 4) |
|------|--------|---------------------|
| Mesh2Motion 動畫 | 15-20 | $0.20-0.40 |
| Blender VRM 匯出 | 10-15 | $0.15-0.30 |
| **總計** | **25-35** | **$0.35-0.70** |
