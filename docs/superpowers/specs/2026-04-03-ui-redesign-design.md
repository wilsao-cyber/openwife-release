# UI/UX Redesign — 玫瑰暮色主題 + 全屏沉浸

**Date:** 2026-04-03
**Status:** Approved

---

## 1. Design Decisions (User-Selected)

| 項目 | 選擇 |
|------|------|
| 色彩主題 | **玫瑰暮色** — `#1c1e2a` 深灰藍底 + `#d4a5a5` 乾燥玫瑰 + `#f2d7d5` 淡粉文字 |
| 佈局 | **角色全屏 + 聊天覆蓋** — VRM 角色佔滿背景，聊天從右側半透明漸層覆蓋 |
| 氣泡 | **漸層陰影** — 深色漸層背景 + 柔和 box-shadow + AI 氣泡左側玫瑰色邊線 |
| 控制列 | **浮動膠囊** — 半透明 backdrop-filter blur 圓角膠囊，浮在角色上方 |

---

## 2. Color Palette

```
Primary BG:     #1c1e2a  (深灰藍)
Secondary BG:   #2a2d3e  (中灰藍)
Accent:         #d4a5a5  (乾燥玫瑰)
Accent Light:   #e6c4c0  (淡玫瑰)
Text Primary:   #f2d7d5  (淡粉白)
Text Secondary: #888      (灰)
User Bubble:    linear-gradient(135deg, #3a2d3e, #2a2d3e)
AI Bubble:      linear-gradient(135deg, #2a2d3e, #1c1e2a)
AI Border:      #d4a5a5 (left 2px)
Glass:          rgba(42, 45, 62, 0.5) + backdrop-filter: blur(12px)
Send Button:    linear-gradient(135deg, #d4a5a5, #e6c4c0)
```

---

## 3. Layout Architecture

### Main View (聊天模式)
```
┌─────────────────────────────┐
│ [🌸 小愛] [自動][繁中][🔊][⚙️]│  ← 浮動膠囊控制列 (top-left)
│                             │
│         3D VRM 角色          │  ← 全屏 canvas
│        (全屏背景)            │
│                             │
│              ┌──────────────│
│              │  聊天訊息     │  ← 右側 55% 寬，漸層覆蓋
│              │  (漸層覆蓋)   │
│              │              │
│              └──────────────│
│ [🎤] [輸入訊息...        ] [➤]│  ← 浮動膠囊輸入框 (bottom)
└─────────────────────────────┘
```

- VRM canvas: `position: absolute; inset: 0;`
- 聊天區: `position: absolute; right: 0; width: 55%; max-width: 450px;` with left gradient fade
- 控制列: `position: absolute; top: 12px; left: 12px;`
- 輸入框: `position: absolute; bottom: 12px; left: 12px; right: 12px;`
- All overlays use `backdrop-filter: blur(12px)` + glass background

### Setup Page
- 保持現有 card 佈局
- 套用玫瑰暮色配色
- 圓角加大到 16px
- 按鈕用漸層玫瑰色

### Settings Modal
- 套用玫瑰暮色配色
- Tab 按鈕改為膠囊樣式

---

## 4. Component Styles

### Chat Bubbles
- **User**: `background: linear-gradient(135deg, #3a2d3e, #2a2d3e)`, rounded 18px, shadow
- **AI**: `background: linear-gradient(135deg, #2a2d3e, #1c1e2a)`, `border-left: 2px solid #d4a5a5`, rounded 18px, shadow
- **Emotion tag**: small text above AI message, color `#d4a5a5`
- **Timing badge**: `color: #888`, smaller font
- **TTS/JA buttons**: inline after timing, muted until hover

### Floating Controls (Top)
- `background: rgba(42, 45, 62, 0.5)`
- `backdrop-filter: blur(12px)`
- `border-radius: 20px`
- `border: 1px solid rgba(212, 165, 165, 0.08)`
- Each control as pill: `padding: 2px 8px; background: rgba(212, 165, 165, 0.1); border-radius: 10px`

### Floating Input (Bottom)
- Same glass style as top controls
- `border-radius: 24px`
- Mic button on left
- Send button: gradient circle `#d4a5a5 → #e6c4c0` with shadow

### Plan Card (Assist Mode)
- Glass background matching theme
- `border-left: 2px solid #d4a5a5`
- Confirm/Deny buttons in pill style

### Media Thumbnails
- Same rounded corners (8px)
- Subtle shadow
- Hover: slight scale transform

### Lightbox
- Background: `rgba(28, 30, 42, 0.95)` (matching theme, not pure black)
- Close button in `#d4a5a5`

---

## 5. Scene Backgrounds

### 5.1 Scene Types
4 switchable background scenes behind the VRM character:

| Scene | Description | Technical |
|-------|------------|-----------|
| 🏠 居家 | 溫馨臥室/客廳，暖色調 | HDR environment map or skybox cubemap |
| 🌸 櫻花 | 櫻花樹下公園，粉色氛圍 | HDR environment map |
| ✨ 奇幻 | 星空浮島，紫色魔幻 | HDR environment map |
| 🌃 夜景 | 都市陽台夜景，霓虹燈火 | HDR environment map |

### 5.2 Implementation
- Use Three.js `scene.background` with `CubeTextureLoader` or `RGBELoader` for HDR
- Provide fallback: CSS gradient background if HDR not loaded
- Scene selector in settings or as quick-switch pills in top control bar
- HDR files stored in `server/static/environments/`
- First load downloads from CDN (Poly Haven or similar free HDR sources)

### 5.3 Rendering Enhancements
- **Environment lighting**: HDR map also used as `scene.environment` for PBR lighting on VRM model
- **Post-processing**: optional bloom effect for glow (especially night/fantasy scenes)
- **Ambient occlusion**: subtle SSAO for depth
- **Tone mapping**: ACESFilmicToneMapping for cinematic look

### 5.4 CSS Fallback Gradients
When HDR not loaded, use CSS gradients on canvas container:
- 🏠 居家: `linear-gradient(180deg, #2a2520 0%, #1a1815 100%)`
- 🌸 櫻花: `linear-gradient(180deg, #2a1f2a 0%, #1a1520 100%)`
- ✨ 奇幻: `linear-gradient(180deg, #1a1a30 0%, #0f0f20 100%)`
- 🌃 夜景: `linear-gradient(180deg, #1a1e2a 0%, #0f1218 100%)`

---

## 6. Animations & Transitions

- Page transitions: fade 0.3s
- Bubble appear: slide-up 0.2s + fade
- Control hover: scale 1.05, 0.15s
- Lightbox open/close: fade + scale 0.2s
- Scene switch: crossfade 0.5s
- Scrollbar: thin, rose-colored thumb

---

## 7. Setup Page Redesign

- Same glass card style
- Background: subtle animated gradient (玫瑰暮色 colors slowly shifting)
- Title: 🌸 in larger decorative font
- Test results: pill badges instead of plain text
- Enter button: gradient rose with glow effect on hover
- Provider/model selects: styled to match theme

---

## 8. Responsive Considerations

- **Desktop (>1024px)**: chat panel 55% width on right
- **Tablet (768-1024px)**: chat panel 65% width
- **Mobile (<768px)**: chat panel full width, swipe to show/hide character
- Controls and input always visible
- Font sizes scale with viewport
