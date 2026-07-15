import { useState, useMemo, useCallback } from "react";

// ── Full course dataset (synced with courses.json) ──────────────────────────
const COURSES = {
  "DATA C8":       { units:4, terms:["Fall","Spring"], prereqs:null, rating:3.5, difficulty:3.1, topics:{python:0.5,statistics:0.5}, instructors:["John DeNero"] },
  "DATA C88C":     { units:3, terms:["Fall","Spring"], prereqs:null, rating:4.3, difficulty:2.8, topics:{python:0.4,algorithm:0.3,statistics:0.3}, instructors:["John DeNero"] },
  "DATA C100":     { units:4, terms:["Fall","Spring"], prereqs:{and:[{or:["DATA C8","STAT 20"]},{or:["COMPSCI 61A","DATA C88C","ENGIN 7"]}]}, rating:5.0, difficulty:2.8, topics:{python:0.4,statistics:0.4,algorithm:0.2}, instructors:["Joseph Gonzalez"] },
  "DATA C101":     { units:4, terms:["Fall","Spring"], prereqs:{and:[{or:["COMPSCI 61B","INFO 206B"]},{or:["DATA C100","COMPSCI 189","DATA 144"]}]}, rating:3.8, difficulty:4.0, topics:{statistics:0.4,algorithm:0.4,python:0.2}, instructors:["Lisa Yan"] },
  "DATA C102":     { units:4, terms:["Fall","Spring"], prereqs:{and:[{or:["MATH 54","MATH 56"]},"DATA C100",{or:["DATA C140","STAT 134"]}]}, rating:4.3, difficulty:3.0, topics:{statistics:0.4,math:0.3,algorithm:0.3}, instructors:["Fernando Perez"] },
  "DATA C104":     { units:4, terms:["Fall","Spring"], prereqs:null, rating:3.5, difficulty:2.9, topics:{python:0.6,statistics:0.4}, instructors:["Cathryn Carson"] },
  "DATA 144":      { units:3, terms:["Fall","Spring"], prereqs:null, rating:1.7, difficulty:3.5, topics:{statistics:0.6,python:0.4}, instructors:["TBA"] },
  "DATA C140":     { units:4, terms:["Fall","Spring"], prereqs:{and:[{or:["DATA C8","STAT 20"]},{or:["COMPSCI 61A","DATA C88C"]},{and:["MATH 51","MATH 52"]}]}, rating:5.0, difficulty:3.0, topics:{statistics:0.5,math:0.4,algorithm:0.1}, instructors:["Ani Adhikari"] },
  "COMPSCI 61A":   { units:4, terms:["Fall","Spring"], prereqs:{or:["MATH 10A","MATH 16A"]}, rating:4.1, difficulty:3.3, topics:{python:0.6,algorithm:0.4}, instructors:["John DeNero"] },
  "COMPSCI 61B":   { units:4, terms:["Fall","Spring"], prereqs:{or:["COMPSCI 61A","ENGIN 7"]}, rating:4.7, difficulty:3.6, topics:{algorithm:0.7,python:0.3}, instructors:["Josh Hug"] },
  "COMPSCI 61C":   { units:4, terms:["Fall","Spring"], prereqs:{and:["COMPSCI 61A",{or:["COMPSCI 61B"]}]}, rating:4.1, difficulty:3.3, topics:{engineering:0.5,algorithm:0.3,physics:0.2}, instructors:["Dan Garcia"] },
  "COMPSCI 70":    { units:4, terms:["Fall","Spring"], prereqs:null, rating:4.7, difficulty:3.6, topics:{math:0.6,algorithm:0.4}, instructors:["Satish Rao"] },
  "COMPSCI 170":   { units:4, terms:["Fall","Spring"], prereqs:{and:["COMPSCI 61B","COMPSCI 70"]}, rating:1.8, difficulty:4.3, topics:{algorithm:0.8,engineering:0.2}, instructors:["Umesh Vazirani"] },
  "ENGIN 7":       { units:4, terms:["Fall","Spring"], prereqs:null, rating:4.8, difficulty:3.1, topics:{engineering:0.5,python:0.3,physics:0.2}, instructors:["Benson Tongue"] },
  "MATH 51":       { units:4, terms:["Fall","Spring"], prereqs:null, rating:2.1, difficulty:3.6, topics:{math:0.8,physics:0.2}, instructors:["Ko Woon Ohm"] },
  "MATH 52":       { units:4, terms:["Fall","Spring"], prereqs:"MATH 51", rating:3.3, difficulty:3.6, topics:{math:0.8,physics:0.2}, instructors:["Zvezdelina Stankova"] },
  "MATH 53":       { units:4, terms:["Fall","Spring"], prereqs:"MATH 52", rating:3.3, difficulty:4.1, topics:{math:0.8,physics:0.2}, instructors:["James Sethian","Suncica Canic"] },
  "MATH 54":       { units:4, terms:["Fall","Spring"], prereqs:"MATH 52", rating:3.7, difficulty:3.4, topics:{math:0.7,algorithm:0.2,python:0.1}, instructors:["Arun Sharma"] },
  "MATH 55":       { units:4, terms:["Fall","Spring"], prereqs:null, rating:4.3, difficulty:2.5, topics:{math:0.7,algorithm:0.3}, instructors:["Mark Haiman"] },
  "MATH 56":       { units:4, terms:["Fall","Spring"], prereqs:"MATH 52", rating:4.6, difficulty:3.3, topics:{math:0.8,algorithm:0.2}, instructors:["Alexander Paulin"] },
  "PHYSICS 7A":    { units:4, terms:["Fall","Spring"], prereqs:{and:["MATH 51","MATH 52"]}, rating:3.7, difficulty:3.1, topics:{physics:0.7,math:0.3}, instructors:["Adrian Lee","Enzo Brandani"] },
  "PHYSICS 7B":    { units:4, terms:["Fall","Spring"], prereqs:{and:["PHYSICS 7A","MATH 51","MATH 52"]}, rating:3.7, difficulty:3.1, topics:{physics:0.6,math:0.4}, instructors:["Catherine Bordel","Eve Schoen","Robert Birgeneau","Kevin Wen"] },
  "PHYSICS 8A":    { units:4, terms:["Fall","Spring"], prereqs:"MATH 51", rating:3.8, difficulty:3.7, topics:{physics:0.6,math:0.4}, instructors:["William Golightly","Kailash Raman"] },
  "PHYSICS 8B":    { units:4, terms:["Fall","Spring"], prereqs:"PHYSICS 8A", rating:4.8, difficulty:3.0, topics:{physics:0.7,math:0.3}, instructors:["Catherine Bordel","Noelle Blose"] },
  "CHEM 1A & CHEM 1AL":   { units:6, terms:["Fall","Spring"], prereqs:null, rating:2.9, difficulty:3.9, topics:{biochemistry:0.6,lab:0.4}, instructors:["TBA"] },
  "CHEM 3A & CHEM 3AL":   { units:6, terms:["Fall","Spring"], prereqs:"CHEM 1A & CHEM 1AL", rating:3.7, difficulty:3.9, topics:{biochemistry:0.6,lab:0.4}, instructors:["Peter Marsden"] },
  "BIOLOGY 1A & BIOLOGY 1AL": { units:5, terms:["Fall","Spring"], prereqs:{or:["CHEM 1A & CHEM 1AL"]}, rating:2.4, difficulty:4.4, topics:{genetics:0.4,lab:0.6}, instructors:["Jennifer Doudna","Andrea Gomez","Karine Gibbs"] },
  "BIOLOGY 1B":    { units:4, terms:["Fall","Spring"], prereqs:null, rating:4.9, difficulty:2.7, topics:{genetics:0.5,biochemistry:0.5}, instructors:["Benjamin Blackman","John Huelsenbeck","Benjamin Blonder","Caroline Williams","Charles Marshall","Michal Shuldman"] },
  "MCELLBI C100A": { units:4, terms:["Fall","Spring"], prereqs:null, rating:2.6, difficulty:3.5, topics:{biochemistry:0.7,genetics:0.3}, instructors:["David Drubin"] },
  "MCELLBI 100B":  { units:4, terms:["Fall","Spring"], prereqs:{or:["MCELLBI C100A"]}, rating:4.7, difficulty:2.3, topics:{biochemistry:0.6,genetics:0.4}, instructors:["Rebecca Heald"] },
  "MCELLBI 102":   { units:4, terms:["Fall","Spring"], prereqs:{and:["BIOLOGY 1A & BIOLOGY 1AL","CHEM 3A & CHEM 3AL"]}, rating:2.5, difficulty:4.0, topics:{biochemistry:0.5,genetics:0.4,lab:0.3}, instructors:["Ahmet Yildiz","William Thomas","Isabel Garcia","Carlos Bustamante","Mary Wildermuth","Bronwyn Lucas"] },
  "MCELLBI 104":   { units:4, terms:["Fall","Spring"], prereqs:"BIOLOGY 1A & BIOLOGY 1AL", rating:4.3, difficulty:2.8, topics:{genetics:0.6,bioinformatics:0.2,statistics:0.2}, instructors:["Nipam Patel"] },
  "MCELLBI C112 & MCELLBI C112L": { units:7, terms:["Fall","Spring"], prereqs:{and:["BIOLOGY 1A & BIOLOGY 1AL","BIOLOGY 1B"]}, rating:2.4, difficulty:3.9, topics:{biochemistry:0.6,lab:0.6,genetics:0.3}, instructors:["Michiko Taga","Karine Gibbs","John Coates"] },
  "MCELLBI 132":   { units:4, terms:["Fall","Spring"], prereqs:{and:["BIOLOGY 1A & BIOLOGY 1AL","BIOLOGY 1B","MCELLBI 102"]}, rating:4.0, difficulty:2.9, topics:{biochemistry:0.5,lab:0.4,bioinformatics:0.2}, instructors:["Kunxin Luo","Michel DuPage","Iswar Hariharan"] },
  "MCELLBI 110":   { units:4, terms:["Fall","Spring"], prereqs:"MCELLBI C100A", rating:4.3, difficulty:3.4, topics:{biochemistry:0.6,genetics:0.3,statistics:0.2}, instructors:["James Nunez","Nick Ingolia","Eunyong Park","Eva Nogales"] },
  "MCELLBI 140 & MCELLBI 140L": { units:8, terms:["Fall","Spring"], prereqs:{and:["BIOLOGY 1A & BIOLOGY 1AL"]}, rating:4.0, difficulty:3.8, topics:{lab:0.7,biochemistry:0.5,engineering:0.2}, instructors:["Elcin Unal","Dipti Nayak","Daniel Rokhsar"] },
  "MCELLBI 141":   { units:4, terms:["Spring"], prereqs:{and:[{or:["MCELLBI 102","MCELLBI C100A"]},{and:["BIOLOGY 1A & BIOLOGY 1AL","BIOLOGY 1B"]}]}, rating:3.8, difficulty:3.5, topics:{genetics:0.5,biochemistry:0.4,lab:0.3}, instructors:["Richard Harland","Craig Miller"] },
  "MCELLBI C148":  { units:4, terms:["Fall","Spring"], prereqs:{or:["MCELLBI C100A","MCELLBI 102"]}, rating:5.0, difficulty:3.0, topics:{bioinformatics:0.6,statistics:0.4,python:0.3}, instructors:["Lior Pachter"] },
  "MCELLBI 149":   { units:3, terms:["Fall"], prereqs:{or:[{and:["MCELLBI 110","MCELLBI 140 & MCELLBI 140L"]},"MCELLBI 104"]}, rating:3.2, difficulty:3.8, topics:{lab:0.6,biochemistry:0.4}, instructors:["Steven Brenner","Priya Moorjani","Lin He"] },
  "MCELLBI 150 & MCELLBI 150L": { units:8, terms:["Fall","Spring"], prereqs:{or:["MCELLBI C100A","MCELLBI 102"]}, rating:4.3, difficulty:3.3, topics:{lab:0.7,biochemistry:0.5,engineering:0.3}, instructors:["Sarah Stanley","Gregory Barton","Laurent Coscoy"] },
  "MCELLBI 153":   { units:4, terms:["Fall"], prereqs:{or:["MCELLBI C100A","BIOLOGY 1A & BIOLOGY 1AL"]}, rating:5.0, difficulty:4.0, topics:{bioinformatics:0.6,statistics:0.4,python:0.3}, instructors:["Andrew Dillin","Sarah Stanley"] },
  "MCELLBI 153L":  { units:4, terms:["Spring"], prereqs:{or:["MCELLBI 102","MCELLBI C100A"]}, rating:5.0, difficulty:4.0, topics:{lab:0.7,bioinformatics:0.4}, instructors:["Jeffery Cox","Andrew Dillin"] },
  "BIOENG C131":   { units:4, terms:["Fall"], prereqs:{or:["ENGIN 7","COMPSCI 61A"]}, rating:1.9, difficulty:4.1, topics:{engineering:0.6,algorithm:0.4,python:0.3}, instructors:["TBA"] },
  "BIOENG C142":   { units:4, terms:["Spring"], prereqs:{and:["MATH 53","MATH 54"]}, rating:2.5, difficulty:3.8, topics:{engineering:0.6,physics:0.4,math:0.3}, instructors:["Teresa Head-Gordon"] },
  "BIOENG 145":    { units:4, terms:["Spring"], prereqs:{and:["MATH 54","COMPSCI 61B"]}, rating:3.1, difficulty:3.1, topics:{algorithm:0.5,bioinformatics:0.4,python:0.3}, instructors:["Liana Lareau"] },
  "BIOENG C149":   { units:4, terms:["Fall"], prereqs:{and:["COMPSCI 61A","BIOENG C131"]}, rating:3.1, difficulty:3.1, topics:{engineering:0.5,algorithm:0.4,statistics:0.3}, instructors:["Liana Lareau"] },
  "BIOENG 103":    { units:4, terms:["Fall"], prereqs:{and:["PHYSICS 7A","PHYSICS 7B","MATH 54"]}, rating:2.7, difficulty:3.7, topics:{physics:0.5,engineering:0.4,math:0.3}, instructors:["Derfogail Delcassian","Matthew Rosenwasser"] },
  "STAT 20":       { units:4, terms:["Fall","Spring"], prereqs:"MATH 51", rating:3.5, difficulty:3.1, topics:{statistics:0.7,probability:0.3}, instructors:["Shobhana Stoyanov"] },
  "STAT 133":      { units:3, terms:["Fall","Spring"], prereqs:null, rating:3.0, difficulty:3.0, topics:{statistics:0.6,data_analysis:0.4}, instructors:["Gaston Sanchez"] },
  "STAT 134":      { units:4, terms:["Fall","Spring"], prereqs:null, rating:2.4, difficulty:3.9, topics:{statistics:0.5,regression:0.3,probability:0.2}, instructors:["Shobhana Stoyanov"] },
};

