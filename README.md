# Hop Rush 🐔

A Crossy Road–style endless hopper, built with plain HTML/CSS/JS and [Three.js](https://threejs.org/) (loaded from a CDN, no build step required).

Hop across roads and rivers, dodge traffic, ride logs, and see how far you can get. Your best score is saved locally in the browser.

## Controls
- **Desktop:** Arrow keys or WASD
- **Mobile:** Swipe, or use the on-screen D-pad

## Run locally

No build tools needed — it's a single static HTML file. Just serve the folder:

```bash
npx serve .
# or
python3 -m http.server 8000
```

Then open the printed URL in your browser.

## Deploy to Vercel

### Option A — Vercel CLI (fastest)
```bash
npm i -g vercel
cd hop-rush
vercel
```
Follow the prompts (accept the defaults — it's a static site, no build command needed) and Vercel will give you a live URL.

### Option B — GitHub + Vercel dashboard
1. Push this folder to a new GitHub repo.
2. Go to [vercel.com/new](https://vercel.com/new), import the repo.
3. Framework preset: **Other** (static). Leave build command empty, output directory as root (`.`).
4. Click **Deploy**.

That's it — `index.html` is served as-is with no build step.

## Files
- `index.html` — the entire game (markup, styles, and game logic)
- `vercel.json` — minimal Vercel static-hosting config
