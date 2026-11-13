import ReactDOM from "react-dom/client";
import { App } from "./App";

// StrictMode is intentionally disabled: TipTap's Collaboration extension
// uses y-prosemirror which accesses fragment.doc synchronously during
// plugin construction. StrictMode's double-invocation destroys the Y.Doc
// between the two renders, leaving a detached XmlFragment whose .doc is
// undefined — crashing on "Cannot read properties of undefined (reading 'doc')".
// This is a known incompatibility between y-prosemirror and React 18 StrictMode.
ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
