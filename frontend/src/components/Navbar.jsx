import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";

const Logo = () => (
  <svg width="26" height="26" viewBox="0 0 100 100" aria-hidden="true">
    <circle cx="44" cy="44" r="28" fill="none" stroke="#2fd3e6" strokeWidth="9" />
    <path d="M24 52 L38 40 L48 48 L62 34" fill="none" stroke="#2fd3e6" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M66 66 L88 88" stroke="#2fd3e6" strokeWidth="11" strokeLinecap="round" />
  </svg>
);

export default function Navbar() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  return (
    <header className="nav">
      <div className="nav-inner">
        <Link to="/" className="brand"><Logo /> Trace<b>Lens</b> AI</Link>
        {user && (
          <nav className="nav-links">
            <NavLink to="/" end>Cases</NavLink>
            <NavLink to="/cameras">Cameras</NavLink>
          </nav>
        )}
        {user && (
          <div className="nav-user">
            <span>{user.name}</span>
            <button className="btn ghost small" onClick={async () => { await logout(); nav("/login"); }}>Log out</button>
          </div>
        )}
      </div>
    </header>
  );
}
