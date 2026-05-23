import { expect, type Locator, type Page } from "playwright/test";

declare global {
  interface Window {
    __moveDemoCursor?: (x: number, y: number, duration?: number) => void;
    __pulseDemoCursor?: () => void;
  }
}

export async function pause(page: Page, ms = 100) {
  await page.waitForTimeout(ms);
}

export async function installDemoCursor(page: Page) {
  await page.addStyleTag({
    content: `
      [data-demo-cursor] {
        position: fixed;
        left: 0;
        top: 0;
        z-index: 2147483647;
        width: 22px;
        height: 22px;
        border: 2px solid #2563eb;
        border-radius: 9999px;
        background: rgba(255, 255, 255, 0.82);
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.28);
        pointer-events: none;
        transform: translate3d(-80px, -80px, 0);
        transition:
          transform var(--demo-cursor-duration, 100ms) cubic-bezier(0.22, 1, 0.36, 1),
          background 90ms ease,
          box-shadow 90ms ease;
        will-change: transform;
      }

      [data-demo-cursor]::after {
        content: "";
        position: absolute;
        inset: 7px;
        border-radius: 9999px;
        background: #2563eb;
      }

      [data-demo-cursor].is-clicking {
        background: rgba(219, 234, 254, 0.95);
        box-shadow: 0 4px 16px rgba(37, 99, 235, 0.35);
      }
    `
  });
  await page.evaluate(() => {
    const existing = document.querySelector("[data-demo-cursor]");
    const cursor = existing ?? document.createElement("div");
    cursor.setAttribute("data-demo-cursor", "true");
    if (!existing) document.body.appendChild(cursor);

    window.__moveDemoCursor = (x: number, y: number, duration = 60) => {
      const cursorElement = cursor as HTMLElement;
      cursorElement.style.setProperty("--demo-cursor-duration", `${Math.max(duration, 0)}ms`);
      cursorElement.style.transform = `translate3d(${x - 11}px, ${y - 11}px, 0)`;
    };
    window.__pulseDemoCursor = () => {
      cursor.classList.add("is-clicking");
      window.setTimeout(() => cursor.classList.remove("is-clicking"), 110);
    };
  });
}

async function centerOf(locator: Locator) {
  await expect(locator).toBeVisible();
  return locator.evaluate((element) => {
    const box = element.getBoundingClientRect();
    if (!box.width || !box.height) throw new Error("Could not find locator position for demo cursor.");
    return {
      x: box.left + box.width / 2,
      y: box.top + box.height / 2
    };
  });
}

export async function moveCursorTo(page: Page, locator: Locator, ms = 45) {
  const point = await centerOf(locator);
  await page.evaluate(
    ({ x, y, duration }) => window.__moveDemoCursor?.(x, y, duration),
    { ...point, duration: ms }
  );
  await pause(page, ms);
}

export async function clickWithCursor(page: Page, locator: Locator, ms = 45) {
  const point = await centerOf(locator);
  await page.evaluate(
    ({ x, y, duration }) => window.__moveDemoCursor?.(x, y, duration),
    { ...point, duration: ms }
  );
  await pause(page, ms);
  await page.evaluate(() => window.__pulseDemoCursor?.());
  await locator.evaluate((element) => {
    if (element instanceof HTMLElement) {
      element.click();
    }
  });
  await pause(page, 25);
}

export async function fillByLabel(page: Page, label: string, value: string) {
  const field = page.getByLabel(label);
  if ((await field.inputValue()).trim()) return;
  await moveCursorTo(page, field, 35);
  await field.fill(value);
  await pause(page, 25);
}

export async function chooseVisibleSelectOption(page: Page, option: string) {
  await clickWithCursor(page, page.getByRole("button", { name: /select/i }).first());
  await clickWithCursor(page, page.getByRole("button", { name: option, exact: true }));
}

export async function checkOption(page: Page, label: string) {
  const checkbox = page.getByLabel(label);
  if (!(await checkbox.isChecked())) {
    await clickWithCursor(page, checkbox, 40);
  }
}

export async function clickNext(page: Page) {
  await clickWithCursor(page, page.getByRole("button", { name: "Next" }));
  await pause(page, 80);
}

export async function expectVisible(locator: Locator) {
  await expect(locator).toBeVisible();
}

export async function resetDemoBrowserState(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });
}