const ALL_TOPICS = [...new Set(Object.values(COURSES).flatMap(c => Object.keys(c.topics)))].sort();
const TERMS_SEQ = [
  ["Fall","Year 1"],["Spring","Year 1"],
  ["Fall","Year 2"],["Spring","Year 2"],
  ["Fall","Year 3"],["Spring","Year 3"],
  ["Fall","Year 4"],["Spring","Year 4"],
];

// ── Prereq evaluator ─────────────────────────────────────────────────────────
function prereqMet(req, taken) {
  if (!req) return true;
  if (typeof req === "string") return taken.has(req);
  if (req.and) return req.and.every(r => prereqMet(r, taken));
  if (req.or)  return req.or.some(r  => prereqMet(r, taken));
  return true;
}

// ── Scoring ──────────────────────────────────────────────────────────────────
function scoreSchedule(courses, profile, weights) {
  const n = courses.length;
  if (!n) return 0;
  let interest = 0, avgDiff = 0, avgProf = 0;
  for (const c of courses) {
    const cd = COURSES[c];
    for (const [t, w] of Object.entries(cd.topics)) interest += w * (profile[t] || 0);
    avgDiff += cd.difficulty;
    avgProf += cd.rating;
  }
  interest /= n; avgDiff /= n; avgProf /= n;
  return weights.interest * interest - weights.difficulty * avgDiff + weights.professor * avgProf;
}

