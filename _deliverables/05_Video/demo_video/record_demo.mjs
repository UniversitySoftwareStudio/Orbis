/**
 * Orbis ENGINEERED demo recorder — drives the real web app through the three
 * use cases with on-screen step labels, for Slide 10.
 *
 * Scenes (each with an injected overlay caption):
 *   0. Login
 *   1. ASK    — open chat EXPANDED, ask, wait for the full cited answer
 *   2. CHECK  — My Regulations → click "Check" → show live matching run
 *   3. SUBMIT — Assignments → open assignment → upload WRONG-content PDF → reject
 *
 * Prereqs (running locally):
 *   - Backend  http://localhost:8000  (api/run.sh)
 *   - Frontend http://localhost:5173  (cd web && npm run dev)
 *   - Seeded demo student wired to everything:
 *       python api/scripts/seed_students.py      (or just the demo functions)
 *   - ./wrong_content_recipe.pdf present (recipe = wrong content → reject)
 *
 * Run:
 *   cd _deliverables/03_Presentation/demo_video
 *   npm i -D playwright && npx playwright install chromium
 *   HEADLESS=false node record_demo.mjs        # watch the first run
 *
 * Output: ./out/page@*.webm (1080p, silent). Convert:
 *   ffmpeg -i out/<file>.webm -c:v libx264 -pix_fmt yuv420p orbis-demo.mp4
 */
import { chromium } from 'playwright';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const EMAIL = process.env.EMAIL || 'a.acar@bilgiedu.net';
const PASSWORD = process.env.PASSWORD || 'demo1234';
const ASK_QUERY = process.env.ASK_QUERY || 'How do I apply for Erasmus?';
const WRONG_PDF = path.join(__dirname, 'wrong_content_recipe.pdf');
const HEADLESS = process.env.HEADLESS !== 'false';
const CHAT_WAIT = Number(process.env.CHAT_WAIT || 16000); // longer wait for RAG answer
const CHECK_WAIT = Number(process.env.CHECK_WAIT || 14000); // regulation check run
const REVIEW_WAIT = Number(process.env.REVIEW_WAIT || 18000); // submission SSE review
const OUT_DIR = path.join(__dirname, 'out');

const beat = (ms = 1200) => new Promise((r) => setTimeout(r, ms));

async function typeSlow(locator, text, delay = 45) {
  await locator.click();
  await locator.fill('');
  await locator.type(text, { delay });
}

/** Inject a styled caption banner into the page so the label is baked into the
 *  recording. step = small kicker, title = the use-case line. */
async function showLabel(page, step, title, accent = '#B7791F') {
  await page.evaluate(
    ({ step, title, accent }) => {
      let el = document.getElementById('orbis-demo-label');
      if (!el) {
        el = document.createElement('div');
        el.id = 'orbis-demo-label';
        el.style.cssText = [
          'position:fixed', 'right:28px', 'bottom:28px',
          'z-index:2147483647', 'background:#000', 'color:#fff',
          'padding:14px 22px', 'border-radius:14px',
          'font-family:Inter,Arial,sans-serif',
          'box-shadow:0 10px 40px rgba(0,0,0,.45)',
          'text-align:left', 'pointer-events:none', 'opacity:0',
          'transition:opacity .4s ease', 'max-width:34vw',
          'border:1px solid rgba(255,255,255,.12)',
        ].join(';');
        document.body.appendChild(el);
      }
      // Red accent draws a left border too, to read as a "warning" callout.
      el.style.borderLeft = `4px solid ${accent}`;
      el.innerHTML =
        `<div style="font-size:13px;letter-spacing:.12em;text-transform:uppercase;color:${accent};font-weight:700">${step}</div>` +
        `<div style="font-size:22px;font-weight:700;margin-top:2px">${title}</div>`;
      requestAnimationFrame(() => { el.style.opacity = '1'; });
    },
    { step, title, accent }
  );
}

async function hideLabel(page) {
  await page.evaluate(() => {
    const el = document.getElementById('orbis-demo-label');
    if (el) el.style.opacity = '0';
  });
}

/** Smoothly zoom into an element (by CSS transform) so its detail is readable,
 *  then optionally reset. Pass selector of the element to magnify. */
