let DATA = [];
const $ = id => document.getElementById(id);
// 만원 단위 → "X억 Y,YYY만원" (예: 15000 → "1억 5,000만원", 40000 → "4억", 5390 → "5,390만원")
const won = m => {
  if(m==null) return "-";
  m = Math.round(m);
  const neg = m<0 ? "-" : ""; m = Math.abs(m);
  const eok = Math.floor(m/10000), man = m%10000;
  if(eok && man) return neg+eok+"억 "+man.toLocaleString()+"만원";
  if(eok) return neg+eok+"억";
  return neg+man.toLocaleString()+"만원";
};
// 추정 현재가: 거래가 있는 '최근 2개월' 매매가 중앙값(없으면 전체 중앙값). 합법 데이터로 현재 시세에 최대한 근접.
const curPrice = a => (a.recent_price_man!=null ? a.recent_price_man : a.trade_price_man);
// 데이터 기준월 대비 마지막 거래가 몇 달 전인지(신선도)
function staleMonths(a){
  if(!a.last_deal) return null;
  const [y,m]=a.last_deal.split(".").map(Number); if(!y||!m) return null;
  const base=LOADED_UPDATED?new Date(LOADED_UPDATED):new Date();
  return (base.getFullYear()-y)*12 + (base.getMonth()+1 - m);
}
// ---- 대출 계산기 ----
// 투기과열지구(2023.1~ 기준: 서울 강남3구+용산). 정책 변동 가능 → 모달에서 LTV 직접 수정 가능.
const REG_ZONES=new Set(["강남구","서초구","송파구","용산구"]);
const FIRST_LTV=80, FIRST_CAP=60000;   // 생애최초: LTV 80%, 한도 6억원(만원)
function ltvFor(gu){return REG_ZONES.has(gu)?40:70;}
function maxLoan(sise,ltv,first){let m=sise*ltv/100;if(first)m=Math.min(m,FIRST_CAP);return Math.max(0,Math.round(m));}
// 월 상환액(만원). 원리금균등=매월 동일, 원금균등=첫 달(최대).
function monthlyPay(P,ratePct,years,method){
  const n=years*12, r=ratePct/100/12; if(P<=0||n<=0)return 0;
  if(method==="원금균등")return P/n + P*r;
  if(r===0)return P/n;
  return P*r/(1-Math.pow(1+r,-n));
}
let LOAN={method:"원리금균등"};
function openLoan(name,gu,price){
  LOAN.gu=gu;
  $("loanTitle").textContent=`${gu} · ${name}`;
  $("lnZone").textContent=REG_ZONES.has(gu)?"투기과열지구":"비규제지역";
  $("lnSise").value=price||0;
  $("lnLtv").value=ltvFor(gu);
  $("lnFirst").checked=false;
  if(!$("lnRate").value)$("lnRate").value="4.0";
  if(!$("lnYears").value)$("lnYears").value="30";
  loanRecalc(true);
  $("loanModal").hidden=false;
}
function loanRecalc(resetAmt){
  const sise=+$("lnSise").value||0, first=$("lnFirst").checked;
  let ltv=first?FIRST_LTV:(+$("lnLtv").value||0);
  if(first)$("lnLtv").value=FIRST_LTV;
  $("lnLtv").disabled=first;
  const max=maxLoan(sise,ltv,first);
  $("lnSiseW").textContent=sise?won(sise):"";
  $("lnMax").textContent=won(max);
  const amt=$("lnAmt"); amt.max=max;
  if(resetAmt||+amt.value>max||+amt.value===0)amt.value=max;
  const P=+amt.value;
  $("lnAmtW").textContent=won(P);
  const pay=monthlyPay(P,+$("lnRate").value||0,+$("lnYears").value||0,LOAN.method);
  $("lnMonthly").textContent=pay?won(Math.round(pay)):"-";
  $("lnMethodLbl").textContent=LOAN.method==="원금균등"?"(첫 달)":"";
}

// ---- 지하철 / GTX ----
let SUBWAY={stations:[],gtx:[]}, GTX_FLAT=[];
function haversine(la1,lo1,la2,lo2){const R=6371,r=Math.PI/180,dla=(la2-la1)*r,dlo=(lo2-lo1)*r,
  a=Math.sin(dla/2)**2+Math.cos(la1*r)*Math.cos(la2*r)*Math.sin(dlo/2)**2;return 2*R*Math.asin(Math.sqrt(a));}
