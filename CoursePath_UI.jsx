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

// ── Major / track data ───────────────────────────────────────────────────────
const MAJOR_TRACKS = {
  "CS B.A.":             { key:"CS_BA",   tracks:["default"] },
  "EECS B.S.":           { key:"EECS_BS", tracks:["default"] },
  "Data Science B.A.":   { key:"DATA_BA", tracks:["default",
    "computational_molecular_genomic_biology","evolution_biodiversity",
    "human_population_health","neurosciences","ecology_environment"] },
  "Bioengineering B.S.": { key:"BIOE_BS", tracks:[
    "bioinstrumentation","computational_biology",
    "synthetic_systems_biology","cell_tissue_engineering"] },
  "MCB B.A.":            { key:"MCB",     tracks:[
    "BBS_track1","BBS_track2","CDP_track1","CDP_track2",
    "GGED_track1","GGED_track2","IMM_track1","IMM_track2","IMM_track3",
    "MTX_track1","MTX_track2"] },
};

// Major requirement buckets (this is a subset: courses in COURSES only)
const MAJOR_REQS = {
  CS_BA: {
    "calc_1":["MATH 51"],"calc_2":["MATH 52"],
    "linear_algebra":["MATH 54","MATH 56"],
    "program_struct":["COMPSCI 61A"],"data_structures":["COMPSCI 61B"],
    "machine_struct":["COMPSCI 61C"],"discrete_math":["COMPSCI 70"],
    "cs_theory":["COMPSCI 170"],
  },
  EECS_BS: {
    "calc_1":["MATH 51"],"calc_2":["MATH 52"],
    "linear_algebra":["MATH 54","MATH 56"],
    "physics_1":["PHYSICS 7A","PHYSICS 8A"],"physics_2":["PHYSICS 7B","PHYSICS 8B"],
    "program_struct":["COMPSCI 61A"],"data_structures":["COMPSCI 61B"],
    "machine_struct":["COMPSCI 61C"],"discrete_math":["COMPSCI 70"],
    "cs_theory":["COMPSCI 170"],
  },
  DATA_BA: {
    "foundations":["DATA C8","STAT 20"],
    "calc_1":["MATH 51"],"calc_2":["MATH 52"],
    "linear_algebra":["MATH 54","MATH 56"],
    "program_struct":["COMPSCI 61A","DATA C88C"],
    "data_structures":["COMPSCI 61B"],
    "core":["DATA C100"],
    "probability":["DATA C140","STAT 134"],
    "CID":["DATA C101","DATA C102","COMPSCI 170","BIOENG 145","MCELLBI C148"],
    "MLDM":["DATA C102"],
    "HCE":["DATA C104"],
  },
  BIOE_BS: {
    "calc_1":["MATH 51"],"calc_2":["MATH 52"],
    "calc_3":["MATH 53"],"linear_alg":["MATH 54"],
    "physics_1":["PHYSICS 7A"],"physics_2":["PHYSICS 7B"],
    "chem_1":["CHEM 1A & CHEM 1AL"],"chem_2":["CHEM 3A & CHEM 3AL"],
    "programming":["ENGIN 7","COMPSCI 61A"],
    "bioe_fundamentals":["BIOENG C131","BIOENG C142","BIOENG C149","BIOENG 103"],
    "bioe_lab":["MCELLBI 140 & MCELLBI 140L","MCELLBI 153L"],
  },
  MCB: {
    "math":["MATH 51","MATH 52"],
    "chem_1":["CHEM 1A & CHEM 1AL"],"chem_2":["CHEM 3A & CHEM 3AL"],
    "bio_1":["BIOLOGY 1A & BIOLOGY 1AL"],"bio_2":["BIOLOGY 1B"],
    "physics_1":["PHYSICS 8A","PHYSICS 7A"],"physics_2":["PHYSICS 8B","PHYSICS 7B"],
    "mcb_core":["MCELLBI C100A","MCELLBI 100B","MCELLBI 102"],
    "genetics":["MCELLBI 104","MCELLBI 110"],
    "lab":["MCELLBI 140 & MCELLBI 140L","MCELLBI 149","MCELLBI 153L"],
  },
};