// ── Combination generator (capped at k=5) ────────────────────────────────────
function* combos(arr, k) {
  if (k === 0) { yield []; return; }
  for (let i = 0; i <= arr.length - k; i++)
    for (const rest of combos(arr.slice(i + 1), k - 1))
      yield [arr[i], ...rest];
}

// ── Single-semester planner ──────────────────────────────────────────────────
function bestSemester(completed, profile, term, weights, minU, maxU, topK = 5) {
  const avail = Object.keys(COURSES).filter(c =>
    !completed.has(c) &&
    prereqMet(COURSES[c].prereqs, completed) &&
    COURSES[c].terms.includes(term)
  );
  let heap = [];
  for (let k = 1; k <= Math.min(avail.length, 5); k++) {
    for (const combo of combos(avail, k)) {
      const units = combo.reduce((s, c) => s + COURSES[c].units, 0);
      if (units < minU || units > maxU) continue;
      const sc = scoreSchedule(combo, profile, weights);
      heap.push({ courses: combo, score: sc, units });
    }
  }
  heap.sort((a, b) => b.score - a.score);
  return heap.slice(0, topK);
}

// ── Four-year beam search ────────────────────────────────────────────────────
function planFourYears(profile, weights, minU, maxU, beamWidth = 3) {
  let beam = [{ completed: new Set(), semesters: [], score: 0 }];
  for (const [term, year] of TERMS_SEQ) {
    const next = [];
    for (const state of beam) {
      const options = bestSemester(state.completed, profile, term, weights, minU, maxU, 4);
      if (!options.length) { next.push(state); continue; }
      for (const opt of options) {
        const newCompleted = new Set([...state.completed, ...opt.courses]);
        next.push({
          completed: newCompleted,
          semesters: [...state.semesters, { term, year, ...opt }],
          score: state.score + opt.score,
        });
      }
    }
    next.sort((a, b) => b.score - a.score);
    beam = next.slice(0, beamWidth);
  }
  return beam;
}

