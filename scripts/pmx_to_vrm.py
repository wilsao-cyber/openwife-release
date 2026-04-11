"""
PMX to VRM converter using Blender + mmd_tools + VRM Addon.
Usage: blender --background --python pmx_to_vrm.py -- input.pmx output.vrm
"""
import bpy
import sys
import os
# Parse args after "--"
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if len(argv) < 2:
    print("Usage: blender --background --python pmx_to_vrm.py -- <input.pmx> <output.vrm>")
    sys.exit(1)

pmx_path = os.path.abspath(argv[0])
vrm_path = os.path.abspath(argv[1])

print(f"[PMX→VRM] Input:  {pmx_path}")
print(f"[PMX→VRM] Output: {vrm_path}")

# Enable addons
bpy.ops.preferences.addon_enable(module="mmd_tools")
bpy.ops.preferences.addon_enable(module="VRM_Addon_for_Blender")

# Clear scene completely (including default Cube, Camera, Light)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
# Also remove orphan data
for mesh in bpy.data.meshes:
    if mesh.users == 0:
        bpy.data.meshes.remove(mesh)
for mat in bpy.data.materials:
    if mat.users == 0:
        bpy.data.materials.remove(mat)

# ── Monkey-patch mmd_tools shader issue for Blender 4.0 ──
# Directly patch the problematic method in the source before it runs
import mmd_tools.core.material as _mmd_mat

# The class is _FnMaterialCycles (internal), find and patch all shader update methods
for _attr in dir(_mmd_mat):
    _obj = getattr(_mmd_mat, _attr)
    if not isinstance(_obj, type):
        continue
    for _method_name in list(vars(_obj)):
        if "update_shader_nodes" in _method_name:
            _orig = getattr(_obj, _method_name)
            if callable(_orig):
                def _make_safe(orig_fn):
                    def _safe(self):
                        try:
                            return orig_fn(self)
                        except (KeyError, AttributeError, RuntimeError):
                            pass
                    return _safe
                setattr(_obj, _method_name, _make_safe(_orig))
                print(f"[PMX→VRM] Patched {_attr}.{_method_name}")

# Import PMX
print("[PMX→VRM] Importing PMX...")
try:
    bpy.ops.mmd_tools.import_model(
        filepath=pmx_path,
        scale=0.12,
        types={"MESH", "ARMATURE", "MORPHS"},
        clean_model=True,
    )
    print("[PMX→VRM] PMX imported successfully")
except Exception as e:
    print(f"[PMX→VRM] Import had issues (continuing): {e}")

# Find the armature and mesh objects
armature = None
meshes = []
mmd_root = None
for obj in bpy.context.scene.objects:
    if obj.type == "ARMATURE":
        armature = obj
    elif obj.type == "MESH":
        meshes.append(obj)
    elif obj.type == "EMPTY" and obj.mmd_type == "ROOT":
        mmd_root = obj

if not armature:
    # Try to find armature as child of MMD root
    for obj in bpy.context.scene.objects:
        if obj.type == "ARMATURE":
            armature = obj
            break

if not armature:
    print("[PMX→VRM] ERROR: No armature found!")
    sys.exit(1)

print(f"[PMX→VRM] Armature: {armature.name}, Meshes: {len(meshes)}")

# ── Filter out non-character meshes ──
# Remove default Cube and any mesh not parented to the armature/MMD root hierarchy
filtered_meshes = []
for m in meshes:
    # Log each mesh for debugging
    vert_count = len(m.data.vertices) if m.data else 0
    print(f"  Mesh: {m.name} verts={vert_count} parent={m.parent.name if m.parent else 'None'}")
    # Skip default Blender objects and very simple meshes (< 100 verts, likely physics boxes)
    if m.name in ("Cube", "Plane", "Sphere", "Cylinder") and vert_count < 100:
        print(f"    Skipping default object: {m.name}")
        bpy.data.objects.remove(m, do_unlink=True)
        continue
    filtered_meshes.append(m)
meshes = filtered_meshes
print(f"[PMX→VRM] After filtering: {len(meshes)} meshes")

