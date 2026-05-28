# /mobile-review — VerbBoard Mobile UI/UX Review

You are a staff-level mobile UI/UX engineer reviewing VerbBoard against Android/Material Design 3 and PWA standards. VerbBoard is a vanilla JS + CSS app (no frameworks); all fixes must stay that way.

Invoke the **ui-ux-engineer** agent for any visual design or CSS changes that arise, briefing it with the specific finding.

---

## Context: what's already in place

- Bottom nav (`_bottom_nav.html` + `common.css`): fixed, 56px min-height, shown `<640px`, `env(safe-area-inset-bottom)` padding, RTL `flex-direction: row-reverse`
- Page clearance: `.page, .vb-page { padding-bottom: calc(56px + env(safe-area-inset-bottom)) }`
- Active colour: `#2d6a4f`; tap highlight suppressed via `-webkit-tap-highlight-color: transparent`
- `viewport-fit=cover` added for Opera bottom nav (commit 5863324)
- PWA: `sw.js`, `pwa.js`, manifest present

---

## Review checklist

Work through every section. For each finding report: **file:line**, what the problem is, and the fix. Group by section. Skip sections with no issues.

### 1. Touch targets

- Every tappable element must have a minimum hit area of **48 × 48 dp** (48px on a 1× screen; use `min-height`/`min-width` or `padding` to expand visual elements without changing layout).
- Inline links inside body text are exempt if they sit in a block with adequate line-height.
- Check: bottom nav tabs, audio buttons, known/seen toggles, filter chips, modal close buttons, badge/pill taps, any `<a>` or `<button>` that is iconOnly.
- Spacing between adjacent targets should be ≥ 8dp so mis-taps are rare.

### 2. Safe area insets

Web translation of Android edge-to-edge requirements:

```css
/* viewport meta must include viewport-fit=cover */
/* then use: */
padding-bottom: env(safe-area-inset-bottom);
padding-top:    env(safe-area-inset-top);
padding-left:   env(safe-area-inset-left);
padding-right:  env(safe-area-inset-right);
```

- Status bar: top-fixed headers/banners must pad `env(safe-area-inset-top)`.
- Bottom nav: already padded -- verify no regression.
- Modals/sheets that sit flush to top or bottom must also apply the relevant inset.
- Landscape: left/right insets matter on notched phones (iPhone X landscape, Android with hole-punch at side).
- Check that scrollable content does not clip under the bottom nav on short phones (375 × 667 viewport).

### 3. Gesture navigation conflict zones

Android 10+ swipe-back gesture zone: **~16–20px from left and right edges**. Android home gesture: **bottom ~48px**.

- Horizontal swipe interactions (carousels, swipe-to-dismiss, side drawers) must not start within 20px of screen edges -- add `touch-action: pan-y` or constrain the drag start zone.
- Draggable elements near the bottom: ensure they don't fire before the home gesture resolves.
- Check `sw.js` for any `fetch` intercept on navigation that could conflict with back-navigation.

### 4. Tap responsiveness

- All interactive elements need `touch-action: manipulation` to eliminate the 300ms tap delay on older Android WebView.
- Prefer CSS `:active` over JS `touchstart` for press feedback -- it fires faster and degrades gracefully.
- Press state visual feedback should appear within **100ms**. A simple opacity or background change is enough; avoid layout-triggering properties (no `width`/`height`/`margin` on press).
- State layer (M3 pattern): pressed = 8% primary colour overlay; hover = 4% overlay.

### 5. Typography

Material Design 3 type scale (web equivalents using `rem`/`px` at 16px root):

| Role | Size | Weight | Use |
|------|------|--------|-----|
| Display L/M/S | 57/45/36sp | 400 | Hero text only |
| Headline L/M/S | 32/28/24sp | 400 | Page titles |
| Title L/M/S | 22/16/14sp | 400–500 | Section heads |
| Body L/M/S | 16/14/12sp | 400 | Content |
| Label L/M/S | 14/12/11sp | 500 | Buttons, nav labels, captions |

Rules:
- **Minimum 12sp (12px)** for any visible text; bottom nav labels sit at Label S (11–12sp).
- **Never use `px` for font sizes** in components that users might scale -- prefer `rem` or `em` so system font-size preference is respected.
- Line-height on body text: 1.4–1.6×. Tight line-height (`< 1.3`) on body copy hurts readability on small screens.
- Letter-spacing on all-caps labels: +0.05–0.1em.

### 6. Motion and transitions

M3 motion tokens (map to CSS):

| Token | Duration | Easing | Use |
|-------|----------|--------|-----|
| Short 1 | 50ms | Linear | Fade-in icon, immediate |
| Short 2 | 100ms | Decelerate | Small elements enter |
| Short 3 | 150ms | Accelerate | Small elements exit |
| Short 4 | 200ms | Emphasized decelerate | Most state changes |
| Medium 1 | 250ms | Emphasized | Panel expand |
| Medium 2 | 300ms | Emphasized decelerate | Full-screen enter |
| Long 1 | 350ms | Emphasized | Complex spatial |
| Long 2 | 400ms | Emphasized | Persistent surface |