// ── Data quality heuristic (client-side) ─────────────────────────────────────
function dataQuality(c) {
  const cd = COURSES[c];
  let score = 0;
  if (!cd.instructors.includes("TBA")) score += 0.35;
  if (Object.keys(cd.topics).length >= 3) score += 0.25;
  if (cd.rating >= 3.0) score += 0.25;
  score += Math.min(cd.units / 8, 0.15);
  return Math.min(score, 1.0);
}

// ── Topic colours ─────────────────────────────────────────────────────────────
const TOPIC_COLOR = {
  python:"#185FA5", algorithm:"#533AB7", statistics:"#0F6E56",
  bioinformatics:"#3B6D11", math:"#5F5E5A", physics:"#854F0B",
  genetics:"#993556", biochemistry:"#993C1D", lab:"#D4537E",
  engineering:"#378ADD", probability:"#1D9E75", regression:"#D85A30",
  data_analysis:"#639922",
};
const tc = (t) => TOPIC_COLOR[t] || "#888";

// ── Difficulty colour ─────────────────────────────────────────────────────────
const dc = (d) => d >= 4 ? "#A32D2D" : d >= 3 ? "#BA7517" : "#3B6D11";

// ── Chip component ────────────────────────────────────────────────────────────
function Chip({ label, color }) {
  return (
    <span style={{
      fontSize: 11, padding: "2px 8px", borderRadius: 20,
      background: color + "22", color, border: `0.5px solid ${color}44`,
      whiteSpace: "nowrap",
    }}>{label}</span>
  );
}