# ── Fix materials: rebuild with Principled BSDF + proper alpha ──
pmx_dir = os.path.dirname(pmx_path)
print("[PMX→VRM] Rebuilding materials...")
for mesh_obj in meshes:
    for mat_slot in mesh_obj.material_slots:
        mat = mat_slot.material
        if not mat or not mat.node_tree:
            continue
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        # Collect all image texture nodes
        img_nodes = [n for n in nodes if isinstance(n, bpy.types.ShaderNodeTexImage) and n.image]

        # Find or create Principled BSDF
        principled = None
        for n in nodes:
            if isinstance(n, bpy.types.ShaderNodeBsdfPrincipled):
                principled = n
                break
        if not principled:
            principled = nodes.new("ShaderNodeBsdfPrincipled")
            principled.location = (0, 0)

        # Find or create output
        out_node = None
        for n in nodes:
            if isinstance(n, bpy.types.ShaderNodeOutputMaterial):
                out_node = n
                break
        if not out_node:
            out_node = nodes.new("ShaderNodeOutputMaterial")
            out_node.location = (300, 0)

        # Connect principled -> output
        links.new(principled.outputs[0], out_node.inputs["Surface"])

        if img_nodes:
            main_tex = img_nodes[0]
            links.new(main_tex.outputs["Color"], principled.inputs["Base Color"])

            # Check if texture has alpha channel
            img = main_tex.image
            has_alpha = img and img.channels == 4

            # Detect if this material needs transparency
            mat_name_lower = mat.name.lower()
            needs_alpha = has_alpha or any(k in mat_name_lower for k in
                ["髪", "hair", "丝", "纱", "lace", "花边", "透", "alpha", "レース"])

            if needs_alpha and has_alpha:
                links.new(main_tex.outputs["Alpha"], principled.inputs["Alpha"])
                mat.blend_method = "HASHED"
                mat.shadow_method = "HASHED"
            else:
                mat.blend_method = "OPAQUE"

            # Always double-sided — PMX models rely on it
            mat.use_backface_culling = False

        # Set material to not be too shiny
        spec_input = principled.inputs.get("Specular") or principled.inputs.get("Specular IOR Level")
        if spec_input:
            spec_input.default_value = 0.3
        principled.inputs["Roughness"].default_value = 0.6

# ── Recalculate normals (fix flipped faces) ──
print("[PMX→VRM] Recalculating normals...")
for m in meshes:
    bpy.ops.object.select_all(action="DESELECT")
    m.select_set(True)
    bpy.context.view_layer.objects.active = m
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")

# Select all mesh objects and join them
if len(meshes) > 1:
    bpy.ops.object.select_all(action="DESELECT")
    for m in meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.join()
    meshes = [bpy.context.active_object]
    print(f"[PMX→VRM] Joined meshes into: {meshes[0].name}")

mesh_obj = meshes[0] if meshes else None

# Make sure mesh is parented to armature
if mesh_obj and mesh_obj.parent != armature:
    mesh_obj.parent = armature
    mod = mesh_obj.modifiers.get("Armature") or mesh_obj.modifiers.new("Armature", "ARMATURE")
    mod.object = armature

# Remove MMD root empty (VRM export doesn't need it)
if mmd_root:
    # Unparent armature from MMD root
    armature.parent = None
    bpy.data.objects.remove(mmd_root, do_unlink=True)

# Select armature for VRM setup
bpy.ops.object.select_all(action="DESELECT")
armature.select_set(True)
bpy.context.view_layer.objects.active = armature

