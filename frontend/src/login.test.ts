import "fake-indexeddb/auto";

import { flushPromises, mount } from "@vue/test-utils";
import { createPinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const replace = vi.fn();
vi.mock("vue-router", () => ({ useRoute: () => ({ query: { next: "/w/coast" } }), useRouter: () => ({ replace }) }));
// the page's logo is an asset import that only the dev server and the build can resolve
vi.mock("/favicon.svg", () => ({ default: "/favicon.svg" }));
vi.mock("./passkey", () => ({ passkeysSupported: () => true, promptError: () => null, runSignIn: vi.fn() }));

import { localDb } from "./localdb";
import LoginView from "./views/LoginView.vue";

const me = { user: { id: "u", display_name: "Writer" }, worlds: [] };
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const badGateway = () => new Response("<html>Bad Gateway</html>", { status: 502 });

beforeEach(async () => {
  await localDb.kv.clear();
  replace.mockReset();
});
afterEach(() => vi.unstubAllGlobals());

async function settle() {
  for (let i = 0; i < 5; i++) await flushPromises();
}

describe("the sign-in page while the server can't be reached", () => {
  it("says the server may be restarting, and opens the app once it answers", async () => {
    let restarting = true;
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(restarting ? badGateway() : json(200, me))));
    const w = mount(LoginView, { global: { plugins: [createPinia()] } });
    await settle();
    expect(w.text()).toMatch(/may be restarting/);
    expect(w.text()).not.toMatch(/hasn't signed in/);
    restarting = false;
    // it also tries every few seconds; coming back online is the quicker way to make it try again here
    window.dispatchEvent(new Event("online"));
    await settle();
    expect(replace).toHaveBeenCalledWith("/w/coast");
    w.unmount();
  });

  it("without a network, says so and doesn't claim the device never signed in", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))));
    const w = mount(LoginView, { global: { plugins: [createPinia()] } });
    await settle();
    expect(w.text()).toMatch(/can't reach the server/);
    expect(w.text()).not.toMatch(/hasn't signed in/);
    w.unmount();
  });

  it("shows the sign-in button without an error once the server says nobody is signed in", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) =>
      Promise.resolve(url === "/api/me" ? json(401, { detail: "Sign in to continue." }) : json(200, { needed: false }))));
    const w = mount(LoginView, { global: { plugins: [createPinia()] } });
    await settle();
    expect(w.find("[role=alert]").exists()).toBe(false);
    expect(replace).not.toHaveBeenCalled();
    w.unmount();
  });
});