// 단지(근사 좌표) 기준 가장 가까운 GTX역. 단지 좌표가 구/동 근사라 거리도 근사치.
function nearestGtx(a){const c=coordFor(a);if(!c||!GTX_FLAT.length)return null;
  let best=null;for(const s of GTX_FLAT){const d=haversine(c[0],c[1],s.lat,s.lon);if(!best||d<best.d)best={s,d};}
  return best?{name:best.s.name,line:best.s.line,status:best.s.status,km:Math.round(best.d*10)/10}:null;}
const SEOUL = new Set(["종로구","중구","용산구","성동구","광진구","동대문구","중랑구","성북구","강북구","도봉구","노원구","은평구","서대문구","마포구","양천구","강서구","구로구","금천구","영등포구","동작구","관악구","서초구","강남구","송파구","강동구"]);

const GU_COORDS={
 "종로구":[37.573,126.979],"중구":[37.564,126.997],"용산구":[37.532,126.990],"성동구":[37.563,127.037],
 "광진구":[37.538,127.082],"동대문구":[37.574,127.040],"중랑구":[37.606,127.093],"성북구":[37.589,127.017],
 "강북구":[37.640,127.026],"도봉구":[37.669,127.047],"노원구":[37.654,127.056],"은평구":[37.603,126.929],
 "서대문구":[37.579,126.937],"마포구":[37.566,126.902],"양천구":[37.517,126.866],"강서구":[37.551,126.850],
 "구로구":[37.495,126.888],"금천구":[37.457,126.895],"영등포구":[37.526,126.896],"동작구":[37.512,126.940],
 "관악구":[37.478,126.951],"서초구":[37.484,127.033],"강남구":[37.517,127.047],"송파구":[37.514,127.106],"강동구":[37.530,127.124],
 "수원장안":[37.304,127.011],"수원권선":[37.258,126.971],"수원팔달":[37.283,127.014],"수원영통":[37.251,127.071],
 "성남수정":[37.450,127.129],"성남중원":[37.431,127.147],"성남분당":[37.382,127.119],"의정부":[37.738,127.034],
 "안양만안":[37.388,126.932],"안양동안":[37.392,126.951],"부천":[37.503,126.766],"광명":[37.479,126.865],
 "안산상록":[37.300,126.866],"안산단원":[37.322,126.823],"고양덕양":[37.637,126.832],"고양일산동":[37.658,126.776],"고양일산서":[37.674,126.751],
 "과천":[37.429,126.988],"구리":[37.594,127.130],"남양주":[37.636,127.216],"시흥":[37.380,126.803],"군포":[37.361,126.935],
 "의왕":[37.345,126.968],"하남":[37.539,127.215],"용인처인":[37.234,127.201],"용인기흥":[37.280,127.115],"용인수지":[37.322,127.098],
 "김포":[37.615,126.716],"광주":[37.429,127.255],
 "화성동탄":[37.200,127.098],"화성병점":[37.207,127.032],"화성만세":[37.199,126.831],"화성효행":[37.218,126.962]
};
const DONG_COORDS={"상계동":[37.659,127.069],"월계동":[37.621,127.060],"창동":[37.653,127.047],"방학동":[37.668,127.044],"구로동":[37.495,126.887],"개봉동":[37.494,126.858],"가산동":[37.477,126.882],"독산동":[37.466,126.896],"중화동":[37.602,127.079],"면목동":[37.588,127.087],"마곡동":[37.560,126.825],"화곡동":[37.541,126.840],"응암동":[37.597,126.922],"신정동":[37.524,126.856],"길동":[37.537,127.139],"천호동":[37.545,127.124]};
function hj(s){let h=0;for(let i=0;i<s.length;i++)h=(h*31+s.charCodeAt(i))%1000;return(h/1000-.5)*.006;}
function coordFor(a){const b=DONG_COORDS[a.dong]||GU_COORDS[a.gu];if(!b)return null;return[b[0]+hj(a.name),b[1]+hj(a.dong+a.name)];}

// ---- 가중치 점수 ----
function weights(){return {gap:+$("wGap").value,nw:+$("wNew").value,tr:+$("wTrend").value,sc:+$("wSchool").value};}
function score(a){
  const W=weights(), tot=W.gap+W.nw+W.tr+W.sc||1;
  const ng=a.gap_ratio!=null?Math.min(a.gap_ratio,1):0;
  const nn=a.built_year?Math.max(0,Math.min(1,(25-(2026-a.built_year))/25)):0;
  const nt=a.trend_pct!=null?Math.max(0,Math.min(1,a.trend_pct/10)):0;
  const ns=a.elem_school_count?Math.min(1,a.elem_school_count/3):0;
  return Math.round(100*(W.gap*ng+W.nw*nn+W.tr*nt+W.sc*ns)/tot);
}