// ── Stat card ─────────────────────────────────────────────────────────────────
function Stat({ label, value }) {
  return (
    <div style={{ background:"var(--color-background-secondary)", borderRadius:"var(--border-radius-md)", padding:"12px 14px" }}>
      <p style={{ fontSize:12, color:"var(--color-text-secondary)", margin:"0 0 4px" }}>{label}</p>
      <p style={{ fontSize:22, fontWeight:500, margin:0, color:"var(--color-text-primary)" }}>{value}</p>
    </div>
  );
}

// ── Course card ───────────────────────────────────────────────────────────────
function CourseCard({ name, showQuality }) {
  const cd = COURSES[name];
  const dq = dataQuality(name);
  const instructorStr = cd.instructors.filter(i => i !== "TBA").join(", ") || "TBA";
  return (
    <div style={{ marginBottom:"0.85rem", paddingBottom:"0.85rem", borderBottom:"0.5px solid var(--color-border-tertiary)" }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"baseline", gap:8 }}>
        <span style={{ fontSize:14, fontWeight:500, color:"var(--color-text-primary)" }}>{name}</span>
        <span style={{ fontSize:12, color:"var(--color-text-secondary)", whiteSpace:"nowrap" }}>{cd.units} units</span>
      </div>
      <div style={{ fontSize:12, color:"var(--color-text-secondary)", margin:"2px 0 6px" }}>{instructorStr}</div>
      <div style={{ display:"flex", gap:6, flexWrap:"wrap", alignItems:"center" }}>
        {Object.entries(cd.topics).map(([t, w]) =>
          <Chip key={t} label={`${t} ${(w*100).toFixed(0)}%`} color={tc(t)} />
        )}
        <span style={{ marginLeft:"auto", fontSize:12, color:"var(--color-text-secondary)", whiteSpace:"nowrap" }}>
          diff <span style={{ color:dc(cd.difficulty), fontWeight:500 }}>{cd.difficulty}</span>
          {" · "}★ {cd.rating.toFixed(1)}
          {showQuality && <span style={{ color: dq < 0.4 ? "#BA7517" : "var(--color-text-secondary)" }}>
            {" · "}dq {(dq*100).toFixed(0)}%
          </span>}
        </span>
      </div>
    </div>
  );
}

