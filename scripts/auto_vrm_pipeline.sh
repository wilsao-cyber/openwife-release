#!/bin/bash

echo "=============================================="
echo "  AI 老婆 3D 角色自動生成 Pipeline"
echo "=============================================="
echo ""
echo "流程: 單張圖片 → CharacterGen → UniRig → Mesh2Motion → VRM + 動畫"
echo ""

# ============================
# 配置
# ============================
INPUT_IMAGE="${1:-./input.png}"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_DIR="$PROJECT_DIR/output/character"
MODELS_DIR="$PROJECT_DIR/models/3d"
ANIMATIONS_DIR="$PROJECT_DIR/mobile_app/assets/animations"
VRM_OUTPUT="$PROJECT_DIR/mobile_app/assets/models/character_final.vrm"

mkdir -p "$OUTPUT_DIR" "$ANIMATIONS_DIR"

# 檢查 GPU
echo "[1/7] 檢查 GPU..."
if ! python3.12 -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
    echo "ERROR: CUDA 不可用。需要 NVIDIA GPU。"
    exit 1
fi
GPU_MEM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader | head -1 | tr -d ' ')
echo "  GPU 記憶體: ${GPU_MEM}MB (RTX 3090 OK)"

# ============================
# Step 1: CharacterGen - 生成 3D 角色
# ============================
echo ""
echo "[2/7] CharacterGen: 生成 3D 動漫角色..."
CHARACTERGEN_DIR="$MODELS_DIR/CharacterGen"

if [ ! -d "$CHARACTERGEN_DIR" ]; then
    echo "  下載 CharacterGen..."
    cd "$MODELS_DIR"
    git clone https://github.com/zjp-shadow/CharacterGen.git
    cd "$CHARACTERGEN_DIR"

    echo "  下載模型權重..."
    source "$PROJECT_DIR/server/venv/bin/activate"
    huggingface-cli download --resume-download zjpshadow/CharacterGen \
        --include "2D_Stage/*" --local-dir .
    huggingface-cli download --resume-download zjpshadow/CharacterGen \
        --include "3D_Stage/*" --local-dir .
fi

echo "  執行 2D 多視圖生成..."
cd "$CHARACTERGEN_DIR/2D_Stage"
python webui.py --input_image "$INPUT_IMAGE" --output_dir "$OUTPUT_DIR/multiview"

echo "  執行 3D 網格生成..."
cd "$CHARACTERGEN_DIR/3D_Stage"
python webui.py --multiview_dir "$OUTPUT_DIR/multiview" --output_dir "$OUTPUT_DIR/mesh"

CHARACTER_MESH="$OUTPUT_DIR/mesh/character.obj"
if [ ! -f "$CHARACTER_MESH" ]; then
    echo "  ERROR: CharacterGen 生成失敗"
    exit 1
fi
echo "  OK: 3D 角色網格生成完成"

# ============================
# Step 2: UniRig - 自動骨骼綁定
# ============================
echo ""
echo "[3/7] UniRig: 自動骨骼綁定..."
UNIRIG_DIR="$MODELS_DIR/UniRig"

if [ ! -d "$UNIRIG_DIR" ]; then
    echo "  下載 UniRig..."
    cd "$MODELS_DIR"
    git clone https://github.com/VAST-AI-Research/UniRig.git
    cd "$UNIRIG_DIR"
    source "$PROJECT_DIR/server/venv/bin/activate"
    pip install -r requirements.txt
fi

cd "$UNIRIG_DIR"
python infer.py \
    --mesh_path "$CHARACTER_MESH" \
    --output_dir "$OUTPUT_DIR/rigged" \
    --device cuda:0

RIGGED_MESH="$OUTPUT_DIR/rigged/character_rigged.glb"
if [ ! -f "$RIGGED_MESH" ]; then
    echo "  ERROR: UniRig 綁定失敗"
    exit 1
fi
echo "  OK: 骨骼綁定完成"

# ============================
# Step 3: Mesh2Motion - 自動動畫
# ============================
echo ""
echo "[4/7] Mesh2Motion: 套用動畫..."

# 使用 Mesh2Motion API 或 Blender 腳本
MESH2MOTION_SCRIPT="$PROJECT_DIR/scripts/mesh2motion_auto.py"

if [ -f "$MESH2MOTION_SCRIPT" ]; then
    source "$PROJECT_DIR/server/venv/bin/activate"
    python "$MESH2MOTION_SCRIPT" \
        --input "$RIGGED_MESH" \
        --output_dir "$ANIMATIONS_DIR" \
        --animations idle,walk,wave,dance,laugh,nod,shake
else
    echo "  使用 Blender 動畫腳本..."
    bash "$PROJECT_DIR/scripts/apply_animations_blender.sh" \
        "$RIGGED_MESH" "$ANIMATIONS_DIR"
fi

echo "  OK: 動畫套用完成"

# ============================
# Step 4: 轉換為 VRM
# ============================
echo ""
echo "[5/7] 轉換為 VRM 格式..."

VRM_CONVERT_SCRIPT="$PROJECT_DIR/scripts/glb_to_vrm.py"
if [ -f "$VRM_CONVERT_SCRIPT" ]; then
    source "$PROJECT_DIR/server/venv/bin/activate"
    python "$VRM_CONVERT_SCRIPT" \
        --input "$RIGGED_MESH" \
        --output "$VRM_OUTPUT" \
        --animations_dir "$ANIMATIONS_DIR"
else
    echo "  使用 Blender VRM addon..."
    BLENDER_VRM_SCRIPT="$PROJECT_DIR/scripts/blender_vrm_export.py"
    blender --background --python "$BLENDER_VRM_SCRIPT" -- \
        --input "$RIGGED_MESH" \
        --output "$VRM_OUTPUT"
fi

if [ -f "$VRM_OUTPUT" ]; then
    echo "  OK: VRM 輸出完成 → $VRM_OUTPUT"
else
    echo "  WARNING: VRM 轉換需要 Blender VRM addon"
    echo "  暫時使用 GLB 格式"
    cp "$RIGGED_MESH" "$PROJECT_DIR/mobile_app/assets/models/character_final.glb"
fi

# ============================
# Step 5: 複製到 Flutter Assets
# ============================
echo ""
echo "[6/7] 複製到 Flutter 專案..."
cp "$VRM_OUTPUT" "$PROJECT_DIR/mobile_app/assets/models/" 2>/dev/null
cp "$RIGGED_MESH" "$PROJECT_DIR/mobile_app/assets/models/character_backup.glb" 2>/dev/null
echo "  OK: 檔案已複製"

# ============================
# Step 6: 更新 Flutter pubspec
# ============================
echo ""
echo "[7/7] 更新 Flutter pubspec.yaml..."
PUBSPEC="$PROJECT_DIR/mobile_app/pubspec.yaml"

if ! grep -q "character_final" "$PUBSPEC" 2>/dev/null; then
    echo "  添加 VRM 模型到 assets..."
    # pubspec 已經有 assets/models/ 目錄，不需要額外添加
fi

echo ""
echo "=============================================="
echo "  Pipeline 完成！"
echo "=============================================="
echo ""
echo "輸出檔案:"
echo "  VRM 模型: $VRM_OUTPUT"
echo "  GLB 備份: $PROJECT_DIR/mobile_app/assets/models/character_backup.glb"
echo "  動畫目錄: $ANIMATIONS_DIR/"
echo ""
echo "下一步:"
echo "  1. 執行 flutter pub get"
echo "  2. 執行 flutter run"
echo "  3. AI 老婆就可以在手機上動起來了！"
echo ""
