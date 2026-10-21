import { createRouter, createWebHistory, type RouteLocationRaw } from "vue-router";

import { get } from "./api";
import { readLastUsed } from "./lastUsed";
import { useSession } from "./stores/session";

declare module "vue-router" {
  interface RouteMeta {
    /** Reachable without signing in (setup and sign-in). */
    public?: boolean;
  }
}

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
        { path: "new-world", name: "new-world", component: () => import("./views/NewWorldView.vue") },
        { path: "settings", name: "settings", component: () => import("./views/SettingsView.vue") },
        { path: "w/:world", name: "world", component: () => import("./views/WorldView.vue") },
        { path: "w/:world/p/:project", name: "project", component: () => import("./views/ProjectView.vue") },
        { path: ":rest(.*)*", name: "not-found", component: () => import("./views/NotFoundView.vue") },
      ],
    },
  ],
});

/** Where "/" leads: the world (and project) last opened on this device, else the first world, else a new one. */
export function homeTarget(): RouteLocationRaw {
  const s = useSession();
  const last = readLastUsed();
  const world = (last.world && s.world(last.world)) || s.worlds[0];
  if (!world) return { name: "new-world" };
  if (last.world === world.slug && last.project && s.project(world.slug, last.project)) {
    return { name: "project", params: { world: world.slug, project: last.project } };
  }
  return { name: "world", params: { world: world.slug } };
}

router.beforeEach(async (to) => {
  if (to.meta.public) return true;
  const s = useSession();
  if (s.me || (await s.load())) return true;
  const setup = await get<{ needed: boolean }>("/api/setup");
  if (setup.needed) return { path: "/setup" };
  return { path: "/login", query: to.fullPath === "/" ? {} : { next: to.fullPath } };
});
