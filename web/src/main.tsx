import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "./shared/theme/global.css";
import { App } from "./app/App";
import { applyTheme } from "./shared/theme/applyTheme";

applyTheme();
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
