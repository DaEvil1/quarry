// Phase 1 from first run to signing back in: setup with a passkey, a world and projects, sign out, sign in with
// the passkey, then with a recovery code. Runs against an empty database; the steps depend on each other.

import { expect, test, type Page } from "@playwright/test";

const SETUP_TOKEN = process.env.E2E_SETUP_TOKEN ?? "e2e-setup-token";

test.describe.configure({ mode: "serial" });

let page: Page;
let recoveryCode = "";

test.beforeAll(async ({ browser }) => {
  page = await browser.newPage();
  // a platform authenticator that always verifies the user, like a phone's fingerprint prompt
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("WebAuthn.enable");
  await cdp.send("WebAuthn.addVirtualAuthenticator", {
    options: {
      protocol: "ctap2",
      transport: "internal",
      hasResidentKey: true,
      hasUserVerification: true,
      isUserVerified: true,
      automaticPresenceSimulation: true,
    },
  });
});

test.afterAll(async () => {
  await page.close();
});

test("first run sends you to setup and creates a passkey", async () => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/setup$/);
  await page.getByLabel("Setup token").fill(SETUP_TOKEN);
  await page.getByLabel("Your name").fill("Test Writer");
  await page.getByLabel("Name for this device's passkey").fill("Test laptop");
  await page.getByRole("button", { name: "Create passkey" }).click();

  const codes = page.getByTestId("recovery-codes");
  await expect(codes.locator("span")).toHaveCount(10);
  recoveryCode = (await codes.locator("span").first().textContent())?.trim() ?? "";
  expect(recoveryCode).toMatch(/^[A-Z0-9]{5}-[A-Z0-9]{5}$/);
  await page.getByTestId("codes-saved").click();
  await expect(page.getByRole("heading", { name: "Create your first world" })).toBeVisible();
});

test("create a world with a first project", async () => {
  await page.getByLabel("World name").fill("The Grey Coast");
  await page.getByLabel("First project").fill("First Light");
  await page.getByLabel("Kind").selectOption("novella");
  await page.getByRole("button", { name: "Create world" }).click();
  await expect(page).toHaveURL(/\/w\/the-grey-coast\/p\/first-light$/);
  await expect(page.getByRole("heading", { name: "First Light" })).toBeVisible();
  await expect(page.locator(".crumbs")).toContainText("Novella");
});

test("add, reorder and rename", async () => {
  await page.locator(".nav").getByRole("link", { name: "Overview" }).click();
  await expect(page.getByRole("heading", { name: "The Grey Coast" })).toBeVisible();
  await page.getByLabel("Name", { exact: true }).fill("Ebb Tide");
  await page.getByRole("button", { name: "Add project" }).click();
  const rows = page.locator("ul.rows > li");
  await expect(rows).toHaveCount(2);
  await page.getByRole("button", { name: "Move Ebb Tide up" }).click();
  await expect(rows.first()).toContainText("Ebb Tide");
  // the nav follows the new order
  await expect(page.locator(".nav nav a").nth(1)).toContainText("Ebb Tide");

  await page.getByRole("button", { name: "Rename" }).click();
  await page.getByLabel("Name", { exact: true }).first().fill("The Grey Shore");
  await page.getByLabel("Address").fill("grey-shore");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page).toHaveURL(/\/w\/grey-shore$/);
  await expect(page.getByRole("heading", { name: "The Grey Shore" })).toBeVisible();
  await expect(page.getByTestId("world-switcher").first()).toContainText("The Grey Shore");
});

test("sign out, then back in with the passkey to where you were", async () => {
  await page.locator(".nav").getByRole("link", { name: "First Light" }).click();
  await expect(page.getByRole("heading", { name: "First Light" })).toBeVisible();
  await page.locator(".nav-foot").getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/settings");
  await expect(page).toHaveURL(/\/login\?next=(%2F|\/)settings$/);
  await page.goto("/login");
  await page.getByTestId("sign-in").click();
  await expect(page).toHaveURL(/\/w\/grey-shore\/p\/first-light$/);
});

test("settings lists the passkey; a recovery code also signs in", async () => {
  await page.goto("/settings");
  await expect(page.getByTestId("passkey-list")).toContainText("Test laptop");
  await expect(page.getByText("10 unused")).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).first().click();
  await expect(page).toHaveURL(/\/login$/);

  await page.getByRole("button", { name: "Lost your passkey?" }).click();
  await page.getByLabel("Recovery code").fill(recoveryCode);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/settings\?recovered=1$/);
  await expect(page.getByText("You signed in with a recovery code")).toBeVisible();
  await expect(page.getByText("9 unused")).toBeVisible();
});

test("on a phone the nav becomes a top bar and tabs", async () => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/w/grey-shore");
  await expect(page.locator(".nav")).toBeHidden();
  await expect(page.locator(".tabbar")).toBeVisible();
  await expect(page.locator(".topbar").getByTestId("world-switcher")).toContainText("The Grey Shore");
  await page.locator(".tabbar").getByRole("link", { name: "Settings" }).click();
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  // nothing scrolls sideways at phone width
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
