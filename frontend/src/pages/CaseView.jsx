import { useEffect, useState } from "react";
import { Link, NavLink, Route, Routes, useParams } from "react-router-dom";
import api from "../api";
import TimelineTab from "./TimelineTab";
import EvidenceTab from "./EvidenceTab";
import ReportTab from "./ReportTab";

export default function CaseView() {
  const { id } = useParams();
  const [c, setC] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { api.get(`/cases/${id}`).then((r) => setC(r.data)).catch(() => setError("Case not found")); }, [id]);

  if (error) return <div className="alert error">{error} <Link to="/">Back to cases</Link></div>;
  if (!c) return <p className="muted">Loading…</p>;

  return (
    <>
      <p className="noprint"><Link to="/">← All cases</Link></p>
      <h1>{c.title}</h1>
      {c.description && <p className="muted case-desc">{c.description}</p>}
      <nav className="tabs noprint">
        <NavLink to={`/cases/${id}`} end>Timeline and map</NavLink>
        <NavLink to={`/cases/${id}/evidence`}>Evidence</NavLink>
        <NavLink to={`/cases/${id}/report`}>Report</NavLink>
      </nav>
      <Routes>
        <Route index element={<TimelineTab caseId={id} />} />
        <Route path="evidence" element={<EvidenceTab caseId={id} />} />
        <Route path="report" element={<ReportTab caseId={id} caseInfo={c} />} />
      </Routes>
    </>
  );
}
