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
    "ejaculation": ["射精音"],
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
    "kiss": ["キス", "ちゅ"],
    "slap": ["平手", "ビンタ", "叩"],
    # NOTE: heartbeat, breathing not in current library
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
    "kiss": "キス (kissing)",
}
