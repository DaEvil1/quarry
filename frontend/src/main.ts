import { createPinia } from "pinia";
import { createApp } from "vue";

import App from "./App.vue";
import { router } from "./router";
import { persistStorage } from "./offline";
import { useOutbox } from "./stores/outbox";
import "./styles/app.css";

const app = createApp(App).use(createPinia()).use(router);
// send captures saved offline as soon as there is a connection
useOutbox().watch();
// ask the browser to keep the offline copy even when space runs low
void persistStorage();
app.mount("#app");