CSS easing equivalents:
- Emphasised decelerate: `cubic-bezier(0.05, 0.7, 0.1, 1.0)`
- Emphasised accelerate: `cubic-bezier(0.3, 0.0, 0.8, 0.15)`
- Standard: `cubic-bezier(0.2, 0.0, 0, 1.0)`

Rules:
- No `linear` easing on UI transitions -- it reads as mechanical.
- Transitions over 400ms feel sluggish on mobile; anything purely decorative should be ≤ 200ms.
- Always guard motion with `@media (prefers-reduced-motion: reduce) { transition: none }`.
- Page-level transitions (if any): slide in from right for forward navigation, slide out to right for back -- matches Android back gesture expectation.

### 7. Scrolling and overscroll

- `overscroll-behavior: contain` on any overlay, modal, or bottom sheet -- prevents the page behind from scrolling when the user hits the boundary.
- Scrollable lists should use `-webkit-overflow-scrolling: touch` (legacy) and `scroll-behavior: smooth` guarded by `prefers-reduced-motion`.
- Avoid `overflow: hidden` on `<body>` as a modal lock -- it breaks position:fixed on some Android browsers. Use `touch-action: none` on the overlay instead.
- Pull-to-refresh: if not intentionally supported, add `overscroll-behavior-y: contain` on the main scroll container to prevent the browser chrome refresh.

### 8. Keyboard and input

- `font-size` on `<input>` and `<textarea>` must be **≥ 16px** -- below this, iOS Safari (and some Android browsers) auto-zoom the viewport on focus, which breaks the layout.
- Set `inputmode` attributes to reduce keyboard type mismatches: `inputmode="search"` for search fields, `inputmode="email"` for email, etc.
- When the soft keyboard appears, fixed bottom elements (bottom nav, FAB) should slide up with the keyboard or be dismissed. Test by focusing a search input on a 375px viewport.
- `autocomplete`, `autocorrect="off"`, `autocapitalize="off"`, `spellcheck="false"` on verb/language search inputs -- autocorrect mangling verb forms is a bad UX.

### 9. PWA surface

- `manifest.json`: verify `display: "standalone"`, `theme_color` matches the page header background, `background_color` matches the splash screen.
- `<meta name="theme-color">` in every page template -- controls the status bar colour in standalone mode and in Chrome. Should match `--card-bg` or page background, not a hardcoded hex.
- `theme-color` should have a `media="(prefers-color-scheme: dark)"` variant if dark mode is ever supported.
- App icon: at minimum 192×192 and 512×512 maskable icons in the manifest.
- Install prompt: only promote after the user has completed a meaningful session action (e.g., marked a verb known), not on first load.

### 10. Colour and contrast (mobile-specific additions)

- Outdoor readability: test primary text at 4.5:1 against background (WCAG AA). On mobile in bright sunlight effective contrast needs to be higher -- aim for 7:1 on body text where possible.
- Active/selected colour `#2d6a4f` against white: compute contrast. If < 4.5:1, it must not be the sole distinguisher for an active state -- add an icon fill or underline.
- `--text-muted` on inactive nav tabs: ensure still ≥ 3:1 against the nav bar background.
- Never rely on colour alone to convey state -- pair with shape, icon weight, or label change.

### 11. RTL layout on mobile

- Bottom nav already has `flex-direction: row-reverse` for `[dir="rtl"]` -- verify tab order still matches visual order for screen readers.
- Icons that imply direction (back arrow, chevron, list bullet) must mirror in RTL. Use CSS `transform: scaleX(-1)` scoped to `[dir="rtl"]`.
- Swipe gestures in RTL: if forward/back swipes are ever added, reverse their direction.
- Hebrew (`he`) is the primary RTL language -- test the bottom nav and page layouts in that locale.

### 12. Performance on low-end Android

- Avoid animating `box-shadow` -- it triggers paint on every frame. Animate `opacity` + `transform` only (GPU composited).
- `position: fixed` elements (bottom nav, topbar) should have `will-change: transform` if they animate, but remove it when animation is idle (memory cost).
- Large background gradients or blurs on the nav bar can drop frame rate on mid-range devices -- keep them simple.
- Image assets: use `loading="lazy"` on below-fold images; serve WebP with JPEG fallback.
- Avoid `@keyframes` that change `width`, `height`, `top`, `left`, or `margin` -- these cause layout recalc.

---

## How to run this review

1. Identify the scope: pass a file glob, a feature name, or leave blank to review the full `mobile/app-shell` diff vs `main`.
2. Read each changed file in scope.
3. Work through sections 1–12 above, checking each rule against the actual code.
4. Report findings in this format:

```
### [Section name]

**[file:line]** — [what the rule is] / [what the code does wrong]
Fix: [exact CSS or HTML change needed]
```

5. If a fix requires visual judgement (colour, spacing, layout balance), spawn the **ui-ux-engineer** agent with the finding and the relevant file content.

---

## Quick-reference: VerbBoard mobile breakpoint

```
<640px  → mobile shell: bottom nav shown, full-bleed layout
≥640px  → desktop: bottom nav hidden, top nav used
```

All mobile rules above apply within the `<640px` breakpoint unless otherwise noted.
