#!/bin/bash

echo "=== FBX Animation to GLTF Converter ==="

INPUT_DIR="${1:-mixamo_animations}"
OUTPUT_DIR="${2:-mobile_app/assets/animations}"

mkdir -p "$OUTPUT_DIR"

if ! command -v blender &> /dev/null; then
    echo "Blender not found. Please install Blender:"
    echo "  Ubuntu: sudo apt install blender"
    echo "  macOS:  brew install --cask blender"
    exit 1
fi

for fbx in "$INPUT_DIR"/*.fbx; do
    [ -f "$fbx" ] || continue
    name=$(basename "$fbx" .fbx)
    gltf="$OUTPUT_DIR/$name.glb"

    echo "Converting: $name.fbx -> $name.glb"

    blender --background --python - <<EOF
import bpy
import sys

bpy.ops.import_scene.fbx(filepath="$fbx")

for obj in bpy.context.selected_objects:
    bpy.context.view_layer.objects.active = obj
    if obj.animation_data and obj.animation_data.action:
        obj.animation_data.action.name = "$name"

bpy.ops.export_scene.gltf(
    filepath="$gltf",
    export_format='GLB',
    export_animations=True,
    export_current_frame=True,
)
EOF

    if [ $? -eq 0 ]; then
        echo "  OK: $gltf"
    else
        echo "  FAILED: $name"
    fi
done

echo "=== Conversion Complete ==="
echo "Output: $OUTPUT_DIR"