// ---- 필터 ----
function passFilters(a){
  const v=id=>$(id).value, n=id=>+$(id).value;
  if(n("priceMin")&&curPrice(a)<n("priceMin"))return false;
  if(n("priceMax")&&curPrice(a)>n("priceMax"))return false;
  if(n("yearMin")&&(!a.built_year||a.built_year<n("yearMin")))return false;
  if(n("yearMax")&&a.built_year&&a.built_year>n("yearMax"))return false;
  if(n("areaMin")&&a.area_m2<n("areaMin"))return false;
  if(n("areaMax")&&a.area_m2>n("areaMax"))return false;
  if(n("pyMin")&&(a.pyeong||0)<n("pyMin"))return false;
  if(n("pyMax")&&a.pyeong&&a.pyeong>n("pyMax"))return false;
  if(n("roomsMin")&&(a.rooms_est||0)<n("roomsMin"))return false;
  if(n("bathsMin")&&(a.baths_est||0)<n("bathsMin"))return false;
  if(n("hhMin")&&!(a.households>=n("hhMin")))return false;
  if(v("gapMin")&&(a.gap_ratio||0)*100<n("gapMin"))return false;
  if(v("gapMax")&&a.gap_ratio!=null&&a.gap_ratio*100>n("gapMax"))return false;
  if(v("trendMin")&&(a.trend_pct==null||a.trend_pct<n("trendMin")))return false;
  if($("schoolReq").checked&&!((a.elem_school_count||0)>=1))return false;
  if($("hideRisk").checked&&a.gap_ratio!=null&&a.gap_ratio>0.95)return false;
  if($("aptOnly").checked&&a.building_type&&a.building_type!=="아파트")return false;
  const r=v("regionSel"); if(r){const s=SEOUL.has(a.gu); if(r==="seoul"&&!s)return false; if(r==="gg"&&s)return false;}
  if(v("guSel")&&a.gu!==v("guSel"))return false;
  return true;
}
function sortRows(rows){
  const D=(a,p)=>distTo(a,p)??1e9;
  const Dboth=a=>{let s=0,n=0;if(PLACES.work){s+=D(a,PLACES.work);n++;}if(PLACES.work2){s+=D(a,PLACES.work2);n++;}return n?s:1e9;};
  const c={score:(a,b)=>score(b)-score(a),gap:(a,b)=>(b.gap_ratio||0)-(a.gap_ratio||0),trend:(a,b)=>(b.trend_pct||-99)-(a.trend_pct||-99),price:(a,b)=>curPrice(a)-curPrice(b),year:(a,b)=>(b.built_year||0)-(a.built_year||0),work:(a,b)=>D(a,PLACES.work)-D(b,PLACES.work),work2:(a,b)=>D(a,PLACES.work2)-D(b,PLACES.work2),workboth:(a,b)=>Dboth(a)-Dboth(b)}[$("sortSel").value];
  return rows.sort(c);
}
// NPay 부동산 직링크: 단지번호(baked)가 있으면 해당 단지 페이지로 직행, 없으면 검색 폴백.
// (정적 호스팅에서도 서버 없이 동작. 단지번호는 빌드 때 미리 구워짐 → scripts/resolve_complexno.py)
function naverUrl(a){
  if(a.naver_complex_no) return "https://fin.land.naver.com/complexes/"+a.naver_complex_no;
  return "https://fin.land.naver.com/search?query="+encodeURIComponent((a.dong?a.dong+" ":"")+a.name);
}
// KB시세 보기: KB시세는 앱 데이터에 없음(KB 독점) → 실제 KB시세가 표시되는 곳으로 보냄.
//  · 단지번호 있으면 네이버 단지 페이지(시세 섹션에 'KB부동산 시세' 표시)
//  · 없으면 KB부동산이 최상단에 뜨는 검색으로 폴백
function kbUrl(a){
  if(a.naver_complex_no) return "https://fin.land.naver.com/complexes/"+a.naver_complex_no;
  return "https://search.naver.com/search.naver?query="+encodeURIComponent((a.dong?a.dong+" ":"")+a.name+" KB시세");
}