// ── Tab bar ───────────────────────────────────────────────────────────────────
function TabBar({ tabs, active, onChange }) {
  return (
    <div style={{ display:"flex", gap:2, borderBottom:"0.5px solid var(--color-border-tertiary)", marginBottom:"1.25rem" }}>
      {tabs.map(t => (
        <button key={t} onClick={() => onChange(t)} style={{
          background: active===t ? "var(--color-background-secondary)" : "transparent",
          border:"none",
          borderBottom: active===t ? "2px solid var(--color-text-primary)" : "2px solid transparent",
          padding:"8px 14px", fontSize:13, fontWeight: active===t ? 500 : 400,
          color: active===t ? "var(--color-text-primary)" : "var(--color-text-secondary)",
          cursor:"pointer", borderRadius:"var(--border-radius-md) var(--border-radius-md) 0 0",
          marginBottom:-1,
        }}>{t}</button>
      ))}
    </div>
  );
}

// ── Slider row ────────────────────────────────────────────────────────────────
function SliderRow({ label, value, min=0, max=1, step=0.05, onChange, color }) {
  return (
    <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:10 }}>
      {color && <span style={{ width:10, height:10, borderRadius:"50%", background:color, flexShrink:0, display:"inline-block" }} />}
      <span style={{ fontSize:13, width:130, flexShrink:0, color:"var(--color-text-primary)" }}>{label}</span>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(+e.target.value)} style={{ flex:1 }} />
      <span style={{ fontSize:13, fontWeight:500, minWidth:32, textAlign:"right", color:"var(--color-text-primary)" }}>
        {value.toFixed(2)}
      </span>
    </div>
  );
}

