import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { errMsg } from "../api";

export default function Login() {
  const { user, loading, login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  if (!loading && user) return <Navigate to="/" replace />;

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    try { await login(email, password); nav("/"); } catch (err) { setError(errMsg(err)); }
  };

  return (
    <div className="login">
      <div>
        <h1>See how an incident unfolded.</h1>
        <p className="lead">Upload footage from CCTV, traffic and bus cameras and citizen photos. TraceLens detects people and vehicles, follows them across cameras, and lays the sightings out on a timeline and a map.</p>
      </div>
      <form className="card form" onSubmit={submit}>
        <h2>Investigator sign in</h2>
        {error && <div className="alert error">{error}</div>}
        <label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus /></label>
        <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
        <button className="btn">Sign in</button>
      </form>
    </div>
  );
}