// ---- 내 위치(집·회사) ----
let PLACES={}; try{PLACES=JSON.parse(localStorage.getItem("aptPlaces"))||{};}catch(e){}
// 무료 지오코딩(OSM Nominatim). 버튼 클릭 시 1~2건만 호출.
async function geocode(q){
  if(!q)return null;
  try{const r=await fetch("https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=kr&q="+encodeURIComponent(q),{headers:{"Accept-Language":"ko"}});
    const j=await r.json(); if(j&&j[0])return {lat:+j[0].lat,lng:+j[0].lon,name:q};}catch(e){}
  return null;
}
async function savePlaces(){
  const msg=$("placesMsg"); msg.textContent="좌표 찾는 중…";
  const w=$("workAddr").value.trim(), w2=$("work2Addr").value.trim();
  const [wr,wr2]=await Promise.all([geocode(w),geocode(w2)]);
  PLACES={}; if(wr)PLACES.work=wr; if(wr2)PLACES.work2=wr2;
  try{localStorage.setItem("aptPlaces",JSON.stringify(PLACES));}catch(e){}
  msg.textContent=[w?(wr?"회사1 ✓":"회사1 실패"):"",w2?(wr2?"회사2 ✓":"회사2 실패"):""].filter(Boolean).join("  ")||"주소를 입력하세요";
  render();
}
// 단지(근사좌표)→집/회사 직선거리(㎞). 단지 좌표가 구/동 근사라 거리도 근사치.
function distTo(a,p){const c=coordFor(a);if(!c||!p)return null;return haversine(c[0],c[1],p.lat,p.lng);}
// 네이버 대중교통 길찾기 직링크(실제 소요시간은 네이버에서 확인). 출발=단지 근사좌표, 도착=집/회사.
function transitUrl(a,p){
  const c=coordFor(a); if(!c||!p)return "#";
  const s=`${c[1]},${c[0]},${encodeURIComponent((a.dong?a.dong+" ":"")+a.name)},,`;
  const e=`${p.lng},${p.lat},${encodeURIComponent(p.name||"목적지")},,`;
  return `https://map.naver.com/p/directions/${s}/${e}/-/transit`;
}
function cardHTML(a){
  const newish=a.built_year&&(2026-a.built_year)<=7, age=a.built_year?(2026-a.built_year)+"년차":"-";
  const risk=a.gap_ratio!=null&&a.gap_ratio>0.95;
  const sm=staleMonths(a), stale=(a.recent_count!=null&&a.recent_count<=1)||(sm!=null&&sm>=3);
  const gx=nearestGtx(a);
  const dw=distTo(a,PLACES.work), dw2=distTo(a,PLACES.work2);
  const dwb=(dw!=null&&dw2!=null)?dw+dw2:null;
  const r1=x=>x==null?"-":(Math.round(x*10)/10)+"㎞";
  return `<span class="score">점수 ${score(a)}</span>
   <div class="name"><a href="${naverUrl(a)}" target="_blank" rel="noopener" title="네이버페이 부동산에서 '${a.dong} ${a.name}' 매물·시세 검색">${a.name} <span class="ext">↗</span></a><span class="ptag">${a.pyeong}평·${a.area_m2}㎡</span>${a._variants>1?`<span class="vtag">외 ${a._variants-1}개 평형</span>`:""}</div>
   <div class="loc">${a.gu} ${a.dong} · ${a.built_year||"?"}년(${age})</div>
   <div class="kv"><span>평형</span><b>${a.pyeong}평 · 전용 ${a.area_m2}㎡</b></div>
   <div class="kv"><span>추정 현재가</span><b class="price">${won(curPrice(a))}</b></div>
   <div class="kv"><span>KB시세(추정)</span><b>${won(curPrice(a))} <small>실거래 추정·KB값 아님</small></b></div>
   <div class="kv"><span>최근 거래</span><b>${a.last_deal||"-"}${a.recent_count?` · 최근 ${a.recent_count}건`:""}${a.trade_count?` (총 ${a.trade_count}건)`:""}</b></div>
   ${a.households?`<div class="kv"><span>세대수</span><b>${a.households.toLocaleString()}세대</b></div>`:""}
   ${a.far?`<div class="kv"><span>용적률</span><b>${a.far}%</b></div>`:""}
   ${PLACES.work?`<div class="kv"><span>🏢 회사1까지(직선)</span><b>${r1(dw)}</b></div>`:""}
   ${PLACES.work2?`<div class="kv"><span>🏢 회사2까지(직선)</span><b>${r1(dw2)}</b></div>`:""}
   ${(PLACES.work&&PLACES.work2)?`<div class="kv"><span>🏢 회사1+2 합산</span><b>${r1(dwb)}</b></div>`:""}
   <div class="kv"><span>전세가</span><b>${won(a.jeonse_price_man)}</b></div>
   <div class="kv"><span>매매-전세 갭</span><b>${a.gap_man!=null?won(a.gap_man):"-"} ${a.gap_ratio!=null?`(전세가율 ${(a.gap_ratio*100).toFixed(0)}%)`:""}</b></div>
   <div class="kv"><span>최근 추세</span><b style="color:${(a.trend_pct||0)>0?'#1E8449':'#C0392B'}">${a.trend_pct!=null?(a.trend_pct>0?"+":"")+a.trend_pct+"%":"-"}</b></div>
   <div class="kv"><span>방/욕실(근사)</span><b>방 ${a.rooms_est||"?"} · 욕실 ${a.baths_est||"?"}</b></div>
   <div class="kv"><span>학교(동 내)</span><b>초 ${a.elem_school_count||0} · 중 ${a.middle_school_count||0} · 고 ${a.high_school_count||0}</b></div>
   <div class="kv"><span>가까운 GTX</span><b>${gx?`${gx.name} ${gx.km}㎞ <small>(${gx.line}·${gx.status})</small>`:"-"}</b></div>
   <div class="badges">
     ${a.building_type&&a.building_type!=="아파트"?`<span class="badge type">${a.building_type}</span>`:''}
     ${newish?'<span class="badge">신축(7년내)</span>':'<span class="badge no">구축</span>'}
     ${(a.gap_ratio||0)>=0.8&&!risk?'<span class="badge">갭 작음</span>':''}
     ${(a.trend_pct||0)>0?'<span class="badge">상승세</span>':''}
     ${(a.rooms_est||0)>=3&&(a.baths_est||0)>=2?'<span class="badge">방3·욕2</span>':''}
     ${(a.elem_school_count||0)>=1?'<span class="badge">🏫 초품아</span>':''}
     ${gx&&gx.km<=2?`<span class="badge">🚄 GTX ${gx.km}㎞</span>`:''}
     ${stale?'<span class="badge no">⚠️시세추정 주의(거래 적음·오래됨)</span>':''}
     ${risk?'<span class="badge no">⚠️깡통위험(전세가율 95%+)</span>':''}
   </div>
   <div class="actions">
     <a class="kbbtn" href="${kbUrl(a)}" target="_blank" rel="noopener" title="앱 가격은 실거래가 기반 추정치입니다. KB시세(매매 일반평균가)는 단지 페이지의 '시세' 섹션에서 확인하세요.">🏦 KB시세 보기</a>
     <button class="loanbtn" data-n="${(a.name||'').replace(/"/g,'')}" data-g="${a.gu}" data-p="${curPrice(a)}">💰 대출 계산기</button>
   </div>
   ${(PLACES.work||PLACES.work2)?`<div class="actions">
     ${PLACES.work?`<a class="dirbtn" href="${transitUrl(a,PLACES.work)}" target="_blank" rel="noopener" title="네이버 대중교통 길찾기(실제 소요시간 확인)">🏢 회사1 대중교통</a>`:""}
     ${PLACES.work2?`<a class="dirbtn" href="${transitUrl(a,PLACES.work2)}" target="_blank" rel="noopener" title="네이버 대중교통 길찾기(실제 소요시간 확인)">🏢 회사2 대중교통</a>`:""}
   </div>`:""}`;
}