// ── Main app ──────────────────────────────────────────────────────────────────
export default function App() {
  const [tab, setTab]         = useState("Profile");
  const [profile, setProfile] = useState(() => Object.fromEntries(ALL_TOPICS.map(t => [t, 0.5])));
  const [weights, setWeights] = useState({ interest:1.0, difficulty:0.5, professor:0.3 });
  const [minU, setMinU]       = useState(12);
  const [maxU, setMaxU]       = useState(18);
  const [beamW, setBeamW]     = useState(3);
  const [showQuality, setShowQuality] = useState(true);
  const [plan, setPlan]       = useState(null);
  const [activePlan, setActivePlan] = useState(0);
  const [activeSem, setActiveSem]   = useState(0);

  const generate = useCallback(() => {
    const result = planFourYears(profile, weights, minU, maxU, beamW);
    setPlan(result);
    setActivePlan(0);
    setActiveSem(0);
    setTab("Plan");
  }, [profile, weights, minU, maxU, beamW]);

  const currentPlan  = plan?.[activePlan];
  const currentSem   = currentPlan?.semesters?.[activeSem];
  const totalCourses = currentPlan ? currentPlan.semesters.reduce((s,sem) => s + sem.courses.length, 0) : 0;
  const totalUnits   = currentPlan ? currentPlan.semesters.reduce((s,sem) => s + sem.units, 0) : 0;

  return (
    <div style={{ fontFamily:"var(--font-sans)", padding:"1.25rem 1rem", maxWidth:700 }}>
      <div style={{ display:"flex", alignItems:"baseline", justifyContent:"space-between", marginBottom:"0.25rem" }}>
        <h2 style={{ fontSize:20, fontWeight:500, margin:0, color:"var(--color-text-primary)" }}>CoursePath</h2>
        <span style={{ fontSize:12, color:"var(--color-text-secondary)" }}>UC Berkeley · {Object.keys(COURSES).length} courses</span>
      </div>
      <p style={{ fontSize:13, color:"var(--color-text-secondary)", margin:"0 0 1.25rem" }}>
        Semantic four-year academic planner
      </p>

      <TabBar tabs={["Profile","Weights","Plan"]} active={tab} onChange={setTab} />

      {/* ── Profile tab ── */}
      {tab === "Profile" && (
        <div>
          <p style={{ fontSize:13, color:"var(--color-text-secondary)", margin:"0 0 1rem" }}>
            Rate your interest in each topic (0 = none, 1 = strong)
          </p>
          {ALL_TOPICS.map(t => (
            <SliderRow key={t} label={t} value={profile[t]} color={tc(t)}
              onChange={v => setProfile(p => ({ ...p, [t]: v }))} />
          ))}
          <button onClick={() => setTab("Weights")} style={{
            marginTop:"1rem", padding:"7px 18px", fontSize:13,
            background:"var(--color-background-secondary)",
            border:"0.5px solid var(--color-border-secondary)",
            borderRadius:"var(--border-radius-md)", cursor:"pointer",
            color:"var(--color-text-primary)"
          }}>Next: scoring weights →</button>
        </div>
      )}

      {/* ── Weights tab ── */}
      {tab === "Weights" && (
        <div>
          <p style={{ fontSize:13, color:"var(--color-text-secondary)", margin:"0 0 1.25rem" }}>
            Adjust how each factor influences schedule ranking
          </p>

          {[
            { key:"interest",   label:"Interest alignment",  hint:"Match to your topic profile" },
            { key:"difficulty", label:"Difficulty penalty",  hint:"Higher = prefer easier courses" },
            { key:"professor",  label:"Professor quality",   hint:"Based on RateMyProfessors" },
          ].map(({ key, label, hint }) => (
            <div key={key} style={{ marginBottom:"1.25rem" }}>
              <div style={{ display:"flex", justifyContent:"space-between", marginBottom:4 }}>
                <span style={{ fontSize:14, fontWeight:500, color:"var(--color-text-primary)" }}>{label}</span>
                <span style={{ fontSize:14, fontWeight:500, color:"var(--color-text-primary)" }}>{weights[key].toFixed(1)}</span>
              </div>
              <p style={{ fontSize:12, color:"var(--color-text-secondary)", margin:"0 0 5px" }}>{hint}</p>
              <input type="range" min={0} max={2} step={0.1} value={weights[key]}
                onChange={e => setWeights(w => ({ ...w, [key]: +e.target.value }))}
                style={{ width:"100%" }} />
            </div>
          ))}

          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12, marginBottom:"1.25rem" }}>
            <div>
              <p style={{ fontSize:13, color:"var(--color-text-secondary)", margin:"0 0 4px" }}>Min units / semester</p>
              <input type="number" min={8} max={16} value={minU}
                onChange={e => setMinU(+e.target.value)}
                style={{ width:"100%", padding:"6px 8px", borderRadius:"var(--border-radius-md)", border:"0.5px solid var(--color-border-secondary)", background:"var(--color-background-secondary)", color:"var(--color-text-primary)", fontSize:14 }} />
            </div>
            <div>
              <p style={{ fontSize:13, color:"var(--color-text-secondary)", margin:"0 0 4px" }}>Max units / semester</p>
              <input type="number" min={12} max={22} value={maxU}
                onChange={e => setMaxU(+e.target.value)}
                style={{ width:"100%", padding:"6px 8px", borderRadius:"var(--border-radius-md)", border:"0.5px solid var(--color-border-secondary)", background:"var(--color-background-secondary)", color:"var(--color-text-primary)", fontSize:14 }} />
            </div>
          </div>

          <div style={{ marginBottom:"1.25rem" }}>
            <p style={{ fontSize:13, color:"var(--color-text-secondary)", margin:"0 0 4px" }}>
              Beam width — how many plan variants to generate ({beamW})
            </p>
            <input type="range" min={1} max={5} step={1} value={beamW}
              onChange={e => setBeamW(+e.target.value)} style={{ width:"100%" }} />
          </div>

          <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:"1.25rem" }}>
            <input type="checkbox" id="dq" checked={showQuality}
              onChange={e => setShowQuality(e.target.checked)} />
            <label htmlFor="dq" style={{ fontSize:13, color:"var(--color-text-secondary)", cursor:"pointer" }}>
              Show data quality indicators on courses
            </label>
          </div>

          <button onClick={generate} style={{
            padding:"10px 24px", fontSize:14, fontWeight:500,
            background:"var(--color-text-primary)", color:"var(--color-background-primary)",
            border:"none", borderRadius:"var(--border-radius-md)", cursor:"pointer",
          }}>
            Generate four-year plan ↗
          </button>
        </div>
      )}

      {/* ── Plan tab ── */}
      {tab === "Plan" && !plan && (
        <div style={{ color:"var(--color-text-secondary)", fontSize:14 }}>
          <p>Set your profile and weights, then generate a plan.</p>
          <button onClick={() => setTab("Weights")} style={{
            fontSize:13, cursor:"pointer", background:"none",
            border:"0.5px solid var(--color-border-secondary)", padding:"6px 14px",
            borderRadius:"var(--border-radius-md)", color:"var(--color-text-primary)"
          }}>Go to weights →</button>
        </div>
      )}

      {tab === "Plan" && plan && (
        <div>
          {/* Plan variant selector */}
          {plan.length > 1 && (
            <div style={{ display:"flex", gap:6, marginBottom:"1rem" }}>
              {plan.map((p, i) => (
                <button key={i} onClick={() => { setActivePlan(i); setActiveSem(0); }} style={{
                  padding:"6px 12px", fontSize:12,
                  background: activePlan===i ? "var(--color-background-secondary)" : "transparent",
                  border: activePlan===i ? "1px solid var(--color-border-primary)" : "0.5px solid var(--color-border-tertiary)",
                  borderRadius:"var(--border-radius-md)", cursor:"pointer", color:"var(--color-text-primary)",
                }}>Plan {i+1} · {p.score.toFixed(2)}</button>
              ))}
            </div>
          )}

          {/* Stats */}
          <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:10, marginBottom:"1.25rem" }}>
            <Stat label="Cumulative score" value={currentPlan.score.toFixed(2)} />
            <Stat label="Courses planned" value={totalCourses} />
            <Stat label="Total units" value={totalUnits} />
          </div>

          {/* Semester grid */}
          <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:6, marginBottom:"1.25rem" }}>
            {currentPlan.semesters.map((sem, i) => (
              <button key={i} onClick={() => setActiveSem(i)} style={{
                padding:"8px 6px", fontSize:11, textAlign:"left",
                background: activeSem===i ? "var(--color-background-secondary)" : "transparent",
                border: activeSem===i ? "1px solid var(--color-border-primary)" : "0.5px solid var(--color-border-tertiary)",
                borderRadius:"var(--border-radius-md)", cursor:"pointer", color:"var(--color-text-primary)",
              }}>
                <div style={{ fontWeight:500 }}>{sem.year}</div>
                <div style={{ color:"var(--color-text-secondary)" }}>{sem.term}</div>
                <div style={{ marginTop:3, color:"var(--color-text-secondary)" }}>
                  {sem.courses.length} · {sem.units}u · {sem.score.toFixed(2)}
                </div>
              </button>
            ))}
          </div>

          {/* Semester detail */}
          {currentSem && (
            <div style={{
              border:"0.5px solid var(--color-border-tertiary)",
              borderRadius:"var(--border-radius-lg)", padding:"1rem 1.25rem",
            }}>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"baseline", marginBottom:"1rem" }}>
                <p style={{ fontWeight:500, margin:0, fontSize:15, color:"var(--color-text-primary)" }}>
                  {currentSem.year} · {currentSem.term}
                </p>
                <span style={{ fontSize:12, color:"var(--color-text-secondary)" }}>
                  {currentSem.units} units · score {currentSem.score.toFixed(3)}
                </span>
              </div>

              {currentSem.courses.length === 0
                ? <p style={{ fontSize:13, color:"var(--color-text-secondary)" }}>No valid schedule found.</p>
                : currentSem.courses.map(c => <CourseCard key={c} name={c} showQuality={showQuality} />)
              }

              <div style={{ display:"flex", justifyContent:"flex-end", marginTop:4 }}>
                <button onClick={() => sendPrompt(`Explain the schedule for ${currentSem.year} ${currentSem.term}: ${currentSem.courses.join(", ")}`)}
                  style={{ fontSize:12, background:"none", border:"0.5px solid var(--color-border-secondary)",
                    padding:"4px 10px", borderRadius:"var(--border-radius-md)", cursor:"pointer",
                    color:"var(--color-text-primary)" }}>
                  Explain this schedule ↗
                </button>
              </div>
            </div>
          )}

          <button onClick={generate} style={{
            marginTop:"1rem", padding:"7px 14px", fontSize:12,
            background:"transparent", border:"0.5px solid var(--color-border-secondary)",
            borderRadius:"var(--border-radius-md)", cursor:"pointer", color:"var(--color-text-primary)"
          }}>Regenerate</button>
        </div>
      )}
    </div>
  );
}
