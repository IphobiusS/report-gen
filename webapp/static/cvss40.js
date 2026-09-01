// AUTO-GENERADO desde cvss/v40_lookup.py + cvss/v40_constants.py (datos == Python).
// No editar a mano. El algoritmo es un port mecanico de cvss/v40.py; NO cablear
// logica 4.0 nueva en app.js: la UI debe llamar a este modulo.
(function (root) {
const LOOKUP = {"000000": 10, "000001": 9.9, "000010": 9.8, "000011": 9.5, "000020": 9.5, "000021": 9.2, "000100": 10, "000101": 9.6, "000110": 9.3, "000111": 8.7, "000120": 9.1, "000121": 8.1, "000200": 9.3, "000201": 9, "000210": 8.9, "000211": 8, "000220": 8.1, "000221": 6.8, "001000": 9.8, "001001": 9.5, "001010": 9.5, "001011": 9.2, "001020": 9, "001021": 8.4, "001100": 9.3, "001101": 9.2, "001110": 8.9, "001111": 8.1, "001120": 8.1, "001121": 6.5, "001200": 8.8, "001201": 8, "001210": 7.8, "001211": 7, "001220": 6.9, "001221": 4.8, "002001": 9.2, "002011": 8.2, "002021": 7.2, "002101": 7.9, "002111": 6.9, "002121": 5, "002201": 6.9, "002211": 5.5, "002221": 2.7, "010000": 9.9, "010001": 9.7, "010010": 9.5, "010011": 9.2, "010020": 9.2, "010021": 8.5, "010100": 9.5, "010101": 9.1, "010110": 9, "010111": 8.3, "010120": 8.4, "010121": 7.1, "010200": 9.2, "010201": 8.1, "010210": 8.2, "010211": 7.1, "010220": 7.2, "010221": 5.3, "011000": 9.5, "011001": 9.3, "011010": 9.2, "011011": 8.5, "011020": 8.5, "011021": 7.3, "011100": 9.2, "011101": 8.2, "011110": 8, "011111": 7.2, "011120": 7, "011121": 5.9, "011200": 8.4, "011201": 7, "011210": 7.1, "011211": 5.2, "011220": 5, "011221": 3, "012001": 8.6, "012011": 7.5, "012021": 5.2, "012101": 7.1, "012111": 5.2, "012121": 2.9, "012201": 6.3, "012211": 2.9, "012221": 1.7, "100000": 9.8, "100001": 9.5, "100010": 9.4, "100011": 8.7, "100020": 9.1, "100021": 8.1, "100100": 9.4, "100101": 8.9, "100110": 8.6, "100111": 7.4, "100120": 7.7, "100121": 6.4, "100200": 8.7, "100201": 7.5, "100210": 7.4, "100211": 6.3, "100220": 6.3, "100221": 4.9, "101000": 9.4, "101001": 8.9, "101010": 8.8, "101011": 7.7, "101020": 7.6, "101021": 6.7, "101100": 8.6, "101101": 7.6, "101110": 7.4, "101111": 5.8, "101120": 5.9, "101121": 5, "101200": 7.2, "101201": 5.7, "101210": 5.7, "101211": 5.2, "101220": 5.2, "101221": 2.5, "102001": 8.3, "102011": 7, "102021": 5.4, "102101": 6.5, "102111": 5.8, "102121": 2.6, "102201": 5.3, "102211": 2.1, "102221": 1.3, "110000": 9.5, "110001": 9, "110010": 8.8, "110011": 7.6, "110020": 7.6, "110021": 7, "110100": 9, "110101": 7.7, "110110": 7.5, "110111": 6.2, "110120": 6.1, "110121": 5.3, "110200": 7.7, "110201": 6.6, "110210": 6.8, "110211": 5.9, "110220": 5.2, "110221": 3, "111000": 8.9, "111001": 7.8, "111010": 7.6, "111011": 6.7, "111020": 6.2, "111021": 5.8, "111100": 7.4, "111101": 5.9, "111110": 5.7, "111111": 5.7, "111120": 4.7, "111121": 2.3, "111200": 6.1, "111201": 5.2, "111210": 5.7, "111211": 2.9, "111220": 2.4, "111221": 1.6, "112001": 7.1, "112011": 5.9, "112021": 3, "112101": 5.8, "112111": 2.6, "112121": 1.5, "112201": 2.3, "112211": 1.3, "112221": 0.6, "200000": 9.3, "200001": 8.7, "200010": 8.6, "200011": 7.2, "200020": 7.5, "200021": 5.8, "200100": 8.6, "200101": 7.4, "200110": 7.4, "200111": 6.1, "200120": 5.6, "200121": 3.4, "200200": 7, "200201": 5.4, "200210": 5.2, "200211": 4, "200220": 4, "200221": 2.2, "201000": 8.5, "201001": 7.5, "201010": 7.4, "201011": 5.5, "201020": 6.2, "201021": 5.1, "201100": 7.2, "201101": 5.7, "201110": 5.5, "201111": 4.1, "201120": 4.6, "201121": 1.9, "201200": 5.3, "201201": 3.6, "201210": 3.4, "201211": 1.9, "201220": 1.9, "201221": 0.8, "202001": 6.4, "202011": 5.1, "202021": 2, "202101": 4.7, "202111": 2.1, "202121": 1.1, "202201": 2.4, "202211": 0.9, "202221": 0.4, "210000": 8.8, "210001": 7.5, "210010": 7.3, "210011": 5.3, "210020": 6, "210021": 5, "210100": 7.3, "210101": 5.5, "210110": 5.9, "210111": 4, "210120": 4.1, "210121": 2, "210200": 5.4, "210201": 4.3, "210210": 4.5, "210211": 2.2, "210220": 2, "210221": 1.1, "211000": 7.5, "211001": 5.5, "211010": 5.8, "211011": 4.5, "211020": 4, "211021": 2.1, "211100": 6.1, "211101": 5.1, "211110": 4.8, "211111": 1.8, "211120": 2, "211121": 0.9, "211200": 4.6, "211201": 1.8, "211210": 1.7, "211211": 0.7, "211220": 0.8, "211221": 0.2, "212001": 5.3, "212011": 2.4, "212021": 1.4, "212101": 2.4, "212111": 1.2, "212121": 0.5, "212201": 1, "212211": 0.3, "212221": 0.1};
const MAX_COMPOSED = {"eq1": {"0": ["AV:N/PR:N/UI:N/"], "1": ["AV:A/PR:N/UI:N/", "AV:N/PR:L/UI:N/", "AV:N/PR:N/UI:P/"], "2": ["AV:P/PR:N/UI:N/", "AV:A/PR:L/UI:P/"]}, "eq2": {"0": ["AC:L/AT:N/"], "1": ["AC:H/AT:N/", "AC:L/AT:P/"]}, "eq3": {"0": {"0": ["VC:H/VI:H/VA:H/CR:H/IR:H/AR:H/"], "1": ["VC:H/VI:H/VA:L/CR:M/IR:M/AR:H/", "VC:H/VI:H/VA:H/CR:M/IR:M/AR:M/"]}, "1": {"0": ["VC:L/VI:H/VA:H/CR:H/IR:H/AR:H/", "VC:H/VI:L/VA:H/CR:H/IR:H/AR:H/"], "1": ["VC:L/VI:H/VA:L/CR:H/IR:M/AR:H/", "VC:L/VI:H/VA:H/CR:H/IR:M/AR:M/", "VC:H/VI:L/VA:H/CR:M/IR:H/AR:M/", "VC:H/VI:L/VA:L/CR:M/IR:H/AR:H/", "VC:L/VI:L/VA:H/CR:H/IR:H/AR:M/"]}, "2": {"1": ["VC:L/VI:L/VA:L/CR:H/IR:H/AR:H/"]}}, "eq4": {"0": ["SC:H/SI:S/SA:S/"], "1": ["SC:H/SI:H/SA:H/"], "2": ["SC:L/SI:L/SA:L/"]}, "eq5": {"0": ["E:A/"], "1": ["E:P/"], "2": ["E:U/"]}};
const MAX_SEVERITY = {"eq1": {"0": 1, "1": 4, "2": 5}, "eq2": {"0": 1, "1": 2}, "eq3eq6": {"0": {"0": 7, "1": 6}, "1": {"0": 8, "1": 8}, "2": {"1": 10}}, "eq4": {"0": 6, "1": 5, "2": 4}, "eq5": {"0": 1, "1": 1, "2": 1}};
const EPSILON = 1e-6;

const BASE = {AV:["N","A","L","P"],AC:["L","H"],AT:["N","P"],PR:["N","L","H"],UI:["N","P","A"],
  VC:["H","L","N"],VI:["H","L","N"],VA:["H","L","N"],SC:["H","L","N"],SI:["H","L","N"],SA:["H","L","N"]};
const THREAT = {E:["X","A","P","U"]};
const ENV = {CR:["X","H","M","L"],IR:["X","H","M","L"],AR:["X","H","M","L"],MAV:["X","N","A","L","P"],
  MAC:["X","L","H"],MAT:["X","N","P"],MPR:["X","N","L","H"],MUI:["X","N","P","A"],
  MVC:["X","H","L","N"],MVI:["X","H","L","N"],MVA:["X","H","L","N"],MSC:["X","H","L","N"],
  MSI:["X","S","H","L","N"],MSA:["X","S","H","L","N"]};
const SUPP = {S:["X","N","P"],AU:["X","N","Y"],R:["X","A","U","I"],V:["X","D","C"],
  RE:["X","L","M","H"],U:["X","Clear","Green","Amber","Red"]};
const ALLOWED = Object.assign({}, BASE, THREAT, ENV, SUPP);
const METRIC_ORDER = ["AV","AC","AT","PR","UI","VC","VI","VA","SC","SI","SA","E","CR","IR","AR",
  "MAV","MAC","MAT","MPR","MUI","MVC","MVI","MVA","MSC","MSI","MSA","S","AU","R","V","RE","U"];
const ORDER_INDEX = {}; METRIC_ORDER.forEach((m,i)=>{ORDER_INDEX[m]=i;});
const BASE_KEYS = Object.keys(BASE);
const MODIFIED = ["MAV","MAC","MAT","MPR","MUI","MVC","MVI","MVA","MSC","MSI","MSA"];
const OPT_X = ["S","AU","R","V","RE","U","CR","IR","AR","E"];
const PREFIX = "CVSS:4.0";

function buildVector(m){ return PREFIX + "/" + METRIC_ORDER.filter(k => k in m).map(k => k + ":" + m[k]).join("/"); }
function parseVector(vector){
  if (typeof vector !== "string") throw new Error("vector no es cadena");
  const v = vector.trim();
  if (!v.startsWith(PREFIX + "/")) throw new Error("prefijo de version invalido");
  const parts = v.split("/").slice(1);
  if (parts.length === 0 || parts.some(p => p === "")) throw new Error("segmento vacio");
  const metrics = {}; let last = -1;
  for (const part of parts){
    const c = part.indexOf(":");
    if (c < 0) throw new Error("segmento sin ':'");
    const key = part.slice(0, c), val = part.slice(c + 1);
    if (!(key in ALLOWED)) throw new Error("metrica desconocida: " + key);
    if (ALLOWED[key].indexOf(val) < 0) throw new Error("valor invalido: " + key + ":" + val);
    const idx = ORDER_INDEX[key];
    if (idx <= last){ if (key in metrics) throw new Error("duplicada: " + key); throw new Error("fuera de orden: " + key); }
    last = idx; metrics[key] = val;
  }
  for (const m of BASE_KEYS) if (!(m in metrics)) throw new Error("falta Base: " + m);
  return metrics;
}
function effectiveMetrics(parsed){
  const m = Object.assign({}, parsed);
  for (const ab of MODIFIED) if (!(ab in m) || m[ab] === "X") m[ab] = m[ab.slice(1)];
  for (const ab of OPT_X) if (!(ab in m)) m[ab] = "X";
  return m;
}
function val(m, metric){
  const sel = m[metric];
  if (metric === "E" && sel === "X") return "A";
  if ((metric === "CR" || metric === "IR" || metric === "AR") && sel === "X") return "H";
  const mod = m["M" + metric];
  if (mod !== undefined && mod !== "X") return mod;
  return sel;
}
function eq1(av,pr,ui){ if(av==="N"&&pr==="N"&&ui==="N")return "0";
  if((av==="N"||pr==="N"||ui==="N")&&!(av==="N"&&pr==="N"&&ui==="N")&&av!=="P")return "1"; return "2"; }
function eq2(ac,at){ return (ac==="L"&&at==="N")?"0":"1"; }
function eq3(vc,vi,va){ if(vc==="H"&&vi==="H")return "0"; if(vc==="H"||vi==="H"||va==="H")return "1"; return "2"; }
function eq4(msi,msa,sc,si,sa){ if(msi==="S"||msa==="S")return "0"; if(sc==="H"||si==="H"||sa==="H")return "1"; return "2"; }
function eq5(e){ return {A:"0",P:"1",U:"2"}[e]; }
function eq6(cr,ir,ar,vc,vi,va){ if((cr==="H"&&vc==="H")||(ir==="H"&&vi==="H")||(ar==="H"&&va==="H"))return "0"; return "1"; }
function macrovector(eff){ const v=k=>val(eff,k);
  return eq1(v("AV"),v("PR"),v("UI"))+eq2(v("AC"),v("AT"))+eq3(v("VC"),v("VI"),v("VA"))+
         eq4(v("MSI"),v("MSA"),v("SC"),v("SI"),v("SA"))+eq5(v("E"))+eq6(v("CR"),v("IR"),v("AR"),v("VC"),v("VI"),v("VA")); }
const LEVELS = {
  AV:{N:0.0,A:0.1,L:0.2,P:0.3}, PR:{N:0.0,L:0.1,H:0.2}, UI:{N:0.0,P:0.1,A:0.2},
  AC:{L:0.0,H:0.1}, AT:{N:0.0,P:0.1},
  VC:{H:0.0,L:0.1,N:0.2}, VI:{H:0.0,L:0.1,N:0.2}, VA:{H:0.0,L:0.1,N:0.2},
  SC:{H:0.1,L:0.2,N:0.3}, SI:{S:0.0,H:0.1,L:0.2,N:0.3}, SA:{S:0.0,H:0.1,L:0.2,N:0.3},
  CR:{H:0.0,M:0.1,L:0.2}, IR:{H:0.0,M:0.1,L:0.2}, AR:{H:0.0,M:0.1,L:0.2} };
const DIST = ["AV","PR","UI","AC","AT","VC","VI","VA","SC","SI","SA","CR","IR","AR"];
function extract(metric, s){ const i = s.indexOf(metric) + metric.length + 1; const rest = s.slice(i);
  const j = rest.indexOf("/"); return j >= 0 ? rest.slice(0, j) : rest; }
function finalRounding(x){ return Math.round((x + EPSILON) * 10) / 10; }
function scoreEff(eff){
  const v = k => val(eff, k);
  if (["VC","VI","VA","SC","SI","SA"].every(x => v(x) === "N")) return 0.0;
  const mv = macrovector(eff); let value = LOOKUP[mv];
  const e1=+mv[0],e2=+mv[1],e3=+mv[2],e4=+mv[3],e5=+mv[4],e6=+mv[5];
  const K=(a,b,c,d,e,f)=>""+a+b+c+d+e+f; const g=k=>(k in LOOKUP)?LOOKUP[k]:NaN;
  const sEq1=g(K(e1+1,e2,e3,e4,e5,e6)), sEq2=g(K(e1,e2+1,e3,e4,e5,e6)); let sEq36;
  if (e3===0 && e6===0) sEq36 = Math.max(g(K(e1,e2,e3,e4,e5,e6+1)), g(K(e1,e2,e3+1,e4,e5,e6)));
  else if (e3===1 && e6===0) sEq36 = g(K(e1,e2,e3,e4,e5,e6+1));
  else sEq36 = g(K(e1,e2,e3+1,e4,e5,e6));
  const sEq4=g(K(e1,e2,e3,e4+1,e5,e6)), sEq5=g(K(e1,e2,e3,e4,e5+1,e6));
  const m1=MAX_COMPOSED.eq1[mv[0]], m2=MAX_COMPOSED.eq2[mv[1]], m36=MAX_COMPOSED.eq3[mv[2]][mv[5]],
        m4=MAX_COMPOSED.eq4[mv[3]], m5=MAX_COMPOSED.eq5[mv[4]];
  const maxVectors=[];
  for (const a of m1) for (const b of m2) for (const c of m36) for (const d of m4) for (const e of m5) maxVectors.push(a+b+c+d+e);
  let sd={};
  for (const mx of maxVectors){ sd={}; let neg=false;
    for (const mt of DIST){ sd[mt]=LEVELS[mt][v(mt)]-LEVELS[mt][extract(mt,mx)]; if(sd[mt]<0)neg=true; }
    if(!neg) break; }
  const cur1=sd.AV+sd.PR+sd.UI, cur2=sd.AC+sd.AT, cur36=sd.VC+sd.VI+sd.VA+sd.CR+sd.IR+sd.AR, cur4=sd.SC+sd.SI+sd.SA;
  const step=0.1;
  const avail=[value-sEq1,value-sEq2,value-sEq36,value-sEq4,value-sEq5];
  const maxsev=[MAX_SEVERITY.eq1[e1]*step, MAX_SEVERITY.eq2[e2]*step, MAX_SEVERITY.eq3eq6[e3][e6]*step, MAX_SEVERITY.eq4[e4]*step, null];
  const cur=[cur1,cur2,cur36,cur4,0.0]; let n=0; const nz=[0,0,0,0,0];
  for (let i=0;i<5;i++){ if(avail[i]>=0){ n++; const pct=(i===4)?0.0:(cur[i]/maxsev[i]); nz[i]=avail[i]*pct; } }
  const mean = n===0?0.0:(nz[0]+nz[1]+nz[2]+nz[3]+nz[4])/n;
  value = Math.max(0.0, Math.min(10.0, value - mean));
  return finalRounding(value);
}
function severity(s){ if(s===0)return "info"; if(s<=3.9)return "low"; if(s<=6.9)return "medium"; if(s<=8.9)return "high"; return "critical"; }
function score(vector){ const eff=effectiveMetrics(parseVector(vector)); const s=scoreEff(eff);
  return {score:s, severity:severity(s), vector:vector, macrovector:macrovector(eff)}; }
const API = {parseVector, effectiveMetrics, macrovector, scoreEff, score, severity, buildVector, METRIC_ORDER, BASE, ALLOWED};
if (typeof module !== "undefined" && module.exports) module.exports = API; else root.CVSS40 = API;
})(typeof window !== "undefined" ? window : this);