# MMD bone name to VRM humanoid bone mapping
# Supports both 左/右 prefix and .L/.R suffix naming conventions
MMD_TO_VRM_BONES = {
    # Core body
    "全ての親": "hips",
    "センター": "hips",
    "上半身": "spine",
    "上半身2": "chest",
    "首": "neck",
    "頭": "head",
    # Arms - 左/右 prefix style
    "左肩": "leftShoulder",  "右肩": "rightShoulder",
    "左腕": "leftUpperArm",  "右腕": "rightUpperArm",
    "左ひじ": "leftLowerArm", "右ひじ": "rightLowerArm",
    "左手首": "leftHand",     "右手首": "rightHand",
    # Arms - .L/.R suffix style
    "肩.L": "leftShoulder",  "肩.R": "rightShoulder",
    "腕.L": "leftUpperArm",  "腕.R": "rightUpperArm",
    "ひじ.L": "leftLowerArm", "ひじ.R": "rightLowerArm",
    "手首.L": "leftHand",     "手首.R": "rightHand",
    # Legs - 左/右 prefix style
    "左足": "leftUpperLeg",   "右足": "rightUpperLeg",
    "左ひざ": "leftLowerLeg", "右ひざ": "rightLowerLeg",
    "左足首": "leftFoot",     "右足首": "rightFoot",
    "左つま先": "leftToes",   "右つま先": "rightToes",
    # Legs - .L/.R suffix style
    "足.L": "leftUpperLeg",   "足.R": "rightUpperLeg",
    "ひざ.L": "leftLowerLeg", "ひざ.R": "rightLowerLeg",
    "足首.L": "leftFoot",     "足首.R": "rightFoot",
    "つま先.L": "leftToes",   "つま先.R": "rightToes",
    # Fingers - 左/右 prefix
    "左親指０": "leftThumbMetacarpal",  "右親指０": "rightThumbMetacarpal",
    "左親指１": "leftThumbProximal",    "右親指１": "rightThumbProximal",
    "左親指２": "leftThumbDistal",      "右親指２": "rightThumbDistal",
    "左人指１": "leftIndexProximal",    "右人指１": "rightIndexProximal",
    "左人指２": "leftIndexIntermediate","右人指２": "rightIndexIntermediate",
    "左人指３": "leftIndexDistal",      "右人指３": "rightIndexDistal",
    "左中指１": "leftMiddleProximal",   "右中指１": "rightMiddleProximal",
    "左中指２": "leftMiddleIntermediate","右中指２": "rightMiddleIntermediate",
    "左中指３": "leftMiddleDistal",     "右中指３": "rightMiddleDistal",
    "左薬指１": "leftRingProximal",     "右薬指１": "rightRingProximal",
    "左薬指２": "leftRingIntermediate", "右薬指２": "rightRingIntermediate",
    "左薬指３": "leftRingDistal",       "右薬指３": "rightRingDistal",
    "左小指１": "leftLittleProximal",   "右小指１": "rightLittleProximal",
    "左小指２": "leftLittleIntermediate","右小指２": "rightLittleIntermediate",
    "左小指３": "leftLittleDistal",     "右小指３": "rightLittleDistal",
    # Fingers - .L/.R suffix
    "親指０.L": "leftThumbMetacarpal",  "親指０.R": "rightThumbMetacarpal",
    "親指１.L": "leftThumbProximal",    "親指１.R": "rightThumbProximal",
    "親指２.L": "leftThumbDistal",      "親指２.R": "rightThumbDistal",
    "人指１.L": "leftIndexProximal",    "人指１.R": "rightIndexProximal",
    "人指２.L": "leftIndexIntermediate","人指２.R": "rightIndexIntermediate",
    "人指３.L": "leftIndexDistal",      "人指３.R": "rightIndexDistal",
    "中指１.L": "leftMiddleProximal",   "中指１.R": "rightMiddleProximal",
    "中指２.L": "leftMiddleIntermediate","中指２.R": "rightMiddleIntermediate",
    "中指３.L": "leftMiddleDistal",     "中指３.R": "rightMiddleDistal",
    "薬指１.L": "leftRingProximal",     "薬指１.R": "rightRingProximal",
    "薬指２.L": "leftRingIntermediate", "薬指２.R": "rightRingIntermediate",
    "薬指３.L": "leftRingDistal",       "薬指３.R": "rightRingDistal",
    "小指１.L": "leftLittleProximal",   "小指１.R": "rightLittleProximal",
    "小指２.L": "leftLittleIntermediate","小指２.R": "rightLittleIntermediate",
    "小指３.L": "leftLittleDistal",     "小指３.R": "rightLittleDistal",
    # Eyes
    "左目": "leftEye",  "右目": "rightEye",
    "目.L": "leftEye",  "目.R": "rightEye",
}

# Set up VRM humanoid bone mapping
print("[PMX→VRM] Setting up VRM humanoid bones...")
vrm_data = armature.data.vrm_addon_extension
human_bones = vrm_data.vrm1.humanoid.human_bones

bone_names = [b.name for b in armature.data.bones]
print(f"[PMX→VRM] Available bones ({len(bone_names)} total): {bone_names[:20]}...")
# Write full bone list for debugging
import tempfile as _tempfile
with open(os.path.join(_tempfile.gettempdir(), "pmx_bones.txt"), "w") as _f:
    for _bn in bone_names:
        _f.write(_bn + "\n")
mapped = 0
bone_names_set = set(bone_names)
import re as _re
def _camel_to_snake(name):
    return _re.sub(r'(?<=[a-z])(?=[A-Z])', '_', name).lower()

for mmd_name, vrm_bone_name in MMD_TO_VRM_BONES.items():
    if mmd_name in bone_names_set:
        # Try both camelCase and snake_case
        bone_prop = getattr(human_bones, vrm_bone_name, None) or getattr(human_bones, _camel_to_snake(vrm_bone_name), None)
        if bone_prop is not None:
            # Don't overwrite if already mapped (e.g. hips from 全ての親 vs センター)
            if bone_prop.node.bone_name and bone_prop.node.bone_name in bone_names_set:
                continue
            bone_prop.node.bone_name = mmd_name
            mapped += 1
            print(f"  {mmd_name} → {vrm_bone_name}")
        else:
            print(f"  {mmd_name} → {vrm_bone_name} (NO PROP)")

