# UI Redesign Phase 1: Rose Dusk Theme + Fullscreen Layout

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the UI from current pink-on-dark to rose dusk theme with fullscreen VRM character and overlay chat.

**Architecture:** Rewrite CSS in-place in index.html. Restructure layout from flex column (VRM top / chat bottom) to absolute positioning (VRM fullscreen / chat overlay right). All JS functionality preserved, only visual layer changes.

**Tech Stack:** CSS3 (backdrop-filter, gradients, animations), HTML structure changes in index.html

---

### Task 1: CSS Color Variables + Base Theme

Replace all hardcoded colors with CSS custom properties for the rose dusk palette.

**Files:**
- Modify: `server/static/index.html` (CSS section, lines 7-250)

- [ ] **Step 1: Add CSS variables at top of style block**

- [ ] **Step 2: Replace body/background colors**

- [ ] **Step 3: Replace all #FF69B4 references with var(--accent)**

- [ ] **Step 4: Replace all #FFB6C1 with var(--text-primary)**

- [ ] **Step 5: Verify page loads, commit**

---

### Task 2: Layout Restructure — Fullscreen VRM + Overlay Chat

Change from flex column to absolute positioning.

**Files:**
- Modify: `server/static/index.html` (CSS + HTML structure)

- [ ] **Step 1: Change #vrm-container to position absolute fullscreen**

- [ ] **Step 2: Add gradient overlay div for chat readability**

- [ ] **Step 3: Change #chat-panel to absolute positioned right overlay**

- [ ] **Step 4: Move #top-bar to floating capsule style**

- [ ] **Step 5: Move #input-bar to floating capsule at bottom**

- [ ] **Step 6: Verify layout, commit**

---

### Task 3: Chat Bubble Restyling

Apply gradient shadow style to all message bubbles.

**Files:**
- Modify: `server/static/index.html` (CSS .msg rules)

- [ ] **Step 1: Restyle .msg.user with gradient + shadow**

- [ ] **Step 2: Restyle .msg.ai with gradient + rose border + shadow**

- [ ] **Step 3: Update emotion tag, timing badge, TTS button colors**

- [ ] **Step 4: Update plan-card, notice, error styles**

- [ ] **Step 5: Verify chat display, commit**

---

### Task 4: Setup Page Restyling

Apply rose dusk theme to setup screen.

**Files:**
- Modify: `server/static/index.html` (CSS #setup-screen, .setup-card)

- [ ] **Step 1: Update setup-screen gradient background**

- [ ] **Step 2: Restyle setup-card with glass effect**

- [ ] **Step 3: Restyle buttons (test, enter) with rose gradient**

- [ ] **Step 4: Restyle select/input elements**

- [ ] **Step 5: Restyle test result badges**

- [ ] **Step 6: Verify setup page, commit**

---

### Task 5: Settings Modal + Lightbox Restyling

**Files:**
- Modify: `server/static/index.html` (CSS modal, tabs, lightbox)

- [ ] **Step 1: Update modal-content background and border**

- [ ] **Step 2: Restyle tab buttons as pills**

- [ ] **Step 3: Update lightbox overlay to match theme**

- [ ] **Step 4: Verify settings and lightbox, commit**

---

### Task 6: Animations + Scrollbar + Polish

**Files:**
- Modify: `server/static/index.html` (CSS animations, scrollbar, transitions)

- [ ] **Step 1: Add bubble appear animation (slide-up + fade)**

- [ ] **Step 2: Update scrollbar to rose theme**

- [ ] **Step 3: Add hover transitions for controls**

- [ ] **Step 4: Final visual polish pass**

- [ ] **Step 5: Commit**
