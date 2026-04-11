"""
Hand-curated SFX tag mappings for accurate scene_play/sfx_play matching.
Each entry maps a semantic tag (used by LLM) to filename patterns.
"""

# Semantic tag → list of filename substring patterns (Japanese)
# LLM uses the tag name; catalog search matches against these patterns
TAG_PATTERNS = {
    # === Intimate / Adult ===
    "handjob_slow": ["手コキ.*ゆっくり", "手コキ.*静か", "手コキ.*控えめ", "手コキ.*ねっとり", "手コキをする音1", "手コキをする音2", "手コキをする音12", "手コキをする音13"],
    "handjob_fast": ["手コキ.*速", "手コキ.*激し", "手コキ.*リズミカル", "手コキをする音3", "手コキをする音10"],
    "handjob_irregular": ["手コキ.*不規則", "手コキ.*焦ら", "手コキをする音4", "手コキをする音7", "手コキをする音11", "手コキをする音14"],
    "handjob_buildup": ["手コキ.*低速→中速", "手コキ.*ラストスパート", "手コキをする音5", "手コキをする音6", "手コキをする音8"],
    "lotion_apply": ["ローション.*塗", "ローション.*こす", "ローション.*くちゅ"],
    "lotion_bottle": ["ローション容器", "ローション.*絞り出す"],
    "piston_slow": ["ピストン.*ゆっくり", "ピストン.*ソフト", "乾いたピストン音3", "濡れたピストン音1", "濡れたピストン音5"],
    "piston_fast": ["ピストン.*激し", "ピストン.*速", "乾いたピストン音4", "濡れたピストン音2", "濡れたピストン音4"],
    "piston_wet": ["濡れたピストン", "弾けるような音", "水っぽい"],
    "piston_dry": ["乾いたピストン"],
    "ejaculation": ["射精音[0-9]"],
    "ejaculation_heavy": ["射精.*大量", "射精.*ドロドロ", "射精.*濃厚"],
    "squirt": ["潮吹き", "潮を吹く"],
    "onahole": ["オナホール"],
    "onahole_intense": ["オナホール.*激し"],
    "condom": ["コンドーム"],
    "tissue": ["ティッシュ"],

    # === Fabric / Bed ===
    "bedsheet": ["布団", "シーツ", "毛布", "掛布団", "ベッド"],
    "clothes_rustle": ["服.*脱", "衣服.*こす", "衣服.*擦", "布.*こす", "服を脱ぐ"],
    "zipper": ["ファスナー", "ジッパー", "チャック"],
    "pillow": ["枕"],

    # === Environment ===
    "rain": ["雨の音", "雨が降"],
    "rain_heavy": ["雨.*激し", "強い雨"],
    "rain_light": ["雨.*短め", "雨.*ループ"],
    "rain_ambient": ["雨.*環境音", "雨.*車"],

    # === Daily Life ===
    "typing": ["キーボード", "タイピング"],
    "gaming": ["ゲームコントローラー"],
    "book": ["本.*めくる", "冊子"],
    "money": ["お札", "小銭", "財布"],
    "cigarette": ["タバコ"],
    "rummage": ["ガサゴソ", "漁る"],
    "mouse": ["マウス"],

    # === Bath ===
    "bath_water": ["お湯", "湯船", "入浴"],
    "shower": ["シャワー"],
    "splash": ["水しぶき", "ばしゃ"],

    # === ASMR ===
    "ear_cleaning": ["耳かき", "耳掃除"],
    "ear_blow": ["息.*吹", "耳.*息"],

    # === Actions (RJ276666) ===
    "door": ["ドア", "扉"],
    "footstep": ["足音", "歩"],
    "slap": ["平手", "ビンタ", "叩"],
    # NOTE: heartbeat, breathing not in current library

    # === Koikatsu Extracted — Intimate ===
    "kiss_light": ["hse_ks_04"],
    "kiss_deep": ["hse_ks_05"],
    "kiss_long": ["hse_ks_06"],
    "touch_light": ["hse_ks_0[0-3]"],
    "lick": ["hse_ks_0[7-8]"],
    "suck": ["hse_ks_(09|10)"],
    "oral": ["hse_ks_11"],
    "wet_touch": ["hse_ks_1[2-3]"],
    "piston_single_kk": ["hse_ks_1[4-5]"],
    "piston_loop_slow_kk": ["hse_ks_16"],
    "piston_medium_kk": ["hse_ks_17"],
    "piston_loop_fast_kk": ["hse_ks_18"],
    "piston_wet_kk": ["hse_ks_19"],
    "vibrator_kk": ["hse_ks_baibu"],
    "denma": ["hse_ks_denma"],
    "rotor": ["hse_ks_rotor"],
    "squirt_kk": ["hse_ks_siofuki"],
    "massage_start": ["se_ks_est_00"],
    "massage_stroke": ["se_ks_est_01"],
    "massage_end": ["se_ks_est_02"],

    # === Koikatsu Extracted — Environment ===
    "wind": ["se_ks_action_001"],
    "water_flow": ["se_ks_action_002"],
    "cicada": ["se_ks_action_004"],
    "bird": ["se_ks_action_006"],
    "impact": ["se_ks_action_007"],
    "chime": ["se_ks_action_008"],
    "bell": ["se_ks_action_009"],
    "creak": ["se_ks_action_019"],
    "ambient_nature": ["se_ks_action_020"],

    # === Koikatsu Extracted — UI/System ===
    "ui_select": ["se_ks_adv_000"],
    "ui_confirm": ["se_ks_adv_001"],
    "ui_cancel": ["se_ks_adv_002"],
    "text_appear": ["se_ks_adv_003"],
    "notification": ["se_ks_adv_004"],
    "scene_transition": ["se_ks_adv_005"],
    "event_trigger": ["se_ks_adv_007"],
    "item_get": ["se_ks_adv_008"],
    "system_alert": ["se_ks_adv_009"],
}