async function zoomInto(page, selector, scale = 1.35) {
  await page.evaluate(
    ({ selector, scale }) => {
      const el = document.querySelector(selector);
      if (!el) return;
      el.style.transition = 'transform .6s ease';
      el.style.transformOrigin = 'top right';
      el.style.transform = `scale(${scale})`;
      el.style.zIndex = '500';
      el.style.position = el.style.position || 'relative';
    },
    { selector, scale }
  );
}

async function resetZoom(page, selector) {
  await page.evaluate((selector) => {
    const el = document.querySelector(selector);
    if (el) el.style.transform = 'scale(1)';
  }, selector);
}

async function main() {
  const browser = await chromium.launch({ headless: HEADLESS });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    recordVideo: { dir: OUT_DIR, size: { width: 1920, height: 1080 } },
    deviceScaleFactor: 1,
  });
  // Force English UI BEFORE any page script runs (app reads localStorage
  // 'orbis_lang' at i18n init; default is 'tr'). addInitScript runs on every
  // navigation prior to the page's own JS, so the FIRST render is already EN.
  await context.addInitScript(() => {
    try { localStorage.setItem('orbis_lang', 'en'); } catch {}
  });

  const page = await context.newPage();
  page.setDefaultTimeout(30000);

  try {
    // ── Scene 0: Login ────────────────────────────────────────────────
    // UI is forced to English by the addInitScript above (runs before page JS).
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' });
    await beat(700);
    await typeSlow(page.getByPlaceholder('you@bilgi.edu.tr'), EMAIL);
    await beat(300);
    await typeSlow(page.locator('input[type="password"]'), PASSWORD);
    await beat(400);
    await page.getByRole('button', { name: /sign in|log ?in|giriş/i }).first().click();
    await page.waitForURL(/\/dashboard/, { timeout: 30000 }).catch(() => {});
    await beat(1500);

    // ── Scene 0.5: PAGE TOUR — walk the student pages ─────────────────
    // Quick guided tour of the SIS pages so the video shows the whole app,
    // not only the three AI flows. Each page gets a label + a slow scroll.
    const tour = [
      ['/dashboard', 'Student dashboard'],
      ['/transcript', 'Transcript & GPA'],
      ['/schedule', 'Weekly schedule'],
      ['/courses', 'Enrolled courses'],
      ['/calendar', 'Academic calendar'],
    ];
    for (const [route, title] of tour) {
      await page.goto(`${BASE_URL}${route}`, { waitUntil: 'networkidle' }).catch(() => {});
      await showLabel(page, 'Overview', title);
      await beat(2000); // ~2s per page — quick, per request
      await hideLabel(page);
      await beat(250);
    }
    await page.goto(`${BASE_URL}/dashboard`, { waitUntil: 'networkidle' }).catch(() => {});
    await beat(800);

    // ── Scene 1: ASK (RAG chatbot, expanded, longer wait) ─────────────
    await showLabel(page, 'Use case 1 — Pull', 'Ask: grounded RAG chatbot');
    await beat(1500);
    await page.getByRole('button', { name: /open orbis chat/i }).click();
    await beat(900);
    // Expand to full-page so the answer is clearly readable.
    await page.getByRole('button', { name: /expand/i }).first().click().catch(() => {});
    await beat(900);
    const chatInput = page
      .getByPlaceholder(/ask me about|sor|regulations|campus/i)
      .or(page.locator('input:not([type="password"]):not([type="email"]), textarea').last())
      .first();
    await typeSlow(chatInput, ASK_QUERY);
    await beat(500);
    await chatInput.press('Enter');
    await beat(CHAT_WAIT); // let the streamed, cited answer fully render
    // Shrink + close the widget.
    await page.getByRole('button', { name: /shrink/i }).first().click().catch(() => {});
    await beat(500);
    await page.keyboard.press('Escape').catch(() => {});
    await hideLabel(page);
    await beat(700);

    // ── Scene 2: CHECK (My Regulations, click Check, live run) ────────
    await page.goto(`${BASE_URL}/regulations`, { waitUntil: 'networkidle' });
    await showLabel(page, 'Use case 2 — Push', 'My Regulations: matching rules to my profile');
    await beat(1600);
    // Click the Check / "Kontrol" button to trigger the streaming match.
    const checkBtn = page
      .getByRole('button', { name: /^(check|kontrol)$/i })
      .or(page.locator('button.btn-accent').filter({ hasText: /check|kontrol/i }))
      .first();
    await checkBtn.click({ timeout: 8000 }).catch(async () => {
      await page.locator('button.btn-accent').first().click().catch(() => {});
    });
    // Show that the live check is RUNNING (the streaming run can take a while).
    await showLabel(page, 'Use case 2 — Push', 'Live check running — evaluating every rule against my profile…');
    await beat(CHECK_WAIT);
    // Wait until the check actually finishes (button leaves the "Checking" state).
    await page.getByRole('button', { name: /^(check|kontrol)$/i })
      .waitFor({ state: 'visible', timeout: 25000 }).catch(() => {});
    await beat(1200);
    await hideLabel(page);
    await beat(400);

    // Click back to the "Assigned" tab to see the matched obligations.
    await page.getByRole('button', { name: /^(assigned|atanan)$/i }).first().click({ timeout: 5000 }).catch(() => {});
    await beat(1200);
    await showLabel(page, 'Use case 2 — Push', 'Matched obligations, ranked by urgency');
    await beat(2200);

    // Open the HIGHEST-urgency obligation — the internship rule, which is the
    // most context-dependent match for this student (internship not started).
    const highRule = page
      .getByText(/internship|staj|compulsory|voluntary/i).first()
      .or(page.getByText(/HIGH/i).first());
    await highRule.click({ timeout: 5000 }).catch(() => {});
    await beat(1500);

    // Zoom into the detail pane so its metadata (deadline, trigger, authority,
    // source evidence) is clearly readable. The pane is a sticky-positioned div.
    const detailSel = 'div[style*="sticky"]';
    await zoomInto(page, detailSel, 1.3);
    await beat(800);
    await showLabel(page, '⚠ Quality signal', 'HIGH urgency — and BLOCKING: must act before the deadline', '#B42318');
    await beat(3600);
    await showLabel(page, '⚠ Why this matters', 'This rule fired because my profile says “internship not started” — context-matched, not generic', '#B42318');
    await beat(4000);
    await showLabel(page, 'Metadata', 'Deadline: 10 working days before start · Authority + source evidence shown');
    await beat(3800);
    await showLabel(page, 'Auditable', 'Every obligation cites the exact regulation text it came from — no black-box alerts');
    await beat(3600);
    await resetZoom(page, detailSel);
    await hideLabel(page);
    await beat(600);

    // ── Scene 3: SUBMIT (open assignment, upload wrong PDF → reject) ──
    // Make sure the floating chat widget is CLOSED so its buttons can't be
    // mis-clicked (this caused the previous broken run).
    await page.keyboard.press('Escape').catch(() => {});
    await page.locator('button[aria-label="Close"], .cw-iconbtn').first().click({ timeout: 1500 }).catch(() => {});
    await page.goto(`${BASE_URL}/assignments`, { waitUntil: 'networkidle' });
    await showLabel(page, 'Use case 3 — Review', 'Submission review: wrong file is rejected');
    await beat(1500);

    // Open the assignment by clicking its card button — scoped to the MAIN
    // content (<main>), never the chat widget. Button reads "Submit" (no prior
    // submission) or "View results". We cleared stale submissions, so it's "Submit".
    const main = page.locator('main').first();
    await main.getByRole('button', { name: /^(submit|view results)$/i }).first().click()
      .catch(async () => {
        await main.getByRole('button', { name: /submit/i }).first().click().catch(() => {});
      });
    await beat(1500);

    // The submit pane must now show a hidden file input. Wait for it; if it's
    // missing the open failed, so bail loudly rather than recording a dead scene.
    const fileInput = page.locator('input[type="file"]');
    await fileInput.waitFor({ state: 'attached', timeout: 12000 });
    await fileInput.setInputFiles(WRONG_PDF);
    await beat(1500);

    // Click "Submit for review" to start the SSE evaluation.
    await main.getByRole('button', { name: /submit for review/i }).click();
    await beat(REVIEW_WAIT); // watch requirements + per-requirement findings + REJECT
    await page.mouse.wheel(0, 500);
    await beat(2500);
    await hideLabel(page);
    await beat(1200);
  } finally {
    await context.close();
    await browser.close();
  }
  console.log(`\nDone. Video written to: ${OUT_DIR}`);
}

main().catch((err) => {
  console.error('Recording failed:', err);
  process.exit(1);
});