function majorProgressBonus(courses, completedSoFar, majorKeys) {
  if (!majorKeys.length) return 0;
  let total = 0;
  for (const mk of majorKeys) {
    const reqs = MAJOR_REQS[mk] || {};
    const buckets = Object.values(reqs);
    if (!buckets.length) continue;
    const allCourses = new Set([...completedSoFar, ...courses]);
    const fulfilled = buckets.filter(opts => opts.some(c => allCourses.has(c))).length;
    const before    = buckets.filter(opts => opts.some(c => completedSoFar.has(c))).length;
    total += (fulfilled - before) / buckets.length;
  }
  return total / majorKeys.length;
}

// ── Prereq evaluator ─────────────────────────────────────────────────────────
function prereqMet(req, taken) {
  if (!req) return true;
  if (typeof req === "string") return taken.has(req);
  if (req.and) return req.and.every(r => prereqMet(r, taken));
  if (req.or)  return req.or.some(r  => prereqMet(r, taken));
  return true;
}

// ── Scoring ──────────────────────────────────────────────────────────────────
function scoreSchedule(courses, profile, weights, completedSoFar = new Set(), majorKeys = []) {
  const n = courses.length;
  if (!n) return 0;
  let interest = 0, avgDiff = 0, avgProf = 0, avgWta = 0, wtaCount = 0;
  for (const c of courses) {
    const cd = COURSES[c];
    for (const [t, w] of Object.entries(cd.topics)) interest += w * (profile[t] || 0);
    avgDiff += (cd.rmp_difficulty != null ? cd.rmp_difficulty * 0.6 + cd.difficulty * 0.4 : cd.difficulty);
    avgProf += cd.rating;
    if (cd.would_take_again != null) { avgWta += cd.would_take_again / 100; wtaCount++; }
  }
  interest /= n; avgDiff /= n; avgProf /= n;
  const wta = wtaCount ? avgWta / wtaCount : 0;
  const mp  = majorProgressBonus(courses, completedSoFar, majorKeys);
  return (weights.interest || 1.0) * interest
       - (weights.difficulty || 0.5) * avgDiff
       + (weights.professor || 0.3) * avgProf
       + (weights.would_take_again || 0.2) * wta
       + (weights.major_progress || 0.2) * mp;
}

// ── Combination generator (capped at k=5) ────────────────────────────────────
function* combos(arr, k) {
  if (k === 0) { yield []; return; }
  for (let i = 0; i <= arr.length - k; i++)
    for (const rest of combos(arr.slice(i + 1), k - 1))
      yield [arr[i], ...rest];
}

// ── Single-semester planner ──────────────────────────────────────────────────
function bestSemester(completed, profile, term, weights, minU, maxU, majorKeys = [], topK = 5) {
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
      const sc = scoreSchedule(combo, profile, weights, completed, majorKeys);
      heap.push({ courses: combo, score: sc, units });
    }
  }
  heap.sort((a, b) => b.score - a.score);
  return heap.slice(0, topK);
}