# Semantic descriptions for LLM tool description (condensed)
TAG_DESCRIPTIONS = {
    "handjob_slow": "ゆっくり手コキ (slow, gentle handjob)",
    "handjob_fast": "速い手コキ (fast, rhythmic handjob)",
    "handjob_irregular": "焦らし手コキ (teasing, irregular rhythm)",
    "handjob_buildup": "手コキ→ラストスパート (buildup to climax)",
    "lotion_apply": "ローション塗布 (applying lotion)",
    "lotion_bottle": "ローション容器 (lotion bottle sounds)",
    "piston_slow": "ゆっくりピストン (slow thrusting)",
    "piston_fast": "激しいピストン (fast, intense thrusting)",
    "piston_wet": "濡れたピストン (wet sounds)",
    "piston_dry": "乾いたピストン (dry skin-on-skin)",
    "ejaculation": "射精音 (ejaculation)",
    "ejaculation_heavy": "大量射精 (heavy ejaculation)",
    "squirt": "潮吹き (squirting)",
    "onahole": "オナホール (onahole sounds)",
    "condom": "コンドーム (condom wrapper/opening)",
    "tissue": "ティッシュ (tissue/cleanup)",
    "bedsheet": "ベッド・布団 (bedsheet rustling)",
    "clothes_rustle": "衣服の音 (clothes rustling/undressing)",
    "zipper": "ファスナー (zipper)",
    "rain": "雨の音 (rain)",
    "rain_heavy": "激しい雨 (heavy rain)",
    "rain_light": "軽い雨 (light rain, loopable)",
    "typing": "タイピング (keyboard typing)",
    "gaming": "ゲーム操作音 (game controller)",
    "bath_water": "入浴 (bath water)",
    "shower": "シャワー (shower)",
    "ear_cleaning": "耳かき (ear cleaning ASMR)",
    "door": "ドア (door open/close)",
    "footstep": "足音 (footsteps)",
    # Koikatsu Extracted
    "kiss_light": "軽いキス (light kiss)",
    "kiss_deep": "ディープキス (deep kiss)",
    "kiss_long": "長いキス (long kiss)",
    "touch_light": "軽い触れ合い (light touch/caress)",
    "lick": "舐める (licking)",
    "suck": "吸う (sucking)",
    "oral": "口でする (oral, slow)",
    "wet_touch": "濡れた触れ合い (wet touch)",
    "piston_single_kk": "単発挿入 (single thrust)",
    "piston_loop_slow_kk": "ゆっくりピストン循環 (slow thrust loop)",
    "piston_medium_kk": "中速ピストン (medium thrust)",
    "piston_loop_fast_kk": "速いピストン循環 (fast thrust loop)",
    "piston_wet_kk": "濡れたピストン (wet thrust)",
    "vibrator_kk": "バイブ (vibrator)",
    "denma": "電マ (electric massager)",
    "rotor": "ローター (rotor vibrator)",
    "squirt_kk": "潮吹き (squirt)",
    "massage_start": "マッサージ開始 (massage start)",
    "massage_stroke": "マッサージ撫で (massage stroke)",
    "massage_end": "マッサージ終了 (massage end)",
    "wind": "風の音 (wind)",
    "water_flow": "水の流れ (flowing water)",
    "cicada": "蝉の声 (cicada)",
    "bird": "鳥の声 (birdsong)",
    "impact": "衝撃音 (impact)",
    "chime": "チャイム (chime)",
    "bell": "鈴の音 (bell)",
    "creak": "きしむ音 (creak)",
    "ambient_nature": "自然の環境音 (nature ambient)",
    "ui_select": "UI選択音 (UI select)",
    "ui_confirm": "UI確認音 (UI confirm)",
    "notification": "通知音 (notification)",
    "scene_transition": "場面転換 (scene transition)",
}
