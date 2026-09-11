import { Route, BrowserRouter, Routes } from "react-router-dom";
import Editor from "./Editor";
import Landing from "./Landing";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/app" element={<Editor />} />
        <Route path="*" element={<Landing />} />
      </Routes>
    </BrowserRouter>
  );
}