print(f"[PMX→VRM] Mapped {mapped} bones")

# Set up VRM expressions from MMD morphs (shape keys)
if mesh_obj and mesh_obj.data.shape_keys:
    print("[PMX→VRM] Setting up VRM expressions from morphs...")
    keys = mesh_obj.data.shape_keys.key_blocks
    key_names = [k.name for k in keys]
    print(f"[PMX→VRM] Available morphs: {key_names[:15]}...")

    MORPH_TO_EXPR = {
        "まばたき": "blink",
        "ウィンク": "blinkLeft",
        "ウィンク右": "blinkRight",
        "あ": "aa",
        "い": "ih",
        "う": "ou",
        "え": "ee",
        "お": "oh",
        "にやり": "happy",
        "笑い": "happy",
        "怒り": "angry",
        "困る": "sad",
        "真面目": "neutral",
        "びっくり": "surprised",
    }

    expressions = vrm_data.vrm1.expressions
    for morph_name, expr_name in MORPH_TO_EXPR.items():
        if morph_name in key_names:
            preset = getattr(expressions, expr_name, None)
            if preset is not None and hasattr(preset, "morph_target_binds"):
                bind = preset.morph_target_binds.add()
                bind.node.mesh_object_name = mesh_obj.name
                bind.index = key_names.index(morph_name)
                bind.weight = 1.0
                print(f"  {morph_name} → {expr_name}")

# VRM meta info
print("[PMX→VRM] Setting VRM metadata...")
meta = vrm_data.vrm1.meta
meta.vrm_name = os.path.splitext(os.path.basename(pmx_path))[0]
meta.authors.clear()
author = meta.authors.add()
author.value = "Converted from PMX"
meta.allow_antisocial_or_hate_usage = False
meta.allow_excessively_sexual_usage = True
meta.allow_excessively_violent_usage = False
meta.allow_political_or_religious_usage = False
meta.allow_redistribution = False

# ── Compress textures to reduce file size ──
print("[PMX→VRM] Compressing textures...")
MAX_TEX_SIZE = 1024  # Good balance of quality vs file size
# Remove images not used by any material (like cover art X.png)
used_images = set()
for mat in bpy.data.materials:
    if mat.node_tree:
        for node in mat.node_tree.nodes:
            if isinstance(node, bpy.types.ShaderNodeTexImage) and node.image:
                used_images.add(node.image.name)

for img in list(bpy.data.images):
    if img.name not in used_images and img.users == 0:
        print(f"  Removing unused image: {img.name}")
        bpy.data.images.remove(img)
        continue

# Resize textures over MAX_TEX_SIZE to reduce VRM file size
for img in bpy.data.images:
    if img.size[0] == 0:
        continue
    if img.size[0] > MAX_TEX_SIZE or img.size[1] > MAX_TEX_SIZE:
        ratio = MAX_TEX_SIZE / max(img.size[0], img.size[1])
        new_w = max(1, int(img.size[0] * ratio))
        new_h = max(1, int(img.size[1] * ratio))
        img.scale(new_w, new_h)
        print(f"  Resized {img.name}: {new_w}x{new_h} ch={img.channels}")
    else:
        print(f"  Keep {img.name}: {img.size[0]}x{img.size[1]} ch={img.channels}")

# Export as VRM
print(f"[PMX→VRM] Exporting VRM to {vrm_path}...")
os.makedirs(os.path.dirname(vrm_path) or ".", exist_ok=True)

try:
    bpy.ops.export_scene.vrm(filepath=vrm_path)
    size_mb = os.path.getsize(vrm_path) / 1024 / 1024
    print(f"[PMX→VRM] === DONE === Output: {vrm_path} ({size_mb:.1f} MB)")
except Exception as e:
    print(f"[PMX→VRM] Export failed: {e}")
    # Try to list what validation errors exist
    print("[PMX→VRM] Checking VRM validation...")
    for bone_name in ["hips", "spine", "chest", "neck", "head",
                       "leftUpperArm", "leftLowerArm", "leftHand",
                       "rightUpperArm", "rightLowerArm", "rightHand",
                       "leftUpperLeg", "leftLowerLeg", "leftFoot",
                       "rightUpperLeg", "rightLowerLeg", "rightFoot"]:
        prop = getattr(human_bones, bone_name, None)
        if prop:
            bn = prop.node.bone_name
            status = f"✓ {bn}" if bn else "✗ MISSING"
            print(f"  {bone_name}: {status}")
    sys.exit(1)