// ── Four-year beam search ────────────────────────────────────────────────────
function planFourYears(profile, weights, minU, maxU, beamWidth = 3, initialCompleted = new Set(), majorKeys = [], numSems = 8) {
  let beam = [{ completed: new Set([...initialCompleted]), semesters: [], score: 0 }];
  for (const [term, year] of TERMS_SEQ.slice(0, numSems)) {
    const next = [];
    for (const state of beam) {
      const options = bestSemester(state.completed, profile, term, weights, minU, maxU, majorKeys, 4);
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
function Stat({ label, value, accent }) {
  return (
    <div style={{
      background:"var(--color-background-secondary)",
      borderRadius:"var(--border-radius-md)",
      padding:"14px 16px",
      borderTop: accent ? `2px solid ${accent}` : "2px solid transparent",
    }}>
      <p style={{ fontSize:11, fontWeight:500, letterSpacing:"0.04em", textTransform:"uppercase", color:"var(--color-text-secondary)", margin:"0 0 6px" }}>{label}</p>
      <p style={{ fontSize:24, fontWeight:700, margin:0, letterSpacing:"-0.5px", color:"var(--color-text-primary)" }}>{value}</p>
    </div>
  );
}

function MajorProgressBar({ pct }) {
  if (pct === null) return null;
  const color = pct >= 80 ? "#3B6D11" : pct >= 50 ? "#BA7517" : "#533AB7";
  return (
    <div style={{ marginBottom:"1.25rem" }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"baseline", marginBottom:6 }}>
        <span style={{ fontSize:12, fontWeight:600, letterSpacing:"0.04em", textTransform:"uppercase", color:"var(--color-text-secondary)" }}>
          Major requirement progress
        </span>
        <span style={{ fontSize:14, fontWeight:700, color }}>{pct}%</span>
      </div>
      <div style={{ height:6, borderRadius:99, background:"var(--color-border-tertiary)", overflow:"hidden" }}>
        <div style={{
          height:"100%", width:`${pct}%`, borderRadius:99,
          background: color,
          transition:"width 0.4s ease",
        }} />
      </div>
    </div>
  );
}

// ── Course card ───────────────────────────────────────────────────────────────
function CourseCard({ name, showQuality }) {
  const cd = COURSES[name];
  const dq = dataQuality(name);
  const instructorStr = cd.instructors.filter(i => i !== "TBA").join(", ") || "TBA";
  return (
    <div style={{ marginBottom:"1rem", paddingBottom:"1rem", borderBottom:"0.5px solid var(--color-border-tertiary)" }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"baseline", gap:8, marginBottom:2 }}>
        <span style={{ fontSize:14, fontWeight:700, letterSpacing:"-0.2px", color:"var(--color-text-primary)" }}>{name}</span>
        <span style={{ fontSize:12, fontWeight:500, color:"var(--color-text-secondary)", whiteSpace:"nowrap" }}>{cd.units} units</span>
      </div>
      <div style={{ fontSize:12, color:"var(--color-text-secondary)", margin:"0 0 7px", opacity:0.8 }}>{instructorStr}</div>
      <div style={{ display:"flex", gap:5, flexWrap:"wrap", alignItems:"center" }}>
        {Object.entries(cd.topics).map(([t, w]) =>
          <Chip key={t} label={`${t} ${(w*100).toFixed(0)}%`} color={tc(t)} />
        )}
        <span style={{ marginLeft:"auto", fontSize:12, color:"var(--color-text-secondary)", whiteSpace:"nowrap", opacity:0.85 }}>
          diff <span style={{ color:dc(cd.rmp_difficulty ?? cd.difficulty), fontWeight:600 }}>
            {(cd.rmp_difficulty ?? cd.difficulty).toFixed(1)}
            {cd.rmp_difficulty != null && <span style={{fontSize:10, opacity:0.6}}> rmp</span>}
          </span>
          {cd.would_take_again != null &&
            <span> · ↩ {cd.would_take_again.toFixed(0)}%</span>}
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
    <div style={{ display:"flex", gap:2, borderBottom:"1px solid var(--color-border-tertiary)", marginBottom:"1.5rem" }}>
      {tabs.map(t => (
        <button key={t} onClick={() => onChange(t)} style={{
          background:"transparent",
          border:"none",
          borderBottom: active===t ? "2px solid var(--color-text-primary)" : "2px solid transparent",
          padding:"9px 16px", fontSize:13, fontWeight: active===t ? 600 : 400,
          color: active===t ? "var(--color-text-primary)" : "var(--color-text-secondary)",
          cursor:"pointer", borderRadius:"var(--border-radius-md) var(--border-radius-md) 0 0",
          marginBottom:-1, letterSpacing: active===t ? "-0.01em" : "normal",
          transition:"color 0.15s",
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
  const [weights, setWeights] = useState({ interest:1.0, difficulty:0.5, professor:0.3, would_take_again:0.2, major_progress:0.2 });
  const [minU, setMinU]       = useState(12);
  const [maxU, setMaxU]       = useState(18);
  const [beamW, setBeamW]     = useState(3);
  const [numSems, setNumSems] = useState(8);
  const [showQuality, setShowQuality] = useState(true);
  const [completedInput, setCompletedInput] = useState("");
  const [selectedMajors, setSelectedMajors] = useState([]);
  const [selectedTracks, setSelectedTracks] = useState({});
  const [plan, setPlan]       = useState(null);
  const [activePlan, setActivePlan] = useState(0);
  const [activeSem, setActiveSem]   = useState(0);

  const completedSet = useMemo(() => {
    const names = completedInput.split(",").map(s => s.trim()).filter(s => s in COURSES);
    return new Set(names);
  }, [completedInput]);

  const majorKeys = useMemo(() =>
    selectedMajors.map(m => {
      const info = MAJOR_TRACKS[m];
      const track = selectedTracks[m] || "default";
      return info?.key || info?.key;
    }).filter(Boolean),
  [selectedMajors, selectedTracks]);

  const generate = useCallback(() => {
    const result = planFourYears(profile, weights, minU, maxU, beamW, completedSet, majorKeys, numSems);
    setPlan(result);
    setActivePlan(0);
    setActiveSem(0);
    setTab("Plan");
  }, [profile, weights, minU, maxU, beamW, completedSet, majorKeys]);

  const currentPlan  = plan?.[activePlan];
  const currentSem   = currentPlan?.semesters?.[activeSem];
  const totalCourses = currentPlan ? currentPlan.semesters.reduce((s,sem) => s + sem.courses.length, 0) : 0;
  const totalUnits   = currentPlan ? currentPlan.semesters.reduce((s,sem) => s + sem.units, 0) : 0;

  const majorProgress = useMemo(() => {
    if (!currentPlan || !majorKeys.length) return null;
    const allCompleted = new Set([...completedSet, ...currentPlan.semesters.flatMap(s => s.courses)]);
    let total = 0, count = 0;
    for (const mk of majorKeys) {
      const reqs = MAJOR_REQS[mk] || {};
      const buckets = Object.values(reqs);
      if (!buckets.length) continue;
      const fulfilled = buckets.filter(opts => opts.some(c => allCompleted.has(c))).length;
      total += fulfilled / buckets.length;
      count++;
    }
    return count ? Math.round((total / count) * 100) : null;
  }, [currentPlan, majorKeys, completedSet]);

  return (
    <div style={{ fontFamily:"var(--font-sans)", padding:"2rem 1rem", maxWidth:680, margin:"0 auto" }}>
      {/* ── Header ── */}
      <div style={{ marginBottom:"1.75rem" }}>
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:"0.4rem" }}>
          <div style={{ display:"flex", alignItems:"baseline", gap:"0.6rem" }}>
            <h1 style={{ fontSize:26, fontWeight:700, margin:0, letterSpacing:"-0.5px", color:"var(--color-text-primary)" }}>
              CoursePath
            </h1>
            <span style={{
              fontSize:11, fontWeight:500, letterSpacing:"0.05em", textTransform:"uppercase",
              color:"var(--color-text-secondary)", opacity:0.7, paddingBottom:2,
            }}>UC Berkeley</span>
          </div>
          <a href="https://github.com/shirleyzxwu/CoursePath" target="_blank" rel="noopener noreferrer"
            style={{
              fontSize:12, color:"var(--color-text-secondary)", textDecoration:"none",
              border:"0.5px solid var(--color-border-tertiary)", padding:"4px 10px",
              borderRadius:"var(--border-radius-md)", opacity:0.8,
            }}>
            GitHub ↗
          </a>
        </div>
        <p style={{ fontSize:13, color:"var(--color-text-secondary)", margin:0, lineHeight:1.5 }}>
          Semantic four-year academic planner &nbsp;·&nbsp; {Object.keys(COURSES).length} courses &nbsp;·&nbsp; beam search over prerequisite graph
        </p>
      </div>

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
          <div style={{ marginTop:"1.5rem", paddingTop:"1rem", borderTop:"0.5px solid var(--color-border-tertiary)" }}>
            <p style={{ fontSize:13, fontWeight:500, color:"var(--color-text-primary)", margin:"0 0 4px" }}>
              Courses already completed
            </p>
            <p style={{ fontSize:12, color:"var(--color-text-secondary)", margin:"0 0 6px" }}>
              Comma-separated — these will be excluded from recommendations
            </p>
            <input
              value={completedInput}
              onChange={e => setCompletedInput(e.target.value)}
              placeholder="e.g. DATA C8, MATH 51, COMPSCI 61A"
              style={{ width:"100%", padding:"8px 10px", borderRadius:"var(--border-radius-md)",
                border:"0.5px solid var(--color-border-secondary)",
                background:"var(--color-background-secondary)",
                color:"var(--color-text-primary)", fontSize:13, boxSizing:"border-box" }}
            />
            {completedSet.size > 0 && (
              <p style={{ fontSize:12, color:"var(--color-text-secondary)", margin:"6px 0 0" }}>
                ✓ {completedSet.size} recognised: {[...completedSet].join(", ")}
              </p>
            )}
          </div>
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
            { key:"interest",        label:"Interest alignment",   hint:"Match to your topic profile" },
            { key:"difficulty",      label:"Difficulty penalty",   hint:"Higher = prefer easier courses" },
            { key:"professor",       label:"Professor quality",    hint:"RMP quality rating (1–5)" },
            { key:"would_take_again",label:"Would take again",     hint:"RMP % who'd retake this course" },
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

          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12, marginBottom:"1.25rem" }}>
            <div>
              <p style={{ fontSize:13, color:"var(--color-text-secondary)", margin:"0 0 4px" }}>
                Beam width — plan variants ({beamW})
              </p>
              <input type="range" min={1} max={5} step={1} value={beamW}
                onChange={e => setBeamW(+e.target.value)} style={{ width:"100%" }} />
            </div>
            <div>
              <p style={{ fontSize:13, color:"var(--color-text-secondary)", margin:"0 0 4px" }}>
                Semesters to plan
              </p>
              <select value={numSems} onChange={e => setNumSems(+e.target.value)}
                style={{ width:"100%", padding:"6px 8px", borderRadius:"var(--border-radius-md)",
                  border:"0.5px solid var(--color-border-secondary)",
                  background:"var(--color-background-secondary)",
                  color:"var(--color-text-primary)", fontSize:13 }}>
                <option value={2}>2 semesters — 1 year</option>
                <option value={4}>4 semesters — 2 years</option>
                <option value={6}>6 semesters — 3 years</option>
                <option value={8}>8 semesters — 4 years</option>
              </select>
            </div>
          </div>

          <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:"1.25rem" }}>
            <input type="checkbox" id="dq" checked={showQuality}
              onChange={e => setShowQuality(e.target.checked)} />
            <label htmlFor="dq" style={{ fontSize:13, color:"var(--color-text-secondary)", cursor:"pointer" }}>
              Show data quality indicators on courses
            </label>
          </div>

          <div style={{ marginBottom:"1.25rem", paddingTop:"0.75rem", borderTop:"0.5px solid var(--color-border-tertiary)" }}>
            <p style={{ fontSize:13, fontWeight:500, color:"var(--color-text-primary)", margin:"0 0 4px" }}>
              Major(s)
            </p>
            <p style={{ fontSize:12, color:"var(--color-text-secondary)", margin:"0 0 8px" }}>
              Select one or more to boost courses that satisfy your requirements
            </p>
            <div style={{ display:"flex", flexWrap:"wrap", gap:6, marginBottom:"0.75rem" }}>
              {Object.keys(MAJOR_TRACKS).map(m => {
                const active = selectedMajors.includes(m);
                return (
                  <button key={m} onClick={() =>
                    setSelectedMajors(prev =>
                      prev.includes(m) ? prev.filter(x => x !== m) : [...prev, m]
                    )
                  } style={{
                    fontSize:12, padding:"4px 12px",
                    borderRadius:"var(--border-radius-md)",
                    border: active ? "1px solid var(--color-text-primary)" : "0.5px solid var(--color-border-tertiary)",
                    background: active ? "var(--color-background-secondary)" : "transparent",
                    color:"var(--color-text-primary)", cursor:"pointer", fontWeight: active ? 500 : 400,
                  }}>{m}</button>
                );
              })}
            </div>
            {selectedMajors.map(m => {
              const tracks = MAJOR_TRACKS[m]?.tracks || [];
              if (tracks.length <= 1) return null;
              return (
                <div key={m} style={{ marginBottom:8 }}>
                  <p style={{ fontSize:12, color:"var(--color-text-secondary)", margin:"0 0 4px" }}>{m} track:</p>
                  <select
                    value={selectedTracks[m] || tracks[0]}
                    onChange={e => setSelectedTracks(prev => ({ ...prev, [m]: e.target.value }))}
                    style={{ fontSize:12, padding:"4px 8px", borderRadius:"var(--border-radius-md)",
                      border:"0.5px solid var(--color-border-secondary)",
                      background:"var(--color-background-secondary)",
                      color:"var(--color-text-primary)", width:"100%" }}
                  >
                    {tracks.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
              );
            })}
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
            <div style={{ display:"flex", gap:6, marginBottom:"1.1rem", flexWrap:"wrap" }}>
              {plan.map((p, i) => (
                <button key={i} onClick={() => { setActivePlan(i); setActiveSem(0); }} style={{
                  padding:"6px 14px", fontSize:12, fontWeight: activePlan===i ? 600 : 400,
                  background: activePlan===i ? "var(--color-background-secondary)" : "transparent",
                  border: activePlan===i ? "1px solid var(--color-border-primary)" : "0.5px solid var(--color-border-tertiary)",
                  borderRadius:"var(--border-radius-md)", cursor:"pointer", color:"var(--color-text-primary)",
                  letterSpacing:"-0.01em",
                }}>Plan {i+1} <span style={{ opacity:0.55, fontWeight:400 }}>· {p.score.toFixed(2)}</span></button>
              ))}
            </div>
          )}

          {/* Stats */}
          <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:8, marginBottom:"1.25rem" }}>
            <Stat label="Score" value={currentPlan.score.toFixed(2)} accent="#533AB7" />
            <Stat label="Courses" value={totalCourses} accent="#185FA5" />
            <Stat label="Units" value={totalUnits} accent="#0F6E56" />
          </div>

          {/* Major progress bar */}
          <MajorProgressBar pct={majorProgress} />

          {/* Semester grid */}
          <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:6, marginBottom:"1.25rem" }}>
            {currentPlan.semesters.map((sem, i) => (
              <button key={i} onClick={() => setActiveSem(i)} style={{
                padding:"10px 8px", fontSize:11, textAlign:"left",
                background: activeSem===i ? "var(--color-background-secondary)" : "transparent",
                border: activeSem===i ? "1px solid var(--color-border-primary)" : "0.5px solid var(--color-border-tertiary)",
                borderRadius:"var(--border-radius-md)", cursor:"pointer", color:"var(--color-text-primary)",
                transition:"background 0.1s",
              }}>
                <div style={{ fontWeight:700, fontSize:12, letterSpacing:"-0.2px" }}>{sem.year}</div>
                <div style={{ color:"var(--color-text-secondary)", marginTop:1 }}>{sem.term}</div>
                <div style={{ marginTop:5, color:"var(--color-text-secondary)", fontSize:11, opacity:0.75 }}>
                  {sem.courses.length} courses · {sem.units}u
                </div>
              </button>
            ))}
          </div>

          {/* Semester detail */}
          {currentSem && (
            <div style={{
              border:"1px solid var(--color-border-tertiary)",
              borderRadius:"var(--border-radius-lg)", padding:"1.25rem 1.5rem",
            }}>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"baseline", marginBottom:"1.1rem" }}>
                <p style={{ fontWeight:700, margin:0, fontSize:16, letterSpacing:"-0.3px", color:"var(--color-text-primary)" }}>
                  {currentSem.year} &nbsp;·&nbsp; {currentSem.term}
                </p>
                <span style={{ fontSize:12, color:"var(--color-text-secondary)" }}>
                  {currentSem.units} units &nbsp;·&nbsp; score {currentSem.score.toFixed(3)}
                </span>
              </div>

              {currentSem.courses.length === 0
                ? <p style={{ fontSize:13, color:"var(--color-text-secondary)" }}>No valid schedule found.</p>
                : currentSem.courses.map(c => <CourseCard key={c} name={c} showQuality={showQuality} />)
              }
            </div>
          )}

          <button onClick={generate} style={{
            marginTop:"1rem", padding:"8px 18px", fontSize:13, fontWeight:500,
            background:"transparent", border:"1px solid var(--color-border-secondary)",
            borderRadius:"var(--border-radius-md)", cursor:"pointer", color:"var(--color-text-primary)",
            letterSpacing:"-0.01em",
          }}>↺ Regenerate</button>
        </div>
      )}
    </div>
  );
}
