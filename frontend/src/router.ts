import { createRouter, createWebHistory, type RouteLocationRaw } from "vue-router";

import { get } from "./api";
import { isPhone, readLastUsed } from "./lastUsed";
import { sharedText } from "./share";
import { useSession } from "./stores/session";

declare module "vue-router" {
  interface RouteMeta {
    /** Reachable without signing in (setup and sign-in). */
    public?: boolean;
  }
}

const first = (v: unknown): string | undefined => {
  const x = Array.isArray(v) ? v[0] : v;
  return typeof x === "string" ? x : undefined;
};

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/setup", component: () => import("./views/SetupView.vue"), meta: { public: true } },
    { path: "/login", component: () => import("./views/LoginView.vue"), meta: { public: true } },
    {
      path: "/",
      component: () => import("./components/AppShell.vue"),
      children: [
        { path: "", name: "home", component: { render: () => null }, beforeEnter: () => homeTarget() },
        // the installed app starts here (manifest start_url): capture in the world last used
        { path: "capture", component: { render: () => null }, beforeEnter: () => captureTarget() },
        // the Android share sheet lands here (manifest share_target)
        {
          path: "share",
          component: { render: () => null },
          beforeEnter: (to) =>
            captureTarget({
              text: sharedText({ title: first(to.query.title), text: first(to.query.text), url: first(to.query.url) }),
              source: "share",
            }),
        },
        { path: "new-world", name: "new-world", component: () => import("./views/NewWorldView.vue") },
        { path: "settings", name: "settings", component: () => import("./views/SettingsView.vue") },
        { path: "w/:world", name: "world", component: () => import("./views/WorldView.vue") },
        { path: "w/:world/capture", name: "capture", component: () => import("./views/CaptureView.vue") },
        { path: "w/:world/inbox", name: "inbox", component: () => import("./views/InboxView.vue") },
        { path: "w/:world/triage", name: "triage", component: () => import("./views/TriageView.vue") },
        { path: "w/:world/decisions", name: "decisions", component: () => import("./views/DecisionsView.vue") },
        { path: "w/:world/journal", name: "journal", component: () => import("./views/JournalView.vue") },
        { path: "w/:world/bible", name: "bible", component: () => import("./views/BibleView.vue") },
        { path: "w/:world/bible/k/:kind", name: "bible-kind", component: () => import("./views/BibleView.vue") },
        { path: "w/:world/bible/types", name: "relation-types", component: () => import("./views/RelationTypesView.vue") },
        { path: "w/:world/bible/:id", name: "entity", component: () => import("./views/EntityView.vue") },
        { path: "w/:world/bible/:id/read", name: "entity-read", component: () => import("./views/ThreadView.vue") },
        { path: "w/:world/checks", name: "checks", component: () => import("./views/ChecksView.vue") },
        { path: "w/:world/graph", name: "graph", component: () => import("./views/GraphView.vue") },
        { path: "w/:world/where", name: "where", component: () => import("./views/WhereView.vue") },
        { path: "w/:world/names", name: "names", component: () => import("./views/NameCheckView.vue") },
        { path: "w/:world/items/:id", name: "item", component: () => import("./views/ItemView.vue") },
        { path: "w/:world/p/:project", name: "project", component: () => import("./views/ProjectView.vue") },
        { path: "w/:world/p/:project/salvage", name: "salvage", component: () => import("./views/SalvageView.vue") },
        { path: "w/:world/p/:project/replace", name: "replace", component: () => import("./views/ReplaceView.vue") },
        { path: "w/:world/chapters/:id", name: "chapter", component: () => import("./views/ChapterView.vue") },
        { path: ":rest(.*)*", name: "not-found", component: () => import("./views/NotFoundView.vue") },
      ],
    },
  ],
});

/** The world last opened on this device, else the first one. */
function currentWorld() {
  const s = useSession();
  const last = readLastUsed();
  return (last.world && s.world(last.world)) || s.worlds[0];
}

/**
 * Where "/" leads. On a phone: capture, in the world last used. At the desk: the world (and project) last opened on
 * this device, else the first world. Without any world: making one.
 */
export function homeTarget(phone = isPhone()): RouteLocationRaw {
  const s = useSession();
  const last = readLastUsed();
  const world = currentWorld();
  if (!world) return { name: "new-world" };
  if (phone) return { name: "capture", params: { world: world.slug } };
  if (last.world === world.slug && last.project && s.project(world.slug, last.project)) {
    return { name: "project", params: { world: world.slug, project: last.project } };
  }
  return { name: "world", params: { world: world.slug } };
}

export function captureTarget(query: { text?: string; source?: string } = {}): RouteLocationRaw {
  const world = currentWorld();
  if (!world) return { name: "new-world" };
  const q = Object.fromEntries(Object.entries(query).filter(([, v]) => v));
  return { name: "capture", params: { world: world.slug }, query: q };
}

router.beforeEach(async (to) => {
  if (to.meta.public) return true;
  const s = useSession();
  if (s.me) return true;
  try {
    if (await s.load()) return true;
    const setup = await get<{ needed: boolean }>("/api/setup");
    if (setup.needed) return { path: "/setup" };
  } catch {
    /* no network and nothing saved on this device: the sign-in page explains */
  }
  return { path: "/login", query: to.fullPath === "/" ? {} : { next: to.fullPath } };
});
