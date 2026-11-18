import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./AuthContext";
import Navbar from "./components/Navbar";
import Login from "./pages/Login";
import Cases from "./pages/Cases";
import Cameras from "./pages/Cameras";
import CaseView from "./pages/CaseView";

function Guard({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="muted">Loading…</p>;
  return user ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <>
      <Navbar />
      <main className="page">
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<Guard><Cases /></Guard>} />
          <Route path="/cameras" element={<Guard><Cameras /></Guard>} />
          <Route path="/cases/:id/*" element={<Guard><CaseView /></Guard>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </>
  );
}