// ---- 지도 ----
let MAP=null,MARKERS=null,SUB_LAYER=null,GTX_LAYER=null;
function ensureMap(){if(MAP)return;MAP=L.map('map').setView([37.5,127.0],10);L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap'}).addTo(MAP);MARKERS=L.layerGroup().addTo(MAP);}
// 지하철(일반 회색점)·GTX(노선색+점선+역마커) 레이어를 1회 생성
function buildSubwayLayers(){
  if(SUB_LAYER||!SUBWAY.stations.length)return;
  SUB_LAYER=L.layerGroup();
  // 노선 실선(호선색, 두껍게) — 가진 노선(1~9·분당·신분당)만, 나머지 역은 점으로 보강
  (SUBWAY.lines||[]).forEach(l=>L.polyline(l.pts,{color:l.color,weight:4,opacity:.85}).addTo(SUB_LAYER));
  SUBWAY.stations.forEach(([la,lo,nm])=>L.circleMarker([la,lo],{radius:2.5,weight:0,fillColor:'#555',fillOpacity:.7}).bindTooltip(nm,{direction:'top'}).addTo(SUB_LAYER));
  // GTX — 운영 구간은 실선, 예정(공사중·계획) 구간은 점선
  GTX_LAYER=L.layerGroup();
  SUBWAY.gtx.forEach(g=>{
    const s=g.stations;
    for(let i=0;i<s.length-1;i++){const open=g.segs[i];
      L.polyline([[s[i].lat,s[i].lon],[s[i+1].lat,s[i+1].lon]],
        {color:g.color,weight:open?4:3,opacity:.85,dashArray:open?null:'7 6'}).addTo(GTX_LAYER);}
    s.forEach(st=>L.circleMarker([st.lat,st.lon],{radius:5,weight:1.5,color:'#fff',fillColor:g.color,fillOpacity:1})
      .bindTooltip(`${st.name} <b>${g.line}</b>·${st.status}`,{direction:'top'}).addTo(GTX_LAYER));
  });
}
function syncSubwayLayers(){
  if(!MAP)return; buildSubwayLayers();
  const sub=$("showSubway")&&$("showSubway").checked, gtx=!$("showGtx")||$("showGtx").checked;
  if(SUB_LAYER){sub?SUB_LAYER.addTo(MAP):MAP.removeLayer(SUB_LAYER);}
  if(GTX_LAYER){gtx?GTX_LAYER.addTo(MAP):MAP.removeLayer(GTX_LAYER);}
}
function renderMap(rows){
  ensureMap();syncSubwayLayers();MARKERS.clearLayers();const pts=[];
  rows.slice(0,500).forEach(a=>{const c=coordFor(a);if(!c)return;pts.push(c);
    const gx=nearestGtx(a);
    const m=L.circleMarker(c,{radius:7,color:'#C0392B',fillColor:'#C0392B',fillOpacity:.7,weight:1});
    m.bindPopup(`<b>${a.name}</b><br>${a.gu} ${a.dong} ${a.built_year||"?"}년<br>추정현재가 ${won(curPrice(a))}${a.last_deal?`(${a.last_deal})`:""} / 전세 ${won(a.jeonse_price_man)}<br>전세가율 ${a.gap_ratio!=null?(a.gap_ratio*100).toFixed(0)+"%":"-"} · 추세 ${a.trend_pct!=null?a.trend_pct+"%":"-"} · 점수 ${score(a)}<br>학교 초${a.elem_school_count||0}·중${a.middle_school_count||0}·고${a.high_school_count||0}${gx?`<br>🚄 가까운 GTX ${gx.name} ${gx.km}㎞ (${gx.line})`:""}<br><a href="${naverUrl(a)}" target="_blank" rel="noopener">네이버페이 부동산 ↗</a>`);
    MARKERS.addLayer(m);});
  setTimeout(()=>{MAP.invalidateSize();if(pts.length)MAP.fitBounds(pts,{padding:[30,30],maxZoom:13});},50);
}

// 매매가: 보이는 억/만원 → 숨김 priceMin/priceMax(만원)
function priceSync(){
  const calc=(e,m)=>{e=+$(e).value||0; m=+$(m).value||0; return (e||m)?(e*10000+m):"";};
  $("priceMin").value=calc("priceMinEok","priceMinMan");
  $("priceMax").value=calc("priceMaxEok","priceMaxMan");
}
// 매매가: 숨김 priceMin/priceMax(만원) → 보이는 억/만원
function priceToFields(){
  const set=(t,e,m)=>{t=+$(t).value; if(!t){$(e).value="";$(m).value="";return;} $(e).value=Math.floor(t/10000)||""; $(m).value=(t%10000)||"";};
  set("priceMin","priceMinEok","priceMinMan");
  set("priceMax","priceMaxEok","priceMaxMan");
}
// 같은 단지(구·동·이름) 묶기: 정렬 순서상 첫 항목(=대표 평형) 유지 + 나머지 평형 수 집계
function groupByComplex(rows){
  const seen=new Map(), out=[];
  for(const a of rows){
    const k=a.gu+"|"+a.dong+"|"+a.name;
    if(seen.has(k)){ seen.get(k)._variants++; continue; }
    const it=Object.assign({}, a); it._variants=1; seen.set(k,it); out.push(it);
  }
  return out;
}
function render(){
  priceSync();
  saveState();
  let rows=sortRows(DATA.filter(passFilters));
  const grouped=$("groupComplex").checked;
  const total=rows.length;
  if(grouped) rows=groupByComplex(rows);
  $("summaryText").textContent = grouped
    ? `단지 ${rows.length.toLocaleString()}곳 (조건 충족 평형 ${total.toLocaleString()}개 묶음)`
    : `조건 충족 ${rows.length.toLocaleString()}개 (전체 ${DATA.length.toLocaleString()}개 중)`;
  const c=$("cards");c.innerHTML="";
  rows.slice(0,400).forEach(a=>{const e=document.createElement("div");e.className="card";e.innerHTML=cardHTML(a);c.appendChild(e);});
  if(rows.length>400){const e=document.createElement("div");e.className="more";e.textContent=`상위 400개만 표시 (조건을 좁히면 정확해집니다). 전체 ${rows.length.toLocaleString()}개`;c.appendChild(e);}
  if($("map").style.display==="block")renderMap(rows);
}
function showView(v){const map=v==="map";$("map").style.display=map?"block":"none";$("cards").style.display=map?"none":"grid";$("viewMap").classList.toggle("active",map);$("viewCards").classList.toggle("active",!map);render();}

// ---- 프리셋 ----
const PRESETS={
 balanced:{yearMin:2019,roomsMin:3,bathsMin:2,priceMin:40000,priceMax:55000,gapMin:75,trendMin:0,areaMin:66,areaMax:110,sort:"score",hideRisk:true},
 gap:{roomsMin:3,gapMin:80,gapMax:95,trendMin:0,sort:"gap",hideRisk:true},
 cheapnew:{yearMin:2019,priceMax:50000,sort:"year",hideRisk:true},
 big:{roomsMin:4,bathsMin:2,priceMax:60000,sort:"score",hideRisk:true},
};
const ALLF=["priceMin","priceMax","yearMin","yearMax","areaMin","areaMax","pyMin","pyMax","roomsMin","bathsMin","gapMin","gapMax","trendMin","hhMin"];
function clearAll(){ALLF.forEach(i=>$(i).value="");["priceMinEok","priceMinMan","priceMaxEok","priceMaxMan"].forEach(i=>$(i).value="");$("regionSel").value="";$("guSel").value="";$("schoolReq").checked=false;$("hideRisk").checked=true;$("groupComplex").checked=true;$("aptOnly").checked=false;$("sortSel").value="score";}
function applyPreset(p){
  clearAll();
  if(p==="reset"){render();return;}
  const c=PRESETS[p];if(!c)return;
  for(const k in c){
    if(k==="sort")$("sortSel").value=c[k];
    else if(k==="hideRisk")$("hideRisk").checked=c[k];
    else if($(k))$(k).value=c[k];
  }
  priceToFields();
  render();
}

// ---- 설정 저장/복원 ----
function saveState(){
  const s={};ALLF.forEach(i=>s[i]=$(i).value);
  s.region=$("regionSel").value;s.gu=$("guSel").value;s.school=$("schoolReq").checked;s.hide=$("hideRisk").checked;s.group=$("groupComplex").checked;s.aptOnly=$("aptOnly").checked;s.sort=$("sortSel").value;
  s.gtxL=$("showGtx").checked;s.subL=$("showSubway").checked;
  s.w=[$("wGap").value,$("wNew").value,$("wTrend").value,$("wSchool").value];
  try{localStorage.setItem("aptFilters_v3",JSON.stringify(s));}catch(e){}
}
function loadState(){
  try{const s=JSON.parse(localStorage.getItem("aptFilters_v3"));if(!s)return;
    ALLF.forEach(i=>{if(s[i]!=null)$(i).value=s[i];});
    priceToFields();
    if(s.region!=null)$("regionSel").value=s.region;if(s.gu!=null)$("guSel").value=s.gu;
    $("schoolReq").checked=!!s.school;if(s.hide!=null)$("hideRisk").checked=s.hide;if(s.group!=null)$("groupComplex").checked=s.group;if(s.aptOnly!=null)$("aptOnly").checked=s.aptOnly;if(s.sort)$("sortSel").value=s.sort;
    if(s.gtxL!=null)$("showGtx").checked=s.gtxL;if(s.subL!=null)$("showSubway").checked=s.subL;
    if(s.w){["wGap","wNew","wTrend","wSchool"].forEach((id,i)=>{$(id).value=s.w[i];syncW();});}
  }catch(e){}
}
function syncW(){["Gap","New","Trend","School"].forEach(k=>$("w"+k+"V").textContent=$("w"+k).value);}

function initGu(){const gus=[...new Set(DATA.map(a=>a.gu))].sort();const sel=$("guSel");gus.forEach(g=>{const o=document.createElement("option");o.value=g;o.textContent=g;sel.appendChild(o);});}

// 데이터 기준일 신선도 라벨
function freshLabel(updated){
  if(!updated) return "";
  const d=new Date(updated); if(isNaN(d)) return "";
  const days=Math.floor((Date.now()-d.getTime())/86400000);
  if(days<=0) return "오늘"; if(days===1) return "어제"; return days+"일 전";
}
function setUpdatedLine(j){
  const date=(j.updated||"").slice(0,10), fl=freshLabel(j.updated);
  $("updated").textContent=(j.is_sample?"⚠️ 샘플 — ":"데이터 기준일: ")+date+(fl?` (${fl})`:"")
    +`  · 실거래가 기반 · ${(j.items?j.items.length:0).toLocaleString()}개 단위(서울+경기)`;
}
let LOADED_UPDATED=null;
fetch("data/apartments.json?v="+Date.now(),{cache:"no-store"}).then(r=>r.json()).then(j=>{
  DATA=j.items||[]; LOADED_UPDATED=j.updated;
  setUpdatedLine(j);
  initGu();syncW();loadState();
  if(location.hash==="#map")showView("map");else render();
  setInterval(pollStatus,20000); pollStatus();
}).catch(e=>{$("summaryText").textContent="데이터 로드 실패: "+e;});

// 지하철/GTX 좌표 로드 → 카드 'GTX 거리' & 지도 레이어. 늦게 와도 재렌더로 반영.
fetch("data/subway.json?v="+Date.now(),{cache:"no-store"}).then(r=>r.json()).then(s=>{
  SUBWAY=s; GTX_FLAT=[];
  (s.gtx||[]).forEach(g=>g.stations.forEach(st=>GTX_FLAT.push({name:st.name,lat:st.lat,lon:st.lon,status:st.status,line:g.line})));
  if(DATA.length)render();
}).catch(()=>{});

// 갱신 상태 폴링: 백그라운드 갱신 중이면 표시, 새 데이터 준비되면 새로고침 배너
function pollStatus(){
  fetch("/status",{cache:"no-store"}).then(r=>r.json()).then(s=>{
    const u=$("updated");
    if(s.refreshing && u && !u.textContent.includes("받는 중")){
      u.textContent="🔄 최신 실거래가 받는 중… "+u.textContent;
    }
    if(s.updated && LOADED_UPDATED && s.updated!==LOADED_UPDATED){
      showRefreshBanner();
    }
  }).catch(()=>{});
}
function showRefreshBanner(){
  if($("refreshBanner")) return;
  const b=document.createElement("div"); b.id="refreshBanner"; b.className="refresh-banner";
  b.innerHTML='✨ 최신 실거래가가 준비됐어요 &nbsp;<button id="rbReload">새로고침</button>';
  document.body.insertBefore(b, document.body.firstChild);
  $("rbReload").onclick=()=>location.reload();
}

$("apply").onclick=render;$("reset").onclick=()=>applyPreset("reset");$("sortSel").onchange=render;$("groupComplex").onchange=render;$("aptOnly").onchange=render;
document.querySelectorAll(".preset").forEach(b=>b.onclick=()=>applyPreset(b.dataset.preset));
document.querySelectorAll(".mini").forEach(b=>b.onclick=()=>{const a=+b.dataset.area;if(a===59){$("areaMin").value=55;$("areaMax").value=66;}else if(a===84){$("areaMin").value=78;$("areaMax").value=100;}else{$("areaMin").value="";$("areaMax").value="";}render();});
["wGap","wNew","wTrend","wSchool"].forEach(id=>$(id).oninput=()=>{syncW();render();});
$("showGtx").onchange=syncSubwayLayers;$("showSubway").onchange=syncSubwayLayers;
// 내 위치
if(PLACES.work)$("workAddr").value=PLACES.work.name||"";
if(PLACES.work2)$("work2Addr").value=PLACES.work2.name||"";
$("savePlaces").onclick=savePlaces;
// 대출 계산기
$("cards").addEventListener("click",e=>{const b=e.target.closest(".loanbtn");if(b)openLoan(b.dataset.n,b.dataset.g,+b.dataset.p);});
$("loanClose").onclick=()=>$("loanModal").hidden=true;
$("loanModal").addEventListener("click",e=>{if(e.target.id==="loanModal")$("loanModal").hidden=true;});
["lnSise","lnLtv","lnRate","lnYears"].forEach(id=>$(id).oninput=()=>loanRecalc(true));
$("lnFirst").onchange=()=>loanRecalc(true);
$("lnAmt").oninput=()=>loanRecalc(false);
document.querySelectorAll(".segb").forEach(b=>b.onclick=()=>{document.querySelectorAll(".segb").forEach(x=>x.classList.remove("active"));b.classList.add("active");LOAN.method=b.dataset.m;loanRecalc(false);});
$("viewCards").onclick=()=>showView("cards");$("viewMap").onclick=()=>showView("map");
if("serviceWorker" in navigator){navigator.serviceWorker.register("sw.js").catch(()=>{});}
