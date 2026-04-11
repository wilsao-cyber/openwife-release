# 全自動 VRM 生成 Pipeline

## 整體架構

```
單張圖片 → CharacterGen → UniRig → Mesh2Motion → VRM + 動畫
   ↓            ↓            ↓           ↓          ↓
你的美少女   多視圖+3D網格   自動骨骼    自動動畫   手機可用
```

---

## 使用的開源工具

| 工具 | 論文/來源 | 功能 | 星星數 |
|------|-----------|------|--------|
| **CharacterGen** | SIGGRAPH'24 (TOG) | 單圖 → 3D 動漫角色 | 784 |
| **UniRig** | SIGGRAPH'25 | 自動骨骼綁定 | 1,462 |
| **Mesh2Motion** | Open Source | 開源 Mixamo 替代 | N/A |
| **three-vrm** | pixiv | VRM 渲染 | 7.2k |

---

## Step-by-Step 流程

### Step 1: CharacterGen - 生成 3D 角色網格

```bash
# 自動下載並執行
cd models/3d/CharacterGen
python webui.py

# 或手動執行兩階段
cd 2D_Stage && python webui.py --input /path/to/your_character.jpeg
cd 3D_Stage && python webui.py --multiview ../2D_Stage/output
```

**輸出**: `character.obj` (帶貼圖的 3D 網格)

### Step 2: UniRig - 自動骨骼綁定

```bash
cd models/3d/UniRig
python infer.py \
    --mesh_path ../CharacterGen/3D_Stage/output/character.obj \
    --output_dir ../../output/rigged \
    --device cuda:0
```

**輸出**: `character_rigged.glb` (帶骨骼的 GLB)

### Step 3: Mesh2Motion - 自動套用動畫

```bash
# 方式 A: 使用 Mesh2Motion Web API
python scripts/mesh2motion_auto.py \
    --input output/rigged/character_rigged.glb \
    --output mobile_app/assets/animations/ \
    --animations idle,walk,wave,dance,laugh,nod,shake

# 方式 B: 使用 Blender 腳本
blender --background --python scripts/apply_animations.py -- \
    --input output/rigged/character_rigged.glb \
    --output mobile_app/assets/animations/
```

**輸出**: 多個 `.glb` 動畫檔案

### Step 4: 轉換為 VRM

```bash
# 使用 Blender VRM addon
blender --background --python scripts/blender_vrm_export.py -- \
    --input output/rigged/character_rigged.glb \
    --output mobile_app/assets/models/character_final.vrm
```

**輸出**: `character_final.vrm`

---

## 一鍵執行

```bash
chmod +x scripts/auto_vrm_pipeline.sh
bash scripts/auto_vrm_pipeline.sh ~/Pictures/your_character.jpeg
```

---

## 輸出檔案結構

```
mobile_app/assets/
├── models/
│   ├── character.glb            # TripoSR 臨時模型 (857KB)
│   ├── character_final.vrm      # 最終 VRM 模型 (10-50MB)
│   └── character_backup.glb     # GLB 備份
└── animations/
    ├── idle_standing.glb        # 預設站立
    ├── idle_breathing.glb       # 呼吸
    ├── walk_forward.glb         # 走路
    ├── wave.glb                 # 打招呼
    ├── dance.glb                # 跳舞
    ├── laugh.glb                # 笑
    ├── nod.glb                  # 點頭
    └── shake.glb                # 搖頭
```

---

## 表情系統

VRM 內建 BlendShape 表情，對應 AI 老婆對話情緒：

| 表情 | 觸發情境 | BlendShape |
|------|----------|------------|
| 開心 | 正面回應 | happy |
| 難過 | 安慰時 | sad |
| 生氣 | 撒嬌抱怨 | angry |
| 驚訝 | 意外發現 | surprised |
| 害羞 | 被稱讚時 | shy |
| 眨眼 | 自動循環 | blink |
| 說話 | 語音同步 | aa, ih, ou, eh, oh |

---

## 需求

- **GPU**: NVIDIA GPU with 12GB+ VRAM (RTX 3060 or above recommended)
- **Python**: 3.11+
- **Blender**: 3.6+ (needs to be installed)
- **磁碟空間**: ~20GB (模型權重)
