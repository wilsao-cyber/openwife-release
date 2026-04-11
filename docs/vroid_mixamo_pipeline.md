# VRoid + Mixamo 3D 動漫美少女 Pipeline

## 整體流程

```
TripoSR 基礎模型          VRoid Studio 精修          Mixamo 動畫          VRM 格式
    ↓                        ↓                         ↓                    ↓
粗糙人形輪廓  →  參考用  →  高品質動漫角色  →  骨骼動畫  →  表情系統  →  手機渲染
 (857KB GLB)              (VRM, 10-50MB)           (FBX animations)    (完整支援)
```

---

## Step 1: VRoid Studio 建模

### 安裝
- **Windows**: https://vroid.com/en/studio
- **macOS**: https://vroid.com/en/studio
- **免費**，支援 Steam 或直接下載

### 使用 TripoSR 模型作為參考
1. 開啟 VRoid Studio
2. 匯入 `output/models/0/mesh.glb` 作為參考模型
3. 根據參考調整：
   - **身體比例**：頭身比、三圍
   - **臉部**：眼睛大小、嘴巴形狀
   - **頭髮**：髮型、髮色、劉海
   - **服裝**：衣服、裙子、配件
   - **膚色**：膚色調整

### 匯出設定
- 格式：**VRM 1.0**
- 解析度：貼圖 2048x2048 或更高
- 檔案名稱：`character_vroid.vrm`

---

## Step 2: Mixamo 動畫

### 上傳模型
1. 前往 https://www.mixamo.com
2. 上傳 VRoid 匯出的 `.vrm` 或先轉成 `.fbx`
3. 設定骨骼綁定點（下巴、手腕、手肘、膝蓋、胯下）

### 選擇動畫
推薦動畫清單：

| 類別 | 動畫名稱 | 用途 |
|------|----------|------|
| Idle | Standing Idle | 預設站立 |
| Idle | Breathing Idle | 呼吸動畫 |
| Greeting | Wave | 打招呼 |
| Greeting | Nod Yes | 點頭 |
| Greeting | Shake Head No | 搖頭 |
| Dancing | Sway Dance | 輕鬆跳舞 |
| Dancing | K-Pop Dance | 韓舞 |
| Emotion | Laughing | 笑 |
| Emotion | Clapping | 拍手 |
| Emotion | Cheer | 歡呼 |
| Walking | Walk Forward | 走路 |
| Sitting | Sitting Idle | 坐下 |

### 下載設定
- 格式：**FBX Binary**
- 幀率：**30 FPS**
- 關鍵幀簡化：**0.5**
- 包含皮膚：**否**（只需要動畫）

---

## Step 3: FBX → VRM 動畫整合

### 使用 UniVRM (Unity)
```bash
# 1. 安裝 Unity 2022 LTS
# 2. 建立新專案
# 3. 安裝 UniVRM: https://github.com/vrm-c/UniVRM/releases
# 4. 匯入 VRoid 模型 + Mixamo 動畫
# 5. 設定 Animator Controller
# 6. 匯出為 VRM
```

### 使用 Python 自動化（簡易版）
```bash
# 轉換 FBX 動畫為 GLTF 動畫
bash scripts/convert_animations.sh

# 整合動畫到 VRM
python scripts/merge_animations.py \
  --model character_vroid.vrm \
  --animations mixamo_animations/ \
  --output character_final.vrm
```

---

## Step 4: VRM 表情系統

### VRM Blendshapes
VRM 內建表情系統，對應 AI 老婆對話時的情緒：

| 表情 | BlendShape | 觸發情境 |
|------|------------|----------|
| 開心 | happy | 正面回應 |
| 難過 | sad | 安慰時 |
| 生氣 | angry | 撒嬌抱怨 |
| 驚訝 | surprised | 意外發現 |
| 害羞 | shy | 被稱讚時 |
| 眨眼 | blink | 自動循環 |
| 說話 | aa, ih, ou, eh, oh | 語音同步 |

### 設定方式
在 VRoid Studio 中設定表情預設值，或在 Unity 中使用 UniVRM 的 BlendShapeProxy。

---

## Step 5: Flutter 整合

### 方案 A: model_viewer_plus (簡易)
- 支援 GLB/GLTF
- 不支援 VRM 表情/動畫
- 適合靜態展示

### 方案 B: flutter_unity_widget (推薦)
- 完整 VRM 支援
- UniVRM + Animator
- 表情控制
- 動畫切換

### 方案 C: three.js via WebView
- 使用 @pixiv/three-vrm
- 網頁渲染
- 跨平台

---

## 檔案結構

```
ai_wife_app/
├── models/
│   ├── 3d/
│   │   ├── TripoSR/           # TripoSR 原始模型
│   │   └── vroid/             # VRoid 精修模型
│   │       ├── character_vroid.vrm
│   │       └── character_final.vrm
│   └── animations/
│       ├── idle_standing.fbx
│       ├── idle_breathing.fbx
│       ├── wave.fbx
│       ├── nod_yes.fbx
│       ├── shake_head_no.fbx
│       ├── sway_dance.fbx
│       ├── laughing.fbx
│       └── walk_forward.fbx
├── mobile_app/
│   └── assets/
│       ├── models/
│       │   ├── character.glb          # TripoSR 臨時模型
│       │   └── character_final.vrm    # 最終 VRM 模型
│       └── animations/                # 動畫檔案
└── scripts/
    ├── convert_animations.sh
    └── merge_animations.py
```

---

## 快速開始

1. **安裝 VRoid Studio** → https://vroid.com/en/studio
2. **根據 TripoSR 模型建立角色** → 匯出 VRM
3. **上傳 Mixamo** → 下載動畫
4. **整合到 Unity + UniVRM** → 匯出最終 VRM
5. **放入 Flutter assets** → 執行 App
