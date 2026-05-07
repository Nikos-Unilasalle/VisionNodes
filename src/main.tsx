import React from "react";
import ReactDOM from "react-dom/client";
import { ReactFlowProvider } from "reactflow";
import App from "./App";
import PopoutPreview from "./PopoutPreview";
import "./index.css";

const isPopout = new URLSearchParams(window.location.search).get('popout') === '1';

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    {isPopout ? (
      <PopoutPreview />
    ) : (
      <ReactFlowProvider>
        <App />
      </ReactFlowProvider>
    )}
  </React.StrictMode>,
);
