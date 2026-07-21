/* Brickfolio – Frontend-Logik */
"use strict";

const $ = (id) => document.getElementById(id);
const state = {
  token: localStorage.getItem("bf_token") || "",
  user: JSON.parse(localStorage.getItem("bf_user") || "null"),
  bricklinkPrices: false,
  catalogSearch: false,
  bricklinkLookup: false,
  collection: [],
};

/* ---------------------------------------------------------------- API */
async function api(path, options = {}) {
  const headers = options.headers || {};
  if (state.token) headers["Authorization"] = "Bearer " + state.token;
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.body);
  }
  const resp = await fetch("/api" + path, { ...options, headers });
  let data = {};
  try { data = await resp.json(); } catch (_) { /* leer */ }
  if (resp.status === 401 && path !== "/login") { logout(); throw new Error(data.detail || "Bitte neu anmelden"); }
  if (!resp.ok) throw new Error(data.detail || `Fehler ${resp.status}`);
  return data;
}

/* ---------------------------------------------------------------- UI-Helfer */
let toastTimer;
function toast(msg) {
  const el = $("toast");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 2600);
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const IMG_PLACEHOLDER = "data:image/svg+xml;utf8," + encodeURIComponent(
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 72 72">
     <rect x="12" y="26" width="48" height="30" rx="5" fill="#FFCF00" stroke="#1D1D1B" stroke-width="3"/>
     <rect x="20" y="16" width="12" height="10" rx="3" fill="#FFCF00" stroke="#1D1D1B" stroke-width="3"/>
     <rect x="40" y="16" width="12" height="10" rx="3" fill="#FFCF00" stroke="#1D1D1B" stroke-width="3"/>
   </svg>`);

function imgSrc(url) { return url ? esc(url) : IMG_PLACEHOLDER; }

function fmtEur(value) {
  return Number(value).toLocaleString("de-DE",
    { style: "currency", currency: "EUR" });
}

async function enrichSuggestions(items) {
  const payload = { items: items.slice(0, 8).map((i) => ({
    item_id: i.item_id, item_type: i.item_type || "minifig" })) };
  if (!payload.items.length) return;
  try {
    const info = await api("/suggest_info", { method: "POST", body: payload });
    applySuggestInfo(info, true);   // gespeicherte Jahre/Preise sofort zeigen
  } catch (_) { /* Badges sind nice-to-have */ }
  const hasBl = payload.items.some((i) => !/^(fig-|manuell-)/.test(i.item_id));
  if (state.bricklinkPrices && hasBl) {
    document.querySelectorAll("[data-sug-id]").forEach((card) => {
      const sub = card.querySelector("[data-sug-sub]");
      if (sub && !/^(fig-|manuell-)/.test(card.dataset.sugId)
          && sub.textContent === card.dataset.sugBase) {
        sub.textContent = card.dataset.sugBase + " · lade Jahr & Preise …";
      }
    });
    try {
      const info = await api("/suggest_info?detail=1",
        { method: "POST", body: payload });
      applySuggestInfo(info, true);
    } catch (_) { /* dito */ }
    // Ladehinweis entfernen, wo nichts kam
    document.querySelectorAll("[data-sug-id]").forEach((card) => {
      const sub = card.querySelector("[data-sug-sub]");
      if (sub && sub.textContent.endsWith("lade Jahr & Preise …")) {
        sub.textContent = card.dataset.sugBase;
      }
    });
  }
}

function wireWantButtons(box, items) {
  box.querySelectorAll("[data-want]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const it = items[Number(btn.dataset.want)];
      btn.disabled = true;
      try {
        const res = await api("/wanted", { method: "POST", body: {
          item_id: it.item_id, item_type: it.item_type || "minifig",
          name: it.name, img_url: it.img_url || "",
          bricklink_url: it.bricklink_url || "", year: it.year || 0,
        }});
        if (res.exists) toast("Steht schon auf der Wunschliste ⭐");
        else if (res.owned > 0) toast(`Gemerkt ⭐ (habt ihr schon ${res.owned}×)`);
        else toast("Auf die Wunschliste gesetzt ⭐");
        btn.textContent = "⭐ Gemerkt";
      } catch (e) {
        toast(e.message);
      } finally {
        btn.disabled = false;
      }
    });
  });
}

async function loadWanted() {
  try {
    const data = await api("/wanted");
    $("stat-wanted").textContent = data.stats.count;
    $("stat-wanted-cost").textContent = data.stats.est_cost
      ? fmtEur(data.stats.est_cost) : "–";
    $("stat-wanted-cost-new").textContent = data.stats.est_cost_new
      ? fmtEur(data.stats.est_cost_new) : "–";
    renderWanted(data.items);
  } catch (e) { toast(e.message); }
}

function renderWanted(items) {
  const list = $("wanted-list");
  $("wanted-empty").hidden = items.length > 0;
  list.innerHTML = items.map((it) => {
    const prices = [
      it.price_new ? "Ø neu " + fmtEur(it.price_new) : "",
      it.price_used ? "Ø gebr. " + fmtEur(it.price_used) : "",
    ].filter(Boolean).join(" · ");
    const needsBlNo = /^(fig-|manuell-)/.test(it.item_id);
    return `
    <div class="card" data-wid="${it.id}">
      <div class="card-head">
        <img class="card-img" src="${imgSrc(it.img_url)}" data-gid="${esc(it.item_id)}" data-gtype="${esc(it.item_type || "minifig")}" alt="" loading="lazy">
        <div class="card-title">
          <strong>${esc(it.name)}</strong>
          <div class="sub">${esc(it.item_id)}${it.year > 0 ? " · " + it.year : ""}${prices ? " · " + prices : ""}</div>
          ${it.owned > 0 ? `<span class="badge badge-owned">✔ ${it.owned}× in eurer Sammlung</span>` : ""}
          ${it.in_sets && !it.owned ? `<div class="sub in-sets">🧩 fehlt zu eurem Set: ${inSetLinks(it.in_sets)}</div>` : ""}
        </div>
      </div>
      ${needsBlNo && state.bricklinkLookup ? `
      <div class="detail-row">
        <input data-wfix-no placeholder="BrickLink-Nr. für Preise, z. B. sw0815" class="fix-input" autocapitalize="none">
        <button class="mini-btn add" data-wfix-btn>Setzen</button>
        ${it.img_url ? `<button class="mini-btn" data-wfix-auto>🔍 Auto</button>` : ""}
      </div>` : ""}
      <div class="card-actions btn-grid">
        <button class="mini-btn add" data-buy>✔ Gekauft!</button>
        ${priceGuideUrl(it) ? `<a class="mini-btn link" href="${esc(priceGuideUrl(it))}" target="_blank" rel="noopener">Preisverlauf ↗</a>` : ""}
        ${it.bricklink_url ? `<a class="mini-btn link" href="${esc(it.bricklink_url)}" target="_blank" rel="noopener">BrickLink ↗</a>` : ""}
        <button class="mini-btn danger" data-del>Löschen</button>
      </div>
    </div>`;
  }).join("");

  list.querySelectorAll(".card").forEach((card) => {
    const wid = Number(card.dataset.wid);
    const item = items.find((i) => i.id === wid);

    card.querySelectorAll("[data-jump-set]").forEach((b) => {
      b.addEventListener("click", (ev) => {
        ev.stopPropagation();
        jumpToSet(b.dataset.jumpSet);
      });
    });
    const moreBtn = card.querySelector("[data-more-sets]");
    if (moreBtn) {
      moreBtn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        const span = card.querySelector(".more-sets");
        span.hidden = !span.hidden;
        moreBtn.textContent = span.hidden
          ? `+${span.querySelectorAll(".set-link").length} weitere ▾`
          : "weniger ▴";
      });
    }

    const wfixBtn = card.querySelector("[data-wfix-btn]");
    if (wfixBtn) {
      wfixBtn.addEventListener("click", async () => {
        const no = card.querySelector("[data-wfix-no]").value.trim();
        if (!no) return;
        wfixBtn.disabled = true;
        try {
          const found = await api(`/lookup/${item.item_type}/${encodeURIComponent(no)}`);
          await api("/wanted/" + wid, { method: "PATCH", body: {
            item_id: found.item_id, name: found.name,
            img_url: found.img_url, bricklink_url: found.bricklink_url,
            year: found.year || 0,
          }});
          toast(`${found.item_id} gesetzt – hole Preise …`);
          await api(`/wanted/${wid}/refresh_prices`, { method: "POST" })
            .catch(() => {});
          loadWanted();
        } catch (e) {
          toast(e.message);
        } finally {
          wfixBtn.disabled = false;
        }
      });
    }
    const wfixAuto = card.querySelector("[data-wfix-auto]");
    if (wfixAuto) {
      wfixAuto.addEventListener("click", async () => {
        wfixAuto.disabled = true;
        wfixAuto.textContent = "Suche …";
        try {
          const data = await api("/resolve", { method: "POST",
            body: { img_url: item.img_url } });
          const filtered = (data.items || [])
            .filter((c) => !c.item_type || c.item_type === item.item_type);
          const best = filtered[0] || (data.items || [])[0];
          if (!best) {
            toast("Keine BrickLink-Nummer gefunden – bitte manuell eintragen");
            return;
          }
          await api("/wanted/" + wid, { method: "PATCH", body: {
            item_id: best.item_id, name: best.name,
            img_url: best.img_url || item.img_url,
            bricklink_url: best.bricklink_url || "",
          }});
          toast(`Gefunden: ${best.name} (${best.item_id}, ${best.score} % sicher) – hole Preise …`);
          await api(`/wanted/${wid}/refresh_prices`, { method: "POST" })
            .catch(() => {});
          loadWanted();
        } catch (e) {
          toast(e.message);
        } finally {
          wfixAuto.disabled = false;
          wfixAuto.textContent = "🔍 Auto";
        }
      });
    }

    card.querySelector("[data-buy]").addEventListener("click", () => {
      const actions = card.querySelector(".card-actions");
      const dealer = state.user && state.user.is_dealer;
      actions.innerHTML = `
        <span class="buy-label">Gekauft als:</span>
        ${dealer ? `<span class="paid-row buy-paid">
          <span class="paid-label">Preis</span>
          <input data-buy-paid class="paid-input" inputmode="decimal" placeholder="0,00">
          <span class="paid-suffix">€</span>
          <span class="sub">leer = BrickLink-Ø</span>
        </span>` : ""}
        <button class="mini-btn add" data-buy-cond="used">Gebraucht</button>
        <button class="mini-btn add" data-buy-cond="new">Neu</button>
        <button class="mini-btn" data-buy-cancel>Abbrechen</button>`;
      actions.querySelectorAll("[data-buy-cond]").forEach((b) => {
        b.addEventListener("click", async () => {
          const paidEl = actions.querySelector("[data-buy-paid]");
          let paid = null;
          if (paidEl && paidEl.value.trim() !== "") {
            paid = Number(paidEl.value.trim().replace(",", "."));
            if (!isFinite(paid) || paid < 0) {
              toast("Bitte einen gültigen Preis eingeben");
              return;
            }
          }
          b.disabled = true;
          try {
            const res = await api(`/wanted/${wid}/acquire`, { method: "POST",
              body: { condition: b.dataset.buyCond, paid_price: paid } });
            toast(res.merged
              ? "In der Sammlung: Anzahl erhöht ✔"
              : `In die Sammlung übernommen ✔ (${b.dataset.buyCond === "new" ? "Neu" : "Gebraucht"})`);
            await askSetFigures(item, b.dataset.buyCond);
            loadWanted();
          } catch (e) {
            toast(e.message);
            b.disabled = false;
          }
        });
      });
      actions.querySelector("[data-buy-cancel]").addEventListener("click",
        () => renderWanted(items));
    });
    card.querySelector("[data-del]").addEventListener("click", async () => {
      if (!confirm(`"${item.name}" von der Wunschliste löschen?`)) return;
      try {
        await api("/wanted/" + wid, { method: "DELETE" });
        loadWanted();
      } catch (e) { toast(e.message); }
    });
  });
}

function applySuggestInfo(info, withDetail) {
  document.querySelectorAll("[data-sug-id]").forEach((card) => {
    const d = info[card.dataset.sugId];
    if (!d) return;
    const ownedEl = card.querySelector("[data-owned]");
    const hasSets = d.in_sets || (d.all_sets && d.all_sets.length);
    if (hasSets) {
      const sub = card.querySelector("[data-sug-sub]");
      let el = card.querySelector(".in-sets");
      if (sub && !el) {
        el = document.createElement("div");
        el.className = "sub in-sets";
        sub.insertAdjacentElement("afterend", el);
      }
      if (el) {
        const links = [];
        const seen = new Set();
        if (d.in_sets) {
          d.in_sets.split(";;").forEach((s) => {
            const parts = s.split("|");
            const no = parts[0];
            const qty = Number(parts[parts.length - 1]) || 1;
            const name = parts.slice(1, -1).join("|");
            seen.add(no);
            links.push(`<button class="set-link owned" data-jump-set="${esc(no)}">`
              + `✔ ${esc(name)} (${esc(no)}${qty > 1 ? `, ${qty}×` : ""})</button>`);
          });
        }
        (d.all_sets || []).forEach((s) => {
          if (seen.has(s.no)) return;
          seen.add(s.no);
          links.push(`<a class="set-link ext" href="https://www.bricklink.com/v2/catalog/catalogitem.page?S=${encodeURIComponent(s.no)}" target="_blank" rel="noopener">`
            + `${esc(s.name)} (${esc(s.no)}${s.qty > 1 ? `, ${s.qty}×` : ""})</a>`);
        });
        let html = "📦 in Sets: " + links[0];
        if (links.length > 1) {
          html += `<span class="more-sets" hidden> · ${links.slice(1).join(" · ")}</span> `
            + `<button class="set-link more-toggle" data-more-sets>+${links.length - 1} weitere ▾</button>`;
        }
        el.innerHTML = html;
        el.querySelectorAll("[data-jump-set]").forEach((b) => {
          b.addEventListener("click", (ev) => {
            ev.stopPropagation();
            jumpToSet(b.dataset.jumpSet);
          });
        });
        const mb = el.querySelector("[data-more-sets]");
        if (mb) {
          mb.addEventListener("click", (ev) => {
            ev.stopPropagation();
            const span = el.querySelector(".more-sets");
            span.hidden = !span.hidden;
            mb.textContent = span.hidden
              ? `+${span.querySelectorAll(".set-link").length} weitere ▾`
              : "weniger ▴";
          });
        }
      }
    }
    if (ownedEl && d.owned > 0) {
      ownedEl.textContent = `✔ ${d.owned}× in eurer Sammlung`;
      ownedEl.hidden = false;
    } else if (ownedEl && d.wanted) {
      ownedEl.textContent = "⭐ auf eurer Wunschliste";
      ownedEl.classList.remove("badge-owned");
      ownedEl.classList.add("badge-wanted");
      ownedEl.hidden = false;
    }
    if (d.on_lists && d.on_lists.length) {
      const card2 = ownedEl ? ownedEl.closest(".card") : null;
      if (card2 && !card2.querySelector(".badge-list")) {
        const lb = document.createElement("span");
        lb.className = "badge badge-list";
        lb.textContent = d.on_lists.length === 1
          ? `🛒 auf »${d.on_lists[0]}«`
          : `🛒 auf ${d.on_lists.length} Einkaufslisten`;
        if (ownedEl && !ownedEl.hidden) ownedEl.after(lb);
        else if (ownedEl) ownedEl.parentElement.appendChild(lb);
      }
    }
    if (withDetail) {
      const sub = card.querySelector("[data-sug-sub]");
      const parts = [];
      if (d.year > 0) parts.push(String(d.year));
      if (d.new != null) parts.push("Ø neu " + fmtEur(d.new));
      if (d.used != null) parts.push("Ø gebr. " + fmtEur(d.used));
      if (sub && parts.length) {
        sub.textContent = card.dataset.sugBase + " · " + parts.join(" · ");
      }
    }
  });
}

let gallery = { urls: [], idx: 0 };

function openGallery(startUrl, gid, gtype) {
  gallery = { urls: [startUrl], idx: 0 };
  renderGallery();
  $("lightbox").hidden = false;
  if (gid && !gid.startsWith("manuell-")) {
    api(`/images/${encodeURIComponent(gtype || "minifig")}/${encodeURIComponent(gid)}`)
      .then((d) => {
        (d.images || []).forEach((u) => {
          if (u && !gallery.urls.includes(u)) gallery.urls.push(u);
        });
        renderGallery();
      })
      .catch(() => {});
  }
}

function renderGallery() {
  $("lightbox-img").src = gallery.urls[gallery.idx] || "";
  const many = gallery.urls.length > 1;
  $("lb-count").textContent = many
    ? `${gallery.idx + 1} / ${gallery.urls.length}` : "";
  $("lb-prev").hidden = !many;
  $("lb-next").hidden = !many;
}

function stepGallery(delta) {
  const n = gallery.urls.length;
  if (n < 2) return;
  gallery.idx = (gallery.idx + delta + n) % n;
  renderGallery();
}

function closeGallery() {
  $("lightbox").hidden = true;
  $("lightbox-img").src = "";
  gallery = { urls: [], idx: 0 };
}

function priceGuideUrl(it) {
  if (/^(fig-|manuell-)/.test(it.item_id)) return "";
  const prefix = BL_URL_PREFIX[it.item_type] || "M";
  return `https://www.bricklink.com/v2/catalog/catalogitem.page?${prefix}=${encodeURIComponent(it.item_id)}#T=P`;
}

// Nach dem Hinzufügen eines Sets: enthaltene Figuren mit übernehmen?
async function askSetFigures(item, condition) {
  if ((item.item_type || "") !== "set") return 0;
  const overlay = $("setfigs-overlay");
  const body = $("setfigs-body");
  if (!overlay || !body) return 0;
  let figs = [];
  try {
    const data = await api(`/set_figs/${encodeURIComponent(item.item_id)}`);
    figs = data.items || [];
  } catch (_) {
    return 0;   // keine BrickLink-Schlüssel oder Set unbekannt: still überspringen
  }
  if (!figs.length) return 0;
  const cond = condition === "new" ? "new" : "used";
  body.innerHTML = `
    <p class="search-hint">„${esc(item.name)}" enthält laut BrickLink
      <b>${figs.length} Minifigur${figs.length === 1 ? "" : "en"}</b>.
      Welche davon sind dabei?</p>
    <div class="setfigs-cond">
      <label for="setfigs-cond">Zustand der Figuren</label>
      <select id="setfigs-cond">
        <option value="used"${cond === "used" ? " selected" : ""}>Gebraucht</option>
        <option value="new"${cond === "new" ? " selected" : ""}>Neu</option>
      </select>
    </div>
    <button class="mini-btn setfigs-all" id="setfigs-toggle">Alle ab-/anwählen</button>
    <div class="setfigs-list">
      ${figs.map((f, i) => `
        <label class="setfigs-row">
          <input type="checkbox" data-fig="${i}" checked>
          <img class="card-img fig-img" src="${imgSrc(f.img_url)}" alt="" loading="lazy">
          <span><strong>${esc(f.name)}</strong><br>
            <span class="sub">${esc(f.item_id)}${f.qty > 1 ? ` · ${f.qty}× im Set` : ""}</span>
          </span>
        </label>`).join("")}
    </div>
    <div class="btn-grid">
      <button class="btn btn-outline" id="setfigs-none">Keine übernehmen</button>
      <button class="btn btn-primary" id="setfigs-ok">Übernehmen</button>
    </div>`;
  overlay.hidden = false;

  return new Promise((resolve) => {
    const finish = (n) => { overlay.hidden = true; resolve(n); };
    $("btn-setfigs-close").onclick = () => finish(0);
    $("setfigs-none").onclick = () => finish(0);
    $("setfigs-toggle").onclick = () => {
      const boxes = [...body.querySelectorAll("[data-fig]")];
      const anyOff = boxes.some((b) => !b.checked);
      boxes.forEach((b) => { b.checked = anyOff; });
    };
    $("setfigs-ok").onclick = async (ev) => {
      const btn = ev.currentTarget;
      const chosen = [...body.querySelectorAll("[data-fig]")]
        .filter((b) => b.checked).map((b) => figs[Number(b.dataset.fig)]);
      if (!chosen.length) return finish(0);
      const c = $("setfigs-cond").value;
      btn.disabled = true;
      btn.textContent = "Übernehme …";
      let done = 0;
      for (const f of chosen) {
        try {
          await api("/collection", { method: "POST", body: {
            item_id: f.item_id, item_type: "minifig", name: f.name,
            img_url: f.img_url, bricklink_url: f.bricklink_url,
            condition: c, quantity: f.qty || 1,
            // kam mit dem Set: kein eigener Kaufpreis, keine ⚙️-Schätzung
            paid_price: 0, paid_source: "set",
          }});
          done += 1;
        } catch (_) { /* einzelne Fehler überspringen */ }
      }
      toast(`${done} Figur${done === 1 ? "" : "en"} zum Set übernommen 👥`);
      finish(done);
    };
  });
}

// Beim Löschen eines Sets: enthaltene Figuren mit entfernen?
async function askRemoveSetFigures(item) {
  if ((item.item_type || "") !== "set") return 0;
  const overlay = $("setfigs-overlay");
  const body = $("setfigs-body");
  if (!overlay || !body) return 0;
  let figs = [];
  try {
    const data = await api(
      `/set_figs_owned/${encodeURIComponent(item.item_id)}`);
    figs = data.items || [];
  } catch (_) {
    return 0;
  }
  if (!figs.length) return 0;
  body.innerHTML = `
    <p class="search-hint">Zu „${esc(item.name)}" sind
      <b>${figs.length} Figur${figs.length === 1 ? "" : "en"}</b> in eurer
      Sammlung. Sollen sie mit entfernt werden?</p>
    <button class="mini-btn setfigs-all" id="setfigs-toggle">Alle ab-/anwählen</button>
    <div class="setfigs-list">
      ${figs.map((f, i) => `
        <label class="setfigs-row">
          <input type="checkbox" data-fig="${i}" checked>
          <img class="card-img fig-img" src="${imgSrc(f.img_url)}" alt="" loading="lazy">
          <span><strong>${esc(f.name)}</strong><br>
            <span class="sub">${esc(f.item_id)} ·
              ${f.condition === "new" ? "Neu" : "Gebraucht"} ·
              ${f.remove}× entfernen${f.quantity > f.remove
                ? ` (von ${f.quantity}, ${f.quantity - f.remove} bleiben)`
                : ""}</span>
          </span>
        </label>`).join("")}
    </div>
    <div class="btn-grid">
      <button class="btn btn-outline" id="setfigs-none">Figuren behalten</button>
      <button class="btn btn-primary" id="setfigs-ok">Mit entfernen</button>
    </div>`;
  overlay.hidden = false;

  return new Promise((resolve) => {
    const finish = (n) => { overlay.hidden = true; resolve(n); };
    $("btn-setfigs-close").onclick = () => finish(0);
    $("setfigs-none").onclick = () => finish(0);
    $("setfigs-toggle").onclick = () => {
      const boxes = [...body.querySelectorAll("[data-fig]")];
      const anyOff = boxes.some((b) => !b.checked);
      boxes.forEach((b) => { b.checked = anyOff; });
    };
    $("setfigs-ok").onclick = async (ev) => {
      const btn = ev.currentTarget;
      const chosen = [...body.querySelectorAll("[data-fig]")]
        .filter((b) => b.checked).map((b) => figs[Number(b.dataset.fig)]);
      if (!chosen.length) return finish(0);
      btn.disabled = true;
      btn.textContent = "Entferne …";
      let done = 0;
      for (const f of chosen) {
        const rest = f.quantity - f.remove;
        try {
          if (rest > 0) {
            await api("/collection/" + f.id, { method: "PATCH",
              body: { quantity: rest } });
          } else {
            await api("/collection/" + f.id, { method: "DELETE" });
          }
          done += 1;
        } catch (_) { /* einzelne Fehler überspringen */ }
      }
      toast(`${done} Figur${done === 1 ? "" : "en"} mit entfernt 🗑`);
      finish(done);
    };
  });
}

async function loadSetFigs(card, item, btn) {
  const out = card.querySelector("[data-figs-out]");
  if (out.dataset.loaded) {
    out.hidden = !out.hidden;
    btn.textContent = out.hidden
      ? "👥 Enthaltene Figuren anzeigen" : "👥 Figuren ausblenden";
    return;
  }
  btn.disabled = true;
  btn.textContent = "Lade Figuren …";
  try {
    const data = await api(`/set_figs/${encodeURIComponent(item.item_id)}`);
    const figs = data.items || [];
    out.dataset.loaded = "1";
    if (!figs.length) {
      out.innerHTML = `<div class="price-note">Laut BrickLink enthält dieses Set keine Minifiguren.</div>`;
    } else {
      out.innerHTML = figs.map((f, i) => `
        <div class="fig-row" data-fig-row="${i}">
          <img class="card-img fig-img" src="${imgSrc(f.img_url)}" data-gid="${esc(f.item_id)}" data-gtype="minifig" alt="" loading="lazy">
          <div class="fig-info">
            <strong>${esc(f.name)}</strong>
            <div class="sub">${esc(f.item_id)}${f.qty > 1 ? ` · ${f.qty}× im Set` : ""}
              <span class="badge badge-owned" data-fig-badge hidden></span></div>
            <div class="fig-actions" data-fig-actions>
              <button class="mini-btn add" data-fig-add="${i}">＋ Sammlung</button>
              <button class="mini-btn" data-fig-want="${i}">☆ Merken</button>
            </div>
          </div>
        </div>`).join("");
      wireFigActions(out, figs);
      const own = await markFigOwnership(out, figs);
      const missing = figs.filter((f) => {
        const d = own[f.item_id] || {};
        return !(d.owned > 0) && !d.wanted;
      });
      if (missing.length) {
        const mrow = document.createElement("div");
        mrow.className = "fig-missing-row";
        mrow.innerHTML = `<button class="mini-btn" data-want-missing>☆ ${missing.length} fehlende auf die Wunschliste</button>`;
        out.appendChild(mrow);
        mrow.querySelector("[data-want-missing]").addEventListener("click",
          async (ev) => {
            const b = ev.currentTarget;
            b.disabled = true;
            let done = 0;
            for (const f of missing) {
              try {
                await api("/wanted", { method: "POST", body: {
                  item_id: f.item_id, item_type: "minifig", name: f.name,
                  img_url: f.img_url, bricklink_url: f.bricklink_url,
                }});
                done += 1;
              } catch (_) { /* einzelne Fehler überspringen */ }
            }
            toast(`${done} Figuren auf die Wunschliste gesetzt ⭐`);
            mrow.remove();
            markFigOwnership(out, figs);
          });
      }
    }
    btn.textContent = "👥 Figuren ausblenden";
  } catch (e) {
    toast(e.message);
    btn.textContent = "👥 Enthaltene Figuren anzeigen";
  } finally {
    btn.disabled = false;
  }
}

async function markFigOwnership(out, figs) {
  const result = {};
  for (let i = 0; i < figs.length; i += 8) {
    const chunk = figs.slice(i, i + 8);
    try {
      const info = await api("/suggest_info", { method: "POST", body: {
        items: chunk.map((f) => ({ item_id: f.item_id, item_type: "minifig" })),
      }});
      chunk.forEach((f, j) => {
        result[f.item_id] = info[f.item_id] || {};
        const row = out.querySelector(`[data-fig-row="${i + j}"]`);
        const badge = row && row.querySelector("[data-fig-badge]");
        const d = info[f.item_id];
        if (!badge || !d) return;
        if (d.owned > 0) {
          badge.textContent = `✔ ${d.owned}× vorhanden`;
          badge.hidden = false;
        } else if (d.wanted) {
          badge.textContent = "⭐ auf der Wunschliste";
          badge.classList.remove("badge-owned");
          badge.classList.add("badge-wanted");
          badge.hidden = false;
        }
      });
    } catch (_) { /* Badges sind nice-to-have */ }
  }
  return result;
}

function wireFigActions(out, figs) {
  out.querySelectorAll("[data-fig-add]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const f = figs[Number(btn.dataset.figAdd)];
      const area = btn.closest("[data-fig-actions]");
      const orig = area.innerHTML;
      area.innerHTML = `
        <button class="mini-btn add" data-fc="used">Gebraucht</button>
        <button class="mini-btn add" data-fc="new">Neu</button>
        <button class="mini-btn" data-fcx>✕</button>`;
      area.querySelector("[data-fcx]").addEventListener("click", () => {
        area.innerHTML = orig;
        wireFigActions(out, figs);
      });
      area.querySelectorAll("[data-fc]").forEach((b) => {
        b.addEventListener("click", async () => {
          b.disabled = true;
          try {
            const res = await api("/collection", { method: "POST", body: {
              item_id: f.item_id, item_type: "minifig", name: f.name,
              img_url: f.img_url, bricklink_url: f.bricklink_url,
              condition: b.dataset.fc,
            }});
            toast(res.merged
              ? `Schon vorhanden – Anzahl erhöht (jetzt ${res.quantity}×)`
              : `Zur Sammlung hinzugefügt ✔ (${b.dataset.fc === "new" ? "Neu" : "Gebraucht"})`);
            area.innerHTML = orig;
            wireFigActions(out, figs);
            markFigOwnership(out, figs);
          } catch (e) {
            toast(e.message);
            b.disabled = false;
          }
        });
      });
    });
  });
  out.querySelectorAll("[data-fig-want]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const f = figs[Number(btn.dataset.figWant)];
      btn.disabled = true;
      try {
        const res = await api("/wanted", { method: "POST", body: {
          item_id: f.item_id, item_type: "minifig", name: f.name,
          img_url: f.img_url, bricklink_url: f.bricklink_url,
        }});
        if (res.exists) toast("Steht schon auf der Wunschliste ⭐");
        else if (res.owned > 0) toast(`Gemerkt ⭐ (habt ihr schon ${res.owned}×)`);
        else toast("Auf die Wunschliste gesetzt ⭐");
        markFigOwnership(out, figs);
      } catch (e) {
        toast(e.message);
      } finally {
        btn.disabled = false;
      }
    });
  });
}

function fmtPaidInput(v) {
  return v == null ? "" : v.toFixed(2).replace(".", ",");
}

function paidSrcIcon(it) {
  const date = it.paid_at
    ? new Date(it.paid_at * 1000).toLocaleDateString("de-DE") : "";
  return it.paid_source === "manual"
    ? `<span title="manuell eingetragen${date ? " am " + date : ""}">✏️</span>`
    : `<span title="automatisch: BrickLink-Ø${date ? " vom " + date : ""}">⚙️</span>`;
}

function profitLine(it) {
  if (it.paid_price == null) return "";
  const value = unitValue(it) ? unitValue(it) * it.quantity : null;
  let s = `Bezahlt ${fmtEur(it.paid_price)}`;
  if (value != null) {
    const diff = value - it.paid_price;
    const cls = diff >= 0 ? "profit-pos" : "profit-neg";
    s += ` · Wert ${fmtEur(value)} · <span class="${cls}">`
      + `${diff >= 0 ? "+" : "−"}${fmtEur(Math.abs(diff))}</span>`;
  }
  return s;
}

const TRASH_SVG = `<svg viewBox="0 0 24 24" width="18" height="18" `
  + `fill="none" stroke="currentColor" stroke-width="2.4" `
  + `stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">`
  + `<path d="M4 7h16"/><path d="M10 4h4a1 1 0 0 1 1 1v2H9V5a1 1 0 0 1 1-1z"/>`
  + `<path d="M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13"/>`
  + `<path d="M10 11v6M14 11v6"/></svg>`;

function collSubText(it) {
  let s = `${it.item_id}`
    + `${it.year > 0 ? " · " + it.year : ""}`
    + ` · ${it.condition === "new" ? "Neu" : "Gebraucht"}`
    + `${unitValue(it) ? " · Ø " + fmtEur(unitValue(it)) : ""}`;
  if (it.item_type === "set" && it.figs_total > 0) {
    s += ` · 👥 ${it.figs_owned}/${it.figs_total}`
      + `${it.figs_owned === it.figs_total ? " ✔" : ""}`;
  }
  return s;
}

function inSetLinks(raw) {
  const links = raw.split(";;").map((s) => {
    const parts = s.split("|");
    const no = parts[0];
    const qty = Number(parts[parts.length - 1]) || 1;
    const name = parts.slice(1, -1).join("|");
    return `<button class="set-link owned" data-jump-set="${esc(no)}">`
      + `✔ ${esc(name)} (${esc(no)}${qty > 1 ? `, ${qty}×` : ""})</button>`;
  });
  if (links.length <= 1) return links.join("");
  return links[0]
    + `<span class="more-sets" hidden> · ${links.slice(1).join(" · ")}</span> `
    + `<button class="set-link more-toggle" data-more-sets>+${links.length - 1} weitere ▾</button>`;
}

async function jumpToSet(setNo) {
  showTab("collection");
  $("type-filter").value = "";
  $("search").value = setNo;
  await loadCollection();
  const item = state.collection.find(
    (i) => i.item_id === setNo && i.item_type === "set");
  if (!item) { toast("Set nicht in der Sammlung gefunden"); return; }
  const card = $("collection-list").querySelector(`[data-id="${item.id}"]`);
  if (!card) return;
  const details = card.querySelector(".card-details");
  if (details && details.hidden) card.querySelector(".card-head").click();
  card.scrollIntoView({ behavior: "smooth", block: "start" });
  card.classList.add("flash");
  setTimeout(() => card.classList.remove("flash"), 1600);
}

function unitValue(it) {
  return it.condition === "new"
    ? (it.price_new ?? it.price_used)
    : (it.price_used ?? it.price_new);
}

function priceLine(label, d) {
  if (!d || !d.avg) {
    return `<div class="price-row"><span class="price-tag">${label}</span> keine Verkäufe</div>`;
  }
  const range = (d.min != null && d.max != null)
    ? ` <span class="price-range">(${fmtEur(d.min)} – ${fmtEur(d.max)})</span>` : "";
  const sold = d.times_sold != null ? ` · ${d.times_sold}× verkauft` : "";
  return `<div class="price-row"><span class="price-tag">${label}</span> `
    + `<strong>Ø ${fmtEur(d.avg)}</strong>${range}${sold}</div>`;
}

function showTab(name) {
  ["scan", "collection", "wanted", "lists", "stats", "settings"].forEach((t) => {
    $("view-" + t).hidden = t !== name;
  });
  document.querySelectorAll(".tab").forEach((b) =>
    b.classList.toggle("active", b.dataset.tab === name));
  if (name === "collection") loadCollection(true);
  if (name === "wanted") loadWanted();
  if (name === "lists") loadLists();
  if (name === "stats") loadStats();
  if (name === "settings") loadSettings();
}

/* ---------------------------------------------------------------- Login */
async function refreshMe() {
  try {
    const me = await api("/me");
    state.user = { username: me.username, is_admin: me.is_admin,
      is_dealer: me.is_dealer };
    localStorage.setItem("bf_user", JSON.stringify(state.user));
  } catch (_) { /* 401 wird von api() behandelt */ }
  updateListsTab();
  checkForUpdate(false).then((info) => {
    if (info && info.update_available && !state.updateToastShown) {
      state.updateToastShown = true;
      toast(`⬆️ Update v${info.latest} verfügbar – Details im Mehr-Tab`);
    }
  });
}

async function updateListsTab() {
  const tab = $("tab-lists");
  if (!tab) return;
  if (state.user && state.user.is_dealer) {
    tab.hidden = false;
    return;
  }
  try {
    const data = await api("/lists");
    tab.hidden = !(data.lists && data.lists.length);
  } catch (_) {
    tab.hidden = true;
  }
  if (tab.hidden && !$("view-lists").hidden) showTab("scan");
}

function applyOwnerName(name) {
  if (!name) return;
  document.querySelectorAll(".logo-name").forEach((el) => {
    el.textContent = name.toUpperCase();
  });
  document.title = name + "'s Brickfolio";
}

function showLogin() {
  $("view-login").hidden = false;
  $("app").hidden = true;
  checkSetup();
}

async function checkSetup() {
  try {
    const s = await api("/setup");
    applyOwnerName(s.owner_name);
    $("setup-box").hidden = !s.needed;
    $("login-box").hidden = s.needed;
    if (s.needed) $("setup-user").focus();
  } catch (_) {
    $("setup-box").hidden = true;
    $("login-box").hidden = false;
  }
}

async function doSetup() {
  const err = $("setup-error");
  err.hidden = true;
  const username = $("setup-user").value.trim();
  const p1 = $("setup-pass").value;
  const p2 = $("setup-pass2").value;
  if (username.length < 2) {
    err.textContent = "Bitte einen Benutzernamen eingeben (mind. 2 Zeichen)";
    err.hidden = false;
    return;
  }
  if (p1.length < 4) {
    err.textContent = "Das Passwort braucht mindestens 4 Zeichen";
    err.hidden = false;
    return;
  }
  if (p1 !== p2) {
    err.textContent = "Die Passwörter stimmen nicht überein";
    err.hidden = false;
    return;
  }
  $("btn-setup").disabled = true;
  try {
    const data = await api("/setup", { method: "POST",
      body: { username, password: p1 } });
    state.token = data.token;
    state.user = { username: data.username, is_admin: data.is_admin,
      is_dealer: data.is_dealer };
    localStorage.setItem("bf_token", data.token);
    localStorage.setItem("bf_user", JSON.stringify(state.user));
    toast(`Willkommen, ${data.username}! 🧱`);
    showApp();
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
  } finally {
    $("btn-setup").disabled = false;
  }
}

function showApp() {
  updateListsTab();
  $("view-login").hidden = true;
  $("app").hidden = false;
  $("whoami").textContent = state.user ? state.user.username : "";
  api("/config").then((c) => {
    state.offerPercent = c.offer_percent || 60;
    state.bricklinkPrices = c.bricklink_prices;
    state.catalogSearch = c.catalog_search;
    state.bricklinkLookup = c.bricklink_lookup;
    state.ownerName = c.owner_name || "Finn";
    applyOwnerName(state.ownerName);
  }).catch(() => {});
  showTab("scan");
}

async function doLogin() {
  const err = $("login-error");
  err.hidden = true;
  try {
    const data = await api("/login", {
      method: "POST",
      body: { username: $("login-user").value.trim(), password: $("login-pass").value },
    });
    state.token = data.token;
    state.user = { username: data.username, is_admin: data.is_admin,
      is_dealer: data.is_dealer };
    localStorage.setItem("bf_token", data.token);
    localStorage.setItem("bf_user", JSON.stringify(state.user));
    $("login-pass").value = "";
    showApp();
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
  }
}

function logout() {
  state.token = "";
  state.user = null;
  localStorage.removeItem("bf_token");
  localStorage.removeItem("bf_user");
  showLogin();
}

/* ---------------------------------------------------------------- Scannen */
async function handlePhoto(file) {
  if (!file) return;
  const url = URL.createObjectURL(file);
  $("preview-img").src = url;
  $("scan-preview").hidden = false;
  $("scan-status").hidden = false;
  $("scan-results").innerHTML = "";

  const form = new FormData();
  form.append("file", file, "scan.jpg");
  try {
    const data = await api("/scan", { method: "POST", body: form });
    renderScanResults(data.items || []);
  } catch (e) {
    toast(e.message);
  } finally {
    $("scan-status").hidden = true;
  }
}

function renderScanResults(items) {
  const box = $("scan-results");
  if (!items.length) {
    box.innerHTML = `<p class="empty">Keine Übereinstimmung gefunden.<br>
      Versucht es mit besserem Licht und neutralem Hintergrund.</p>`;
    return;
  }
  box.innerHTML = items.map((it, i) => {
    const scoreCls = it.score >= 60 ? "badge-score" : "badge badge-low";
    const base = `${it.item_id}${it.category ? " · " + it.category : ""}`;
    return `
    <div class="card" data-sug-id="${esc(it.item_id)}" data-sug-base="${esc(base)}">
      <div class="card-head">
        <img class="card-img" src="${imgSrc(it.img_url)}" data-gid="${esc(it.item_id)}" data-gtype="${esc(it.item_type || "minifig")}" alt="" loading="lazy">
        <div class="card-title">
          <strong>${esc(it.name)}</strong>
          <div class="sub" data-sug-sub>${esc(base)}</div>
          <span class="badge ${scoreCls}">${it.score} % sicher</span><span class="badge badge-type">${esc(it.item_type)}</span>
          <span class="badge badge-owned" data-owned hidden></span>
        </div>
      </div>
      <div class="card-actions">
        <button class="mini-btn add" data-add="${i}">＋ Zur Sammlung</button>
        <button class="mini-btn" data-want="${i}">☆ Merken</button>
        ${state.user && state.user.is_dealer ? `<button class="mini-btn" data-cart="${i}">🛒 Liste</button>` : ""}
        ${it.bricklink_url ? `<a class="mini-btn link" href="${esc(it.bricklink_url)}" target="_blank" rel="noopener">BrickLink ↗</a>` : ""}
      </div>
    </div>`;
  }).join("");

  enrichSuggestions(items);
  wireWantButtons(box, items);
  wireCartButtons(box, items);

  box.querySelectorAll("[data-add]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const it = items[Number(btn.dataset.add)];
      const card = btn.closest(".card");
      if (card.querySelector("[data-cond-row]")) return;
      const actions = card.querySelector(".card-actions");
      actions.hidden = true;
      const row = document.createElement("div");
      row.className = "card-actions btn-grid";
      row.setAttribute("data-cond-row", "");
      row.innerHTML = `
        <input data-add-paid class="paid-input" inputmode="decimal"
          placeholder="Bezahlt € (optional)" style="grid-column:1/-1">
        <span class="buy-label" style="grid-column:1/-1">Zustand wählen (wird sofort gespeichert):</span>
        <button class="mini-btn add" data-c="used">Gebraucht</button>
        <button class="mini-btn add" data-c="new">Neu</button>
        <button class="mini-btn" data-cancel style="grid-column:1/-1">Abbrechen</button>`;
      actions.after(row);
      row.querySelector("[data-cancel]").addEventListener("click", () => {
        row.remove();
        actions.hidden = false;
      });
      row.querySelectorAll("[data-c]").forEach((b) => {
        b.addEventListener("click", async () => {
          const paidRaw = row.querySelector("[data-add-paid]").value
            .trim().replace(",", ".");
          let paidPrice = null;
          if (paidRaw) {
            const n = Number(paidRaw);
            if (!Number.isFinite(n) || n < 0) {
              toast("Bezahlt bitte als Zahl, z. B. 4,50");
              return;
            }
            paidPrice = Math.round(n * 100) / 100;
          }
          b.disabled = true;
          try {
            const res = await api("/collection", { method: "POST", body: {
              item_id: it.item_id, item_type: it.item_type || "minifig",
              name: it.name, img_url: it.img_url,
              bricklink_url: it.bricklink_url,
              condition: b.dataset.c, paid_price: paidPrice,
            }});
            toast(res.merged
              ? `Schon vorhanden – Anzahl erhöht (jetzt ${res.quantity}×)`
              : `Zur Sammlung hinzugefügt ✔ (${b.dataset.c === "new" ? "Neu" : "Gebraucht"})`);
            row.remove();
            await askSetFigures(it, b.dataset.c);
            actions.hidden = false;
          } catch (e) {
            toast(e.message);
            b.disabled = false;
          }
        });
      });
    });
  });
}

/* ---------------------------------------------------------------- Sammlung */
async function loadCollection(showSpinner = false) {
  const q = $("search").value;
  const sort = $("sort").value;
  const typeFilter = $("type-filter").value;
  const list = $("collection-list");
  // Beim Öffnen des Tabs sofort eine Lade-Anzeige zeigen, damit die Sekunde
  // bis zum fertigen Aufbau nicht wie ein Hänger wirkt.
  if (showSpinner) {
    $("collection-empty").hidden = true;
    list.setAttribute("aria-busy", "true");
    list.innerHTML = '<div class="list-loading">'
      + '<svg class="spinner-brick" viewBox="0 0 48 48" width="46" height="46" '
      + 'role="status" aria-label="Sammlung wird geladen" '
      + 'xmlns="http://www.w3.org/2000/svg">'
      + '<g stroke="var(--ink)" stroke-width="2" stroke-linejoin="round">'
      + '<rect x="11" y="15" width="6" height="9" rx="2" fill="var(--yellow)"/>'
      + '<rect x="21" y="15" width="6" height="9" rx="2" fill="var(--yellow)"/>'
      + '<rect x="31" y="15" width="6" height="9" rx="2" fill="var(--yellow)"/>'
      + '<rect x="8" y="22" width="32" height="14" rx="3" fill="var(--yellow)"/>'
      + '</g></svg>'
      + '<span>Sammlung wird geladen …</span></div>';
    // Dem Browser eine Bildaufbau-Runde geben, damit der Spinner sichtbar ist,
    // bevor der (bei großer Sammlung rechenintensive) Aufbau beginnt.
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  }
  try {
    const data = await api("/collection?q=" + encodeURIComponent(q)
      + "&sort=" + encodeURIComponent(sort)
      + "&item_type=" + encodeURIComponent(typeFilter));
    state.collection = data.items;
    $("stat-total").textContent = data.stats.total;
    $("stat-unique").textContent = data.stats.unique_items;
    $("stat-value").textContent = data.stats.total_value
      ? fmtEur(data.stats.total_value) : "–";
    $("stat-value-sub").textContent = data.stats.unpriced > 0
      ? `Wert · ${data.stats.unpriced} ohne Preis`
      : "Wert (BrickLink Ø)";
    renderCollection();
  } catch (e) {
    toast(e.message);
  } finally {
    list.removeAttribute("aria-busy");
  }
}

function applyCollView() {
  const list = $("collection-list");
  const btn = $("btn-collview");
  const grid = localStorage.getItem("bf_collview") === "grid";
  if (list) list.classList.toggle("grid-mode", grid);
  if (btn) {
    btn.textContent = grid ? "▦" : "▤";
    btn.title = grid ? "Ansicht: Raster (tippen für Liste)"
                     : "Ansicht: Liste (tippen für Raster)";
  }
}

function collCardDetails(it) {
  const needsBlNo = /^(fig-|manuell-)/.test(it.item_id);
  return `
      <div class="card-details" hidden>
        <div class="qty-edit">
          <span class="qty-edit-label">Anzahl</span>
          <div class="qty">
            <button data-qty="-1" class="${it.quantity <= 1 ? "qty-del" : ""}" aria-label="${it.quantity <= 1 ? "Aus der Sammlung löschen" : "Anzahl verringern"}">${it.quantity <= 1 ? TRASH_SVG : "−"}</button>
            <span data-qty-val>${it.quantity}</span>
            <button data-qty="1" aria-label="Anzahl erhöhen">＋</button>
          </div>
        </div>
        <label>Zustand</label>
        <div class="detail-row">
          <button class="mini-btn cond ${it.condition === "used" ? "sel" : ""}" data-cond="used">Gebraucht</button>
          <button class="mini-btn cond ${it.condition === "new" ? "sel" : ""}" data-cond="new">Neu</button>
        </div>
        ${state.user && state.user.is_dealer ? `
        <div class="paid-block">
          <div class="detail-row paid-row">
            <span class="paid-label">Bezahlt</span>
            <input data-paid class="paid-input" inputmode="decimal"
              placeholder="0,00" value="${fmtPaidInput(it.paid_price)}">
            <span class="paid-suffix">€ <span data-paid-src>${it.paid_price != null ? paidSrcIcon(it) : ""}</span></span>
            <button class="mini-btn add" data-paid-save>Speichern</button>
          </div>
          <div class="sub profit-line" data-profit>${profitLine(it)}</div>
        </div>` : ""}
        <label>Notizen</label>
        <textarea data-notes placeholder="z. B. Zustand, Herkunft, Set …">${esc(it.notes)}</textarea>
        ${needsBlNo && state.bricklinkLookup ? `
        <label>BrickLink-Nr. setzen (für Preise & exakte Variante)</label>
        <div class="detail-row">
          <input data-fix-no placeholder="z. B. sw0815" autocapitalize="none" class="fix-input">
          <button class="mini-btn add" data-fix-btn>Übernehmen</button>
          ${it.img_url ? `<button class="mini-btn" data-fix-auto>🔍 Automatisch</button>` : ""}
        </div>` : ""}
        <div class="detail-row btn-grid">
          <button class="mini-btn" data-save-notes>Notiz speichern</button>
          ${state.bricklinkPrices && !needsBlNo ? `<button class="mini-btn" data-price>↻ Preise aktualisieren</button>` : ""}
          ${priceGuideUrl(it) ? `<a class="mini-btn link" href="${esc(priceGuideUrl(it))}" target="_blank" rel="noopener">Preisverlauf ↗</a>` : ""}
          ${it.bricklink_url ? `<a class="mini-btn link" href="${esc(it.bricklink_url)}" target="_blank" rel="noopener">BrickLink ↗</a>` : ""}
          <button class="mini-btn danger" data-delete>Löschen</button>
        </div>
        ${it.item_type === "set" && state.bricklinkPrices ? `
        <div class="detail-row">
          <button class="mini-btn" data-figs>👥 Enthaltene Figuren anzeigen</button>
        </div>
        <div class="set-figs" data-figs-out></div>` : ""}
        <div class="price-result" data-price-out></div>
        <div class="price-history" data-history></div>
        <div class="meta">Erfasst von ${esc(it.added_by_name || "unbekannt")} am ${new Date(it.added_at * 1000).toLocaleDateString("de-DE")}</div>
      </div>`;
}

function renderCollection() {
  const list = $("collection-list");
  const items = state.collection;
  applyCollView();
  $("collection-empty").hidden = items.length > 0 || $("search").value.trim() !== "";
  // Nur die Karten-Köpfe rendern; der (umfangreiche) Detailblock wird erst
  // beim ersten Aufklappen erzeugt. Das hält das DOM bei großen Sammlungen
  // schlank, damit Antippen und Suchen sofort reagieren.
  list.innerHTML = items.map((it) => `
    <div class="card" data-id="${it.id}">
      <div class="card-head">
        <img class="card-img" src="${imgSrc(it.img_url)}" data-gid="${esc(it.item_id)}" data-gtype="${esc(it.item_type || "minifig")}" alt="" loading="lazy">
        <span class="qty-badge" data-qty-val>${it.quantity}</span>
        <div class="card-title">
          <strong>${esc(it.name)}</strong>
          <div class="sub" data-sub>${esc(collSubText(it))}</div>
          ${it.in_sets ? `<div class="sub in-sets">📦 aus Set: ${inSetLinks(it.in_sets)}</div>` : ""}
        </div>
        <div class="qty">
          <button data-qty="-1" class="${it.quantity <= 1 ? "qty-del" : ""}" aria-label="${it.quantity <= 1 ? "Aus der Sammlung löschen" : "Anzahl verringern"}">${it.quantity <= 1 ? TRASH_SVG : "−"}</button>
          <span data-qty-val>${it.quantity}</span>
          <button data-qty="1" aria-label="Anzahl erhöhen">＋</button>
        </div>
      </div>
    </div>`).join("");

  list.querySelectorAll(".card").forEach((card) => {
    const id = Number(card.dataset.id);
    const item = items.find((i) => i.id === id);
    const canPrice = state.bricklinkPrices && !/^(fig-|manuell-)/.test(item.item_id);

    const deleteEntry = async () => {
      if (!confirm(`"${item.name}" wirklich löschen?`)) return;
      try {
        // Erst fragen (solange das Set noch da ist), dann löschen
        await askRemoveSetFigures(item);
        await api("/collection/" + id, { method: "DELETE" });
        loadCollection();
      } catch (e) { toast(e.message); }
    };

    // Mengen-Knöpfe verdrahten (im Kopf sofort, im Detailbereich nach dem
    // Aufklappen). `root` grenzt ein, welche Knöpfe gemeint sind.
    const wireQty = (root) => {
      root.querySelectorAll("[data-qty]").forEach((btn) => {
        btn.addEventListener("click", async (ev) => {
          ev.stopPropagation();
          const step = Number(btn.dataset.qty);
          // Letztes Exemplar: derselbe Ablauf wie der Löschen-Knopf
          if (step < 0 && item.quantity <= 1) { await deleteEntry(); return; }
          const newQty = item.quantity + step;
          if (newQty < 1) return;
          try {
            await api("/collection/" + id, { method: "PATCH", body: { quantity: newQty } });
            item.quantity = newQty;
            card.querySelectorAll("[data-qty-val]").forEach((s) => {
              s.textContent = newQty;
            });
            // Minus-Knopf wird zum Papierkorb, sobald nur noch eines übrig ist
            card.querySelectorAll('[data-qty="-1"]').forEach((b) => {
              b.innerHTML = newQty <= 1 ? TRASH_SVG : "−";
              b.classList.toggle("qty-del", newQty <= 1);
              b.setAttribute("aria-label", newQty <= 1
                ? "Aus der Sammlung löschen" : "Anzahl verringern");
            });
            updateStatsOnly();
          } catch (e) { toast(e.message); }
        });
      });
    };

    card.querySelectorAll("[data-jump-set]").forEach((b) => {
      b.addEventListener("click", (ev) => {
        ev.stopPropagation();
        jumpToSet(b.dataset.jumpSet);
      });
    });

    const moreBtn = card.querySelector("[data-more-sets]");
    if (moreBtn) {
      moreBtn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        const span = card.querySelector(".more-sets");
        span.hidden = !span.hidden;
        moreBtn.textContent = span.hidden
          ? `+${span.querySelectorAll(".set-link").length} weitere ▾`
          : "weniger ▴";
      });
    }

    wireQty(card.querySelector(".card-head"));

    card.querySelector(".card-head").addEventListener("click", (ev) => {
      if (ev.target.closest(".qty") || ev.target.closest(".card-img")
          || ev.target.closest(".set-link")) return;
      let details = card.querySelector(".card-details");
      if (!details) {
        // Detailblock erst jetzt bauen und verdrahten
        card.insertAdjacentHTML("beforeend", collCardDetails(item));
        details = card.querySelector(".card-details");
        wireCollectionDetails(card, item, id, deleteEntry, wireQty);
      }
      details.hidden = !details.hidden;
      card.classList.toggle("open", !details.hidden);
      if (!details.hidden && canPrice && !details.dataset.priced) {
        details.dataset.priced = "1";
        loadEntryPrice(card, item, false);
      }
    });
  });
}

function wireCollectionDetails(card, item, id, deleteEntry, wireQty) {
  const details = card.querySelector(".card-details");

  details.querySelectorAll("[data-cond]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const cond = btn.dataset.cond;
      if (cond === item.condition) return;
      try {
        const res = await api("/collection/" + id, { method: "PATCH",
          body: { condition: cond } });
        if (res.merged) {
          toast("Mit dem vorhandenen Eintrag in diesem Zustand "
            + "zusammengeführt ✔");
          loadCollection();
          return;
        }
        item.condition = cond;
        card.querySelectorAll("[data-cond]").forEach((b) =>
          b.classList.toggle("sel", b.dataset.cond === cond));
        const sub = card.querySelector(".card-head .sub");
        if (sub) sub.textContent = collSubText(item);
        updateStatsOnly();
        toast(cond === "new" ? "Zustand: Neu ✔" : "Zustand: Gebraucht ✔");
      } catch (e) { toast(e.message); }
    });
  });

  wireQty(details);

  const paidBtn = card.querySelector("[data-paid-save]");
  if (paidBtn) {
    paidBtn.addEventListener("click", async () => {
      const raw = card.querySelector("[data-paid]").value.trim()
        .replace(",", ".");
      const paid = raw === "" ? null : Number(raw);
      if (raw !== "" && (!isFinite(paid) || paid < 0)) {
        toast("Bitte einen gültigen Betrag eingeben");
        return;
      }
      if (raw === "") { toast("Zum Entfernen 0 eintragen"); return; }
      paidBtn.disabled = true;
      try {
        await api("/collection/" + id, { method: "PATCH",
          body: { paid_price: paid } });
        item.paid_price = paid;
        item.paid_source = "manual";
        item.paid_at = Math.floor(Date.now() / 1000);
        card.querySelector("[data-paid]").value = fmtPaidInput(paid);
        card.querySelector("[data-paid-src]").innerHTML = paidSrcIcon(item);
        card.querySelector("[data-profit]").innerHTML = profitLine(item);
        toast("Kaufpreis gespeichert ✔");
      } catch (e) {
        toast(e.message);
      } finally {
        paidBtn.disabled = false;
      }
    });
  }

  const figsBtn = card.querySelector("[data-figs]");
  if (figsBtn) {
    figsBtn.addEventListener("click", () => loadSetFigs(card, item, figsBtn));
  }

  const fixAutoBtn = card.querySelector("[data-fix-auto]");
  if (fixAutoBtn) {
    fixAutoBtn.addEventListener("click", async () => {
      fixAutoBtn.disabled = true;
      fixAutoBtn.textContent = "Suche …";
      try {
        const data = await api("/resolve", { method: "POST",
          body: { img_url: item.img_url } });
        const filtered = (data.items || [])
          .filter((c) => !c.item_type || c.item_type === item.item_type);
        const best = filtered[0] || (data.items || [])[0];
        if (!best) {
          toast("Keine BrickLink-Nummer gefunden – bitte manuell eintragen");
          return;
        }
        await api("/collection/" + id, { method: "PATCH", body: {
          item_id: best.item_id, name: best.name,
          img_url: best.img_url || item.img_url,
          bricklink_url: best.bricklink_url || "",
        }});
        toast(`Gefunden: ${best.name} (${best.item_id}, ${best.score} % sicher) ✔`);
        loadCollection();
      } catch (e) {
        toast(e.message);
      } finally {
        fixAutoBtn.disabled = false;
        fixAutoBtn.textContent = "🔍 Automatisch";
      }
    });
  }

  const fixBtn = card.querySelector("[data-fix-btn]");
  if (fixBtn) {
    fixBtn.addEventListener("click", async () => {
      const no = card.querySelector("[data-fix-no]").value.trim();
      if (!no) return;
      fixBtn.disabled = true;
      try {
        const found = await api(`/lookup/${item.item_type}/${encodeURIComponent(no)}`);
        await api("/collection/" + id, { method: "PATCH", body: {
          item_id: found.item_id, name: found.name,
          img_url: found.img_url, bricklink_url: found.bricklink_url,
          year: found.year || 0,
        }});
        toast(`Aktualisiert: ${found.name} (${found.item_id}) ✔`);
        loadCollection();
      } catch (e) {
        toast(e.message);
      } finally {
        fixBtn.disabled = false;
      }
    });
  }

  card.querySelector("[data-save-notes]").addEventListener("click", async () => {
    try {
      await api("/collection/" + id, { method: "PATCH",
        body: { notes: card.querySelector("[data-notes]").value } });
      toast("Notiz gespeichert ✔");
    } catch (e) { toast(e.message); }
  });

  card.querySelector("[data-delete]").addEventListener("click", deleteEntry);

  const priceBtn = card.querySelector("[data-price]");
  if (priceBtn) {
    priceBtn.addEventListener("click", () => loadEntryPrice(card, item, true));
  }
}

async function loadEntryPrice(card, item, refresh) {
  const out = card.querySelector("[data-price-out]");
  out.textContent = refresh ? "Hole frische Preise von BrickLink …" : "Lade Preise …";
  try {
    const p = await api(`/collection/${item.id}/price${refresh ? "?refresh=1" : ""}`);
    if (!refresh && !p.updated_at) {
      // frisch erfasste Figur, Hintergrund-Abruf noch nicht durch → einmal live holen
      return loadEntryPrice(card, item, true);
    }
    const stand = p.updated_at
      ? new Date(p.updated_at * 1000).toLocaleDateString("de-DE") : "";
    out.innerHTML = priceLine("Neu", p.new) + priceLine("Gebraucht", p.used)
      + `<div class="price-note">Ø-Verkaufspreise, letzte 6 Monate (BrickLink)`
      + `${stand ? " · Stand " + stand : ""}</div>`;
    // Frische Preise sofort in Karte und Rechnung übernehmen
    if (p.new && p.new.avg != null) item.price_new = p.new.avg;
    if (p.used && p.used.avg != null) item.price_used = p.used.avg;
    const subEl = card.querySelector("[data-sub]");
    if (subEl) subEl.textContent = collSubText(item);
    const profitEl = card.querySelector("[data-profit]");
    if (profitEl) profitEl.innerHTML = profitLine(item);
    if (refresh) updateStatsOnly();   // Wert-Widget mitziehen
    loadPriceHistory(card, item);
  } catch (e) {
    out.textContent = e.message;
  }
}

async function loadPriceHistory(card, item) {
  const box = card.querySelector("[data-history]");
  if (!box) return;
  try {
    const data = await api(`/history/${encodeURIComponent(item.item_type)}/${encodeURIComponent(item.item_id)}`);
    const pts = (data.points || []).filter((p) => p.price_new || p.price_used);
    box.innerHTML = pts.length >= 2 ? historyChart(pts)
      : (pts.length === 1
         ? `<div class="price-note">Preisverlauf: Aufzeichnung gestartet – Chart erscheint, sobald weitere Datenpunkte vorliegen.</div>`
         : "");
  } catch (_) { box.innerHTML = ""; }
}

function historyChart(pts) {
  const w = 560, h = 130, padX = 8, padT = 10, padB = 22;
  const values = [];
  pts.forEach((p) => {
    if (p.price_new) values.push(p.price_new);
    if (p.price_used) values.push(p.price_used);
  });
  let lo = Math.min(...values), hi = Math.max(...values);
  if (hi - lo < 0.01) { lo -= 1; hi += 1; }
  const t0 = pts[0].ts, t1 = pts[pts.length - 1].ts || t0 + 1;
  const x = (ts) => padX + ((ts - t0) / Math.max(1, t1 - t0)) * (w - 2 * padX);
  const y = (v) => padT + (1 - (v - lo) / (hi - lo)) * (h - padT - padB);
  const line = (key) => pts.filter((p) => p[key])
    .map((p) => `${x(p.ts).toFixed(1)},${y(p[key]).toFixed(1)}`).join(" ");
  const dots = (key, color) => pts.filter((p) => p[key]).map((p) =>
    `<circle cx="${x(p.ts).toFixed(1)}" cy="${y(p[key]).toFixed(1)}" r="3.5" fill="${color}"/>`).join("");
  const dFmt = (ts) => new Date(ts * 1000).toLocaleDateString("de-DE",
    { day: "2-digit", month: "2-digit", year: "2-digit" });
  return `
  <svg viewBox="0 0 ${w} ${h}" class="history-svg" role="img" aria-label="Preisverlauf">
    <line x1="${padX}" y1="${h - padB}" x2="${w - padX}" y2="${h - padB}" stroke="#D4D7DC" stroke-width="1.5"/>
    <polyline points="${line("price_new")}" fill="none" stroke="#0057A6" stroke-width="2.5"/>
    <polyline points="${line("price_used")}" fill="none" stroke="#00963E" stroke-width="2.5"/>
    ${dots("price_new", "#0057A6")}${dots("price_used", "#00963E")}
    <text x="${padX}" y="${h - 6}" class="hist-label">${dFmt(t0)}</text>
    <text x="${w - padX}" y="${h - 6}" text-anchor="end" class="hist-label">${dFmt(t1)}</text>
    <text x="${padX}" y="${padT + 2}" class="hist-label">${fmtEur(hi)}</text>
    <text x="${padX}" y="${h - padB - 4}" class="hist-label">${fmtEur(lo)}</text>
  </svg>
  <div class="price-note"><span class="hist-dot" style="background:#0057A6"></span> Neu
    &nbsp;<span class="hist-dot" style="background:#00963E"></span> Gebraucht
    · eigene Aufzeichnung seit Erfassung</div>`;
}

async function updateStatsOnly() {
  try {
    const data = await api("/collection?q=");
    $("stat-total").textContent = data.stats.total;
    $("stat-unique").textContent = data.stats.unique_items;
    $("stat-value").textContent = data.stats.total_value
      ? fmtEur(data.stats.total_value) : "–";
    $("stat-value-sub").textContent = data.stats.unpriced > 0
      ? `Wert · ${data.stats.unpriced} ohne Preis`
      : "Wert (BrickLink Ø)";
  } catch (_) { /* still */ }
}

/* ---------------------------------------------------------------- Manuell erfassen */
const BL_URL_PREFIX = { minifig: "M", part: "P", set: "S" };
let suggestTimer;
let manualSelection = null;   // übernommener Vorschlag (Bild + BrickLink-Link)

function setupCatalogSearch() {
  $("m-name").addEventListener("input", () => {
    manualSelection = null;
    clearTimeout(suggestTimer);
    suggestTimer = setTimeout(runCatalogSearch, 450);
  });
  $("m-id").addEventListener("input", () => {
    manualSelection = null;
    clearTimeout(suggestTimer);
    suggestTimer = setTimeout(runBricklinkLookup, 550);
  });
  $("m-type").addEventListener("change", () => {
    if ($("m-id").value.trim().length >= 3) runBricklinkLookup();
    else runCatalogSearch();
  });
}

async function runBricklinkLookup() {
  const no = $("m-id").value.trim();
  const box = $("m-suggestions");
  const hint = $("m-search-hint");
  if (!state.bricklinkLookup || no.length < 3) return;
  hint.textContent = "Suche bei BrickLink …";
  hint.hidden = false;
  const found = await lookupNumber(no);
  if (found.length) {
    renderSuggestions(found);
    hint.hidden = true;
  } else {
    box.innerHTML = "";
    hint.textContent = `"${no}" nicht im BrickLink-Katalog gefunden`;
  }
}

const BL_NO_RE = /^[a-z]{2,4}\d{2,5}[a-z0-9]*$/i;   // sw0815, cty1234, hp123a …
const NUM_NO_RE = /^\d{3,7}(-\d{1,2})?$/;           // 75154, 75154-1, 3001 …

async function lookupNumber(no) {
  // Reine Zahl kann Set ODER Teil sein – gewählten Typ zuerst, dann die anderen
  const primary = $("m-type").value;
  const digits = NUM_NO_RE.test(no);
  const types = digits
    ? [...new Set([primary, "set", "part"])]
    : [primary];
  const found = [];
  for (const t of types) {
    try {
      found.push(await api(`/lookup/${t}/${encodeURIComponent(no)}`));
    } catch (_) { /* dieser Typ kennt die Nummer nicht */ }
    if (!digits) break;
  }
  return found;
}

async function runCatalogSearch() {
  const q = $("m-name").value.trim();
  const box = $("m-suggestions");
  const hint = $("m-search-hint");
  if (q.length < 2) {
    box.innerHTML = "";
    hint.hidden = true;
    return;
  }
  // Sieht nach BrickLink-Nummer aus? Dann zuerst dort direkt nachschlagen.
  if (state.bricklinkLookup && (BL_NO_RE.test(q) || NUM_NO_RE.test(q))) {
    hint.textContent = "Suche bei BrickLink …";
    hint.hidden = false;
    const found = await lookupNumber(q);
    if (found.length) {
      renderSuggestions(found);
      hint.hidden = true;
      return;
    }
    /* kein Treffer – unten normal bei Rebrickable suchen */
  }
  if (!state.catalogSearch) {
    box.innerHTML = "";
    hint.hidden = true;
    return;
  }
  hint.textContent = "Suche im Katalog …";
  hint.hidden = false;
  try {
    const data = await api(`/search?q=${encodeURIComponent(q)}&item_type=${$("m-type").value}`);
    renderSuggestions(data.items || []);
    hint.hidden = true;
  } catch (e) {
    hint.textContent = e.message;
  }
}

function renderSuggestions(items) {
  const box = $("m-suggestions");
  if (!items.length) {
    box.innerHTML = "";
    const hint = $("m-search-hint");
    hint.textContent = "Nichts gefunden – einfach weitertippen oder unten manuell speichern.";
    hint.hidden = false;
    return;
  }
  box.innerHTML = items.map((it, i) => {
    const base = `${it.item_id}${it.sub ? " · " + it.sub : ""}`;
    return `
    <div class="card" data-sug-id="${esc(it.item_id)}" data-sug-base="${esc(base)}">
      <div class="card-head">
        <img class="card-img" src="${imgSrc(it.img_url)}" data-gid="${esc(it.item_id)}" data-gtype="${esc(it.item_type || "minifig")}" alt="" loading="lazy">
        <div class="card-title">
          <strong>${esc(it.name)}</strong>
          <div class="sub" data-sug-sub>${esc(base)}</div>
          <span class="badge badge-owned" data-owned hidden></span>
        </div>
      </div>
      <div class="card-actions">
        <button class="mini-btn add" data-suggest="${i}">✔ Übernehmen</button>
        <button class="mini-btn" data-want="${i}">☆ Merken</button>
        ${state.user && state.user.is_dealer ? `<button class="mini-btn" data-cart="${i}">🛒 Liste</button>` : ""}
        ${it.bricklink_url ? `<a class="mini-btn link" href="${esc(it.bricklink_url)}" target="_blank" rel="noopener">BrickLink ↗</a>` : ""}
      </div>
    </div>`;
  }).join("");

  enrichSuggestions(items);
  wireWantButtons(box, items);
  wireCartButtons(box, items);

  box.querySelectorAll("[data-suggest]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const it = items[Number(btn.dataset.suggest)];
      $("m-name").value = it.name;
      $("m-id").value = it.item_id;
      if (it.item_type) $("m-type").value = it.item_type;
      manualSelection = { item_id: it.item_id, img_url: it.img_url || "",
                          bricklink_url: it.bricklink_url || "",
                          year: it.year || 0 };
      box.innerHTML = "";
      $("m-search-hint").hidden = true;
      if (/^fig-/.test(it.item_id) && it.img_url) {
        resolveBricklinkNo(it);        // automatisch sw-/dis-Nummer suchen
      } else {
        toast("Übernommen – unten Anzahl & Zustand prüfen und speichern");
        $("btn-manual-add").scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
  });
}

async function resolveBricklinkNo(it) {
  const hint = $("m-search-hint");
  hint.textContent = "Suche die passende BrickLink-Nummer (sw/dis/…) …";
  hint.hidden = false;
  try {
    const data = await api("/resolve", { method: "POST", body: { img_url: it.img_url } });
    let candidates = (data.items || [])
      .filter((c) => !c.item_type || c.item_type === $("m-type").value);
    if (!candidates.length) candidates = data.items || [];
    if (!candidates.length) {
      hint.textContent = "Keine BrickLink-Nummer gefunden – der Eintrag behält "
        + "die Rebrickable-Nummer. Speichern ist trotzdem möglich.";
      return;
    }
    hint.textContent = "BrickLink-Treffer – bitte die exakte Variante wählen "
      + "(Bild antippen für Großansicht):";
    renderSuggestions(candidates.map((c) => ({ ...c, sub: `${c.score} % sicher` })));
  } catch (e) {
    hint.textContent = e.message + " – der Eintrag behält die Rebrickable-Nummer.";
  }
}


async function addManual() {
  const err = $("manual-error");
  err.hidden = true;
  const name = $("m-name").value.trim();
  if (!name) {
    err.textContent = "Bitte mindestens einen Namen angeben.";
    err.hidden = false;
    return;
  }
  const type = $("m-type").value;
  let itemId = $("m-id").value.trim();
  let imgUrl = "";
  let blUrl = "";
  let year = 0;
  if (manualSelection && manualSelection.item_id === itemId) {
    imgUrl = manualSelection.img_url;
    blUrl = manualSelection.bricklink_url;
    year = manualSelection.year || 0;
  } else if (itemId) {
    blUrl = `https://www.bricklink.com/v2/catalog/catalogitem.page?${BL_URL_PREFIX[type]}=${encodeURIComponent(itemId)}`;
  }
  if (!itemId) itemId = "manuell-" + Date.now();
  const paidRaw = $("m-paid").value.trim().replace(",", ".");
  let paidPrice = null;
  if (paidRaw) {
    const n = Number(paidRaw);
    if (!Number.isFinite(n) || n < 0) {
      err.textContent = "Bezahlt bitte als Zahl, z. B. 4,50";
      err.hidden = false;
      return;
    }
    paidPrice = Math.round(n * 100) / 100;
  }
  try {
    const res = await api("/collection", { method: "POST", body: {
      item_id: itemId, item_type: type, name, img_url: imgUrl,
      bricklink_url: blUrl, year,
      quantity: Math.max(1, Number($("m-qty").value) || 1),
      condition: $("m-cond").value, notes: $("m-notes").value,
      paid_price: paidPrice,
    }});
    toast(res.merged
      ? `Schon vorhanden – Anzahl erhöht (jetzt ${res.quantity}×)`
      : "Zur Sammlung hinzugefügt ✔");
    $("m-name").value = ""; $("m-id").value = "";
    $("m-qty").value = "1"; $("m-notes").value = ""; $("m-paid").value = "";
    $("m-suggestions").innerHTML = "";
    manualSelection = null;
    $("manual-form").hidden = true;
    await askSetFigures({ item_id: itemId, item_type: type, name },
                        $("m-cond").value);
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
  }
}

/* ---------------------------------------------------------------- API-Schlüssel */
const KEY_FIELDS = {
  rebrickable_key: "k-rb",
  bl_consumer_key: "k-bck",
  bl_consumer_secret: "k-bcs",
  bl_token: "k-bt",
  bl_token_secret: "k-bts",
};

async function loadApiKeys() {
  try {
    const data = await api("/settings");
    for (const [name, id] of Object.entries(KEY_FIELDS)) {
      const input = $(id);
      input.value = "";
      const info = data[name] || {};
      input.placeholder = info.set
        ? `gespeichert: ${info.masked}${info.from_env ? " (aus docker-compose)" : ""}`
        : "nicht gesetzt";
    }
  } catch (e) { toast(e.message); }
}

async function saveApiKeys() {
  const body = {};
  for (const [name, id] of Object.entries(KEY_FIELDS)) {
    const value = $(id).value.trim();
    if (value) body[name] = value;
  }
  if (!Object.keys(body).length) {
    toast("Keine Änderungen eingegeben");
    return;
  }
  try {
    const res = await api("/settings", { method: "PUT", body });
    state.bricklinkPrices = res.flags.bricklink_prices;
    state.bricklinkLookup = res.flags.bricklink_lookup;
    state.catalogSearch = res.flags.catalog_search;
    toast(`Gespeichert (${res.changed} Schlüssel) ✔`);
    loadApiKeys();
  } catch (e) { toast(e.message); }
}

async function testApiKeys() {
  const out = $("keys-status");
  out.textContent = "Teste Verbindungen …";
  out.hidden = false;
  try {
    const r = await api("/settings/test", { method: "POST" });
    out.textContent =
      `BrickLink: ${r.bricklink.ok ? "✅" : "❌"} ${r.bricklink.info} — ` +
      `Rebrickable: ${r.rebrickable.ok ? "✅" : "❌"} ${r.rebrickable.info}`;
  } catch (e) {
    out.textContent = e.message;
  }
}

async function addManualWanted() {
  const err = $("manual-error");
  err.hidden = true;
  const name = $("m-name").value.trim();
  if (!name) {
    err.textContent = "Bitte mindestens einen Namen angeben.";
    err.hidden = false;
    return;
  }
  const type = $("m-type").value;
  let itemId = $("m-id").value.trim();
  let imgUrl = "";
  let blUrl = "";
  let year = 0;
  if (manualSelection && manualSelection.item_id === itemId) {
    imgUrl = manualSelection.img_url;
    blUrl = manualSelection.bricklink_url;
    year = manualSelection.year || 0;
  } else if (itemId) {
    blUrl = `https://www.bricklink.com/v2/catalog/catalogitem.page?${BL_URL_PREFIX[type]}=${encodeURIComponent(itemId)}`;
  }
  if (!itemId) itemId = "manuell-" + Date.now();
  try {
    const res = await api("/wanted", { method: "POST", body: {
      item_id: itemId, item_type: type, name, img_url: imgUrl,
      bricklink_url: blUrl, year, notes: $("m-notes").value,
    }});
    if (res.exists) toast("Steht schon auf der Wunschliste ⭐");
    else if (res.owned > 0) toast(`Gemerkt ⭐ (habt ihr schon ${res.owned}×)`);
    else toast("Auf die Wunschliste gesetzt ⭐");
    $("m-name").value = ""; $("m-id").value = "";
    $("m-qty").value = "1"; $("m-notes").value = ""; $("m-paid").value = "";
    $("m-suggestions").innerHTML = "";
    manualSelection = null;
    $("manual-form").hidden = true;
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
  }
}

async function changeOwnUsername() {
  const err = $("own-name-error");
  err.hidden = true;
  const name = $("own-name").value.trim();
  if (name.length < 2) {
    err.textContent = "Bitte mindestens 2 Zeichen.";
    err.hidden = false;
    return;
  }
  try {
    const res = await api("/me/username", { method: "POST",
      body: { username: name } });
    state.token = res.token;
    state.user = { username: res.username, is_admin: res.is_admin,
      is_dealer: state.user && state.user.is_dealer };
    localStorage.setItem("bf_token", res.token);
    localStorage.setItem("bf_user", JSON.stringify(state.user));
    $("whoami").textContent = res.username;
    $("settings-user").textContent = res.username;
    toast(`Name geändert: ${res.username} ✔`);
    loadSettings();
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
  }
}

/* ---------------------------------------------------------------- Einkaufslisten */
async function loadLists() {
  const dealer = state.user && state.user.is_dealer;
  $("lists-admin").hidden = !dealer;
  if (!dealer) $("duplicates-box").hidden = true;
  $("btn-toggle-archive").textContent = state.showArchive
    ? "↩︎ Aktive Listen anzeigen" : "📦 Archiv anzeigen";
  try {
    const data = await api("/lists" + (state.showArchive ? "?archived=1" : ""));
    renderLists(data.lists || []);
  } catch (e) { toast(e.message); }
}

function renderLists(lists) {
  const dealer = state.user && state.user.is_dealer;
  const box = $("lists-container");
  $("lists-empty").hidden = lists.length > 0;
  $("lists-empty").textContent = state.showArchive
    ? "Das Archiv ist leer." : "Keine Einkaufslisten vorhanden."
      + (dealer ? "" : "");
  box.innerHTML = lists.map((l) => `
    <div class="card list-card" data-lid="${l.id}">
      <div class="card-head">
        <div class="card-title">
          <strong>${state.showArchive ? "📦 " : "🛒 "}<span data-l-name>${esc(l.name)}</span>${dealer && !state.showArchive ? ` <button class="set-link rename-btn" data-l-rename title="Liste umbenennen">✏️</button>` : ""}</strong>
          <div class="sub">${l.stats.count} Artikel · ${l.stats.open} offen
            · Marktwert ca. ${fmtEur(l.stats.est)} (je Zustand)${l.stats.paid_sum > 0 ? ` · Einkauf ${fmtEur(l.stats.paid_sum)}` : ""}</div>
        </div>
      </div>
      <div class="set-figs">
        ${l.items.map((it) => listItemRow(it, dealer)).join("")}
        ${!l.items.length ? `<div class="price-note">Noch leer – beim Scannen oder Suchen auf 🛒 tippen.</div>` : ""}
      </div>
      ${dealer ? `<div class="card-actions btn-grid" style="margin-top:8px">
        ${!state.showArchive && l.stats.open > 0 ? `<button class="mini-btn add" data-l-offer>💰 Gesamtangebot</button>` : ""}
        ${state.showArchive
          ? `<button class="mini-btn" data-l-restore>↩︎ Reaktivieren</button>`
          : `<button class="mini-btn" data-l-archive>📦 Archivieren</button>`}
        <button class="mini-btn danger" data-l-del>Liste löschen</button>
      </div>` : ""}
    </div>`).join("");

  box.querySelectorAll(".list-card").forEach((card) => {
    const lid = Number(card.dataset.lid);
    const storeKey = "bf_listcard_" + lid;
    if (localStorage.getItem(storeKey) !== "open") {
      card.classList.add("collapsed");
    }
    card.querySelector(".card-head").addEventListener("click", (ev) => {
      if (ev.target.closest("[data-l-rename]")) return;
      card.classList.toggle("collapsed");
      localStorage.setItem(storeKey,
        card.classList.contains("collapsed") ? "closed" : "open");
    });
    const renameBtn = card.querySelector("[data-l-rename]");
    if (renameBtn) {
      renameBtn.addEventListener("click", () => {
        if (card.querySelector("[data-l-rename-row]")) return;
        const nameEl = card.querySelector("[data-l-name]");
        const current = nameEl.textContent;
        const row = document.createElement("div");
        row.className = "card-actions btn-grid";
        row.setAttribute("data-l-rename-row", "");
        row.innerHTML = `
          <input data-l-newname maxlength="120" style="grid-column:1/-1">
          <button class="mini-btn add" data-l-rename-save>Umbenennen</button>
          <button class="mini-btn" data-l-rename-cancel style="grid-column:auto">Abbrechen</button>`;
        nameEl.closest(".card-head").after(row);
        const input = row.querySelector("[data-l-newname]");
        input.value = current;
        input.focus();
        input.select();
        const closeRow = () => row.remove();
        row.querySelector("[data-l-rename-cancel]")
          .addEventListener("click", closeRow);
        const save = async () => {
          const name = input.value.trim();
          if (!name) { toast("Bitte einen Namen eingeben"); return; }
          if (name === current) { closeRow(); return; }
          try {
            await api(`/lists/${lid}/rename`, { method: "POST",
              body: { name } });
            toast(`Liste heißt jetzt »${name}« ✔`);
            loadLists();
          } catch (e) { toast(e.message); }
        };
        row.querySelector("[data-l-rename-save]")
          .addEventListener("click", save);
        input.addEventListener("keydown", (ev) => {
          if (ev.key === "Enter") save();
          if (ev.key === "Escape") { ev.stopPropagation(); closeRow(); }
        });
      });
    }
    const list = lists.find((l) => l.id === lid);
    const lOffer = card.querySelector("[data-l-offer]");
    if (lOffer) lOffer.addEventListener("click", () => {
      if (card.querySelector("[data-offer-row]")) return;
      const actions = lOffer.closest(".card-actions");
      actions.hidden = true;
      const openValue = list.items.filter((i) => !i.done)
        .reduce((s, i) => s + (((i.condition === "new"
          ? (i.price_new || i.price_used)
          : (i.price_used || i.price_new)) || 0) * i.qty), 0);
      const pct = (state.offerPercent || 60) / 100;
      const suggestion = Math.round(openValue * pct * 100) / 100;
      const row = document.createElement("div");
      row.className = "card-actions btn-grid";
      row.setAttribute("data-offer-row", "");
      row.innerHTML = `
        <span class="buy-label">Gesamtpreis für alle offenen Artikel –
          wird anteilig nach Marktwert verteilt.<br>
          Ø-Marktwert gesamt: ${fmtEur(openValue)}</span>
        <span class="paid-row buy-paid">
          <span class="paid-label">Gesamt</span>
          <input data-offer-total class="paid-input" inputmode="decimal" placeholder="0,00">
          <span class="paid-suffix">€</span>
          ${suggestion > 0 ? `<button class="set-link offer-suggest" data-offer-suggest>Vorschlag: ${fmtEur(suggestion)}</button>` : ""}
        </span>
        <button class="mini-btn add" data-offer-go>Verteilen</button>
        <button class="mini-btn" data-offer-cancel>Abbrechen</button>`;
      actions.after(row);
      row.querySelector("[data-offer-cancel]").addEventListener("click",
        () => { row.remove(); actions.hidden = false; });
      const sugBtn = row.querySelector("[data-offer-suggest]");
      if (sugBtn) sugBtn.addEventListener("click", () => {
        row.querySelector("[data-offer-total]").value = fmtPaidInput(suggestion);
      });
      row.querySelector("[data-offer-go]").addEventListener("click",
        async (ev) => {
          const raw = row.querySelector("[data-offer-total]").value.trim()
            .replace(",", ".");
          const total = Number(raw);
          if (raw === "" || !isFinite(total) || total < 0) {
            toast("Bitte einen gültigen Gesamtpreis eingeben");
            return;
          }
          ev.currentTarget.disabled = true;
          try {
            const res = await api(`/lists/${lid}/offer`, { method: "POST",
              body: { total } });
            toast(`${fmtEur(total)} anteilig auf ${res.count} Artikel verteilt ✔`);
            loadLists();
          } catch (e) {
            toast(e.message);
            ev.currentTarget.disabled = false;
          }
        });
    });

    const lArch = card.querySelector("[data-l-archive]");
    if (lArch) lArch.addEventListener("click", async () => {
      try {
        await api(`/lists/${lid}/archive`, { method: "POST",
          body: { archived: true } });
        toast("Liste archiviert 📦");
        loadLists();
        updateListsTab();
      } catch (e) { toast(e.message); }
    });
    const lRest = card.querySelector("[data-l-restore]");
    if (lRest) lRest.addEventListener("click", async () => {
      try {
        await api(`/lists/${lid}/archive`, { method: "POST",
          body: { archived: false } });
        toast("Liste reaktiviert ✔");
        loadLists();
        updateListsTab();
      } catch (e) { toast(e.message); }
    });
    const lDel = card.querySelector("[data-l-del]");
    if (lDel) lDel.addEventListener("click", async () => {
      if (!confirm(`Liste "${list.name}" mitsamt Artikeln löschen?`)) return;
      try {
        await api("/lists/" + lid, { method: "DELETE" });
        loadLists();
        updateListsTab();
      } catch (e) { toast(e.message); }
    });

    card.querySelectorAll("[data-ic]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (btn.classList.contains("sel")) return;
        try {
          await api(`/lists/items/${btn.dataset.icid}`, { method: "PATCH",
            body: { condition: btn.dataset.ic } });
          loadLists();
        } catch (e) { toast(e.message); }
      });
    });

    card.querySelectorAll("[data-ip-save]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const iid = btn.dataset.ipSave;
        const raw = card.querySelector(`[data-ip="${iid}"]`).value.trim()
          .replace(",", ".");
        const paid = Number(raw);
        if (raw === "" || !isFinite(paid) || paid < 0) {
          toast("Bitte einen gültigen Betrag eingeben");
          return;
        }
        btn.disabled = true;
        try {
          await api(`/lists/items/${iid}`, { method: "PATCH",
            body: { paid_price: paid } });
          toast("Einkaufspreis gespeichert ✔");
          loadLists();
        } catch (e) {
          toast(e.message);
          btn.disabled = false;
        }
      });
    });

    card.querySelectorAll("[data-i-recv]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const iid = Number(btn.dataset.iRecv);
        const listItem = list.items.find((x) => x.id === iid);
        const row = btn.closest(".fig-row");
        if (row.querySelector("[data-recv-row]")) return;
        const actions = row.querySelector(".fig-actions");
        const dealer2 = state.user && state.user.is_dealer;
        // Zustand steht am Listeneintrag schon fest – nicht erneut abfragen.
        const cond = listItem && listItem.condition === "new" ? "new" : "used";
        const condLabel = cond === "new" ? "Neu" : "Gebraucht";

        const send = async (mode, paid) => {
          const res = await api(`/lists/items/${iid}/receive`,
            { method: "POST", body: { condition: cond,
              paid_price: paid, mode } });
          if (res.need_mode) return res;
          toast(res.list_archived
            ? "In die Sammlung ✔ – Liste abgearbeitet, ab ins Archiv 🎉"
            : (mode === "replace" ? "Eintrag überschrieben ✔"
               : (res.merged
                  ? "Anzahl erhöht, Einkaufspreis gemittelt ✔"
                  : "In die Sammlung übernommen ✔")));
          if (listItem) {
            await askSetFigures(listItem, cond);
          }
          loadLists();
          updateListsTab();
          return res;
        };

        // Rückfrage, falls der Artikel in diesem Zustand schon vorhanden ist
        const askMode = (owned, paid) => {
          actions.hidden = true;
          const mc = document.createElement("div");
          mc.className = "fig-actions";
          mc.setAttribute("data-recv-row", "");
          mc.style.flexWrap = "wrap";
          mc.innerHTML = `
            <span class="buy-label">Schon ${owned}× in der Sammlung:</span>
            <button class="mini-btn add" data-rm="add">＋ Zusätzlich</button>
            <button class="mini-btn" data-rm="replace">Überschreiben</button>
            <button class="mini-btn" data-rm-cancel>✕</button>`;
          actions.after(mc);
          mc.querySelector("[data-rm-cancel]").addEventListener(
            "click", () => { mc.remove(); actions.hidden = false; });
          mc.querySelectorAll("[data-rm]").forEach((mb) => {
            mb.addEventListener("click", async () => {
              mb.disabled = true;
              try {
                await send(mb.dataset.rm, paid);
              } catch (e2) {
                toast(e2.message);
                mb.disabled = false;
              }
            });
          });
        };

        const doReceive = async (paid) => {
          btn.disabled = true;
          try {
            const res = await send(null, paid);
            if (res.need_mode) askMode(res.owned, paid);
          } catch (e) {
            toast(e.message);
            btn.disabled = false;
            actions.hidden = false;
          }
        };

        if (dealer2) {
          // Profi: Einkaufspreis bestätigen (Zustand ist bereits gewählt)
          actions.hidden = true;
          const chooser = document.createElement("div");
          chooser.className = "fig-actions";
          chooser.setAttribute("data-recv-row", "");
          chooser.style.flexWrap = "wrap";
          chooser.innerHTML = `
            <span class="paid-row buy-paid" style="flex-basis:100%">
              <span class="paid-label">Preis</span>
              <input data-recv-paid class="paid-input" inputmode="decimal" placeholder="0,00" value="${listItem && listItem.paid_price != null ? fmtPaidInput(listItem.paid_price) : ""}">
              <span class="paid-suffix">€</span>
              <span class="sub">leer = BrickLink-Ø</span></span>
            <button class="mini-btn add" data-rc-go>✔ ${condLabel} übernehmen</button>
            <button class="mini-btn" data-rc-cancel>✕</button>`;
          actions.after(chooser);
          chooser.querySelector("[data-rc-cancel]").addEventListener("click",
            () => { chooser.remove(); actions.hidden = false; });
          chooser.querySelector("[data-rc-go]").addEventListener("click",
            async () => {
              const paidEl = chooser.querySelector("[data-recv-paid]");
              let paid = null;
              if (paidEl && paidEl.value.trim() !== "") {
                paid = Number(paidEl.value.trim().replace(",", "."));
                if (!isFinite(paid) || paid < 0) {
                  toast("Bitte einen gültigen Preis eingeben");
                  return;
                }
              }
              chooser.remove();
              await doReceive(paid);
            });
        } else {
          // Kein Profi: direkt mit dem angegebenen Zustand verbuchen
          doReceive(null);
        }
      });
    });
    card.querySelectorAll("[data-i-undo]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          await api(`/lists/items/${btn.dataset.iUndo}/undo`,
            { method: "POST" });
          toast("Rückgängig – Sammlung ggf. manuell anpassen");
          state.showArchive = false;
          loadLists();
        } catch (e) { toast(e.message); }
      });
    });
    card.querySelectorAll("[data-i-del]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          await api("/lists/items/" + btn.dataset.iDel,
            { method: "DELETE" });
          loadLists();
        } catch (e) { toast(e.message); }
      });
    });
  });
}

function listItemRow(it, dealer) {
  const condPrice = it.condition === "new"
    ? (it.price_new || it.price_used) : (it.price_used || it.price_new);
  const prices = condPrice
    ? `Ø ${it.condition === "new" ? "neu" : "gebr."} ${fmtEur(condPrice)}` : "";
  const doneInfo = it.done
    ? `<div class="sub done-note">✔ in Sammlung${it.done_by_name ? " von " + esc(it.done_by_name) : ""}${it.done_at ? " am " + new Date(it.done_at * 1000).toLocaleDateString("de-DE") : ""}</div>`
    : "";
  return `
  <div class="fig-row ${it.done ? "done" : ""}" data-iid="${it.id}">
    <img class="card-img fig-img" src="${imgSrc(it.img_url)}" data-gid="${esc(it.item_id)}" data-gtype="${esc(it.item_type)}" alt="" loading="lazy">
    <div class="fig-info">
      <strong>${esc(it.name)}</strong>
      <div class="sub">${esc(it.item_id)}${it.qty > 1 ? ` · ${it.qty}×` : ""} · ${it.condition === "new" ? "Neu" : "Gebraucht"}${prices ? " · " + prices : ""}${it.paid_price != null ? ` · Einkauf ${fmtEur(it.paid_price)}` : ""}</div>
      ${doneInfo}
      ${!it.done && dealer ? `
      <div class="fig-actions" style="margin-top:6px">
        <button class="mini-btn cond-mini ${it.condition !== "new" ? "sel" : ""}" data-ic="used" data-icid="${it.id}">Gebraucht</button>
        <button class="mini-btn cond-mini ${it.condition === "new" ? "sel" : ""}" data-ic="new" data-icid="${it.id}">Neu</button>
      </div>
      <div class="paid-row" style="margin-top:6px">
        <span class="paid-label">Einkauf</span>
        <input data-ip="${it.id}" class="paid-input" inputmode="decimal" placeholder="0,00" value="${it.paid_price != null ? fmtPaidInput(it.paid_price) : ""}">
        <span class="paid-suffix">€</span>
        <button class="mini-btn add" data-ip-save="${it.id}" style="flex:1;min-height:38px">✓</button>
      </div>` : ""}
      <div class="fig-actions">
        ${!it.done ? `<button class="mini-btn add" data-i-recv="${it.id}">✔ Da! Ab in die Sammlung</button>` : ""}
        ${!it.done && dealer ? `<button class="mini-btn danger" data-i-del="${it.id}">✕</button>` : ""}
        ${it.done && dealer ? `<button class="mini-btn" data-i-undo="${it.id}">↩︎ Rückgängig</button>` : ""}
      </div>
    </div>
  </div>`;
}

async function addToList(list, it, condition, paidPrice) {
  const cond = condition === "new" ? "new" : "used";
  try {
    const body = { item_id: it.item_id, item_type: it.item_type || "minifig",
      name: it.name, img_url: it.img_url || "",
      bricklink_url: it.bricklink_url || "", year: it.year || 0,
      condition: cond };
    if (paidPrice != null) body.paid_price = paidPrice;
    const res = await api(`/lists/${list.id}/items`, { method: "POST",
      body });
    const suffix = cond === "new" ? " (Neu)" : "";
    toast(res.merged ? `Menge erhöht in "${list.name}" 🛒${suffix}`
                     : `Auf "${list.name}" gesetzt 🛒${suffix}`);
  } catch (e) { toast(e.message); }
}

function wireCartButtons(box, items) {
  box.querySelectorAll("[data-cart]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      let lists;
      try {
        lists = (await api("/lists")).lists || [];
      } catch (e) { toast(e.message); return; }
      const it = items[Number(btn.dataset.cart)];
      const card = btn.closest(".card");
      if (card.querySelector("[data-cart-row]")) return;
      const actions = card.querySelector(".card-actions");
      actions.hidden = true;
      const row = document.createElement("div");
      row.className = "card-actions btn-grid";
      row.setAttribute("data-cart-row", "");
      actions.after(row);

      const close = () => { row.remove(); actions.hidden = false; };
      let cond = "used";
      let priceVal = "";
      const priceField = () => `
        <input data-cl-price inputmode="decimal" value="${esc(priceVal)}"
          placeholder="Einkauf € (optional)" style="grid-column:1/-1">`;
      const wirePriceField = () => {
        const inp = row.querySelector("[data-cl-price]");
        if (inp) inp.addEventListener("input", () => {
          priceVal = inp.value;
        });
      };
      const readPrice = () => {
        const raw = priceVal.trim().replace(",", ".");
        if (!raw) return null;
        const n = Number(raw);
        if (!Number.isFinite(n) || n < 0) return undefined;
        return Math.round(n * 100) / 100;
      };
      const condChips = () => `
        <button class="mini-btn cond-mini ${cond !== "new" ? "sel" : ""}" data-cc="used">Gebraucht</button>
        <button class="mini-btn cond-mini ${cond === "new" ? "sel" : ""}" data-cc="new">Neu</button>`;
      const wireCondChips = (rerender) => {
        row.querySelectorAll("[data-cc]").forEach((c) => {
          c.addEventListener("click", () => {
            if (c.dataset.cc === cond) return;
            cond = c.dataset.cc;
            rerender();
          });
        });
      };

      const renderNew = () => {
        const today = new Date().toLocaleDateString("de-DE",
          { day: "2-digit", month: "2-digit" });
        row.innerHTML = `
          ${condChips()}${priceField()}
          <span class="buy-label">Neue Einkaufsliste anlegen:</span>
          <input data-cl-name maxlength="120" style="grid-column:1/-1"
            value="Flohmarkt ${today}">
          <button class="mini-btn add" data-cl-create>Anlegen &amp; drauflegen</button>
          <button class="mini-btn" data-cl-back>${lists.length ? "Zurück" : "Abbrechen"}</button>`;
        const input = row.querySelector("[data-cl-name]");
        input.focus();
        input.select();
        row.querySelector("[data-cl-back]").addEventListener("click",
          () => { lists.length ? renderChooser() : close(); });
        const create = async () => {
          const name = input.value.trim();
          if (!name) { toast("Bitte einen Namen eingeben"); return; }
          const price = readPrice();
          if (price === undefined) {
            toast("Preis bitte als Zahl, z. B. 4,50");
            return;
          }
          const createBtn = row.querySelector("[data-cl-create]");
          createBtn.disabled = true;
          try {
            const res = await api("/lists", { method: "POST",
              body: { name } });
            await addToList({ id: res.id, name }, it, cond, price);
            updateListsTab();
            close();
          } catch (e) {
            toast(e.message);
            createBtn.disabled = false;
          }
        };
        row.querySelector("[data-cl-create]").addEventListener("click",
          create);
        input.addEventListener("keydown", (ev) => {
          if (ev.key === "Enter") create();
        });
        wireCondChips(renderNew);
        wirePriceField();
      };

      const renderChooser = () => {
        row.innerHTML = condChips() + priceField()
          + `<span class="buy-label">Auf welche Liste?</span>`
          + lists.map((l) => `<button class="mini-btn" data-cl="${l.id}">${esc(l.name)}</button>`).join("")
          + `<button class="mini-btn add" data-cl-new>＋ Neue Liste</button>`
          + `<button class="mini-btn" data-cl-cancel>Abbrechen</button>`;
        row.querySelector("[data-cl-cancel]").addEventListener("click",
          close);
        row.querySelector("[data-cl-new]").addEventListener("click",
          renderNew);
        row.querySelectorAll("[data-cl]").forEach((b) => {
          b.addEventListener("click", async () => {
            const price = readPrice();
            if (price === undefined) {
              toast("Preis bitte als Zahl, z. B. 4,50");
              return;
            }
            const l = lists.find((x) => x.id === Number(b.dataset.cl));
            await addToList(l, it, cond, price);
            close();
          });
        });
        wireCondChips(renderChooser);
        wirePriceField();
      };

      if (lists.length) renderChooser(); else renderNew();
    });
  });
}

/* ---------------------------------------------------------------- Statistik */
const TYPE_LABELS = { minifig: "Figuren", set: "Sets", part: "Teile" };

async function loadStats() {
  const box = $("stats-view");
  box.innerHTML = `<p class="empty">Lade Statistik …</p>`;
  try {
    const data = await api("/stats/dashboard");
    renderStats(data);
  } catch (e) {
    box.innerHTML = `<p class="empty">${esc(e.message)}</p>`;
  }
}

function renderStats(data) {
  const t = data.totals;
  const dealer = state.user && state.user.is_dealer;
  const profitCls = t.profit >= 0 ? "profit-pos" : "profit-neg";

  const chips = `
  <div class="card">
    <div class="stats-row">
      <div class="stat-chip"><strong>${t.pieces}</strong><span>Stück</span></div>
      <div class="stat-chip"><strong>${t.unique}</strong><span>verschieden</span></div>
      <div class="stat-chip"><strong>${fmtEur(t.avg_piece)}</strong><span>Ø je Stück</span></div>
    </div>
    <div class="stats-row">
      <div class="stat-chip"><strong>${fmtEur(t.value)}</strong><span>Gesamtwert</span></div>
      ${dealer ? `
      <div class="stat-chip"><strong>${fmtEur(t.paid)}</strong><span>bezahlt</span></div>
      <div class="stat-chip"><strong class="${profitCls}">${t.profit >= 0 ? "+" : "−"}${fmtEur(Math.abs(t.profit))}</strong><span>Gewinn</span></div>` : ""}
    </div>
    ${t.paid_estimated > 0 ? `<div class="price-note" style="margin-top:6px">
      Bei Figuren, die in euren Sets stecken, zählt ein nur ⚙️ automatisch
      ermittelter Kaufpreis nicht extra – der Set-Preis deckt sie ab
      (${fmtEur(t.paid_estimated)}). ✏️ Selbst eingetragene Preise zählen
      immer mit, auch bei Set-Figuren.</div>` : ""}
    ${t.in_sets_value > 0 ? `<div class="price-note" style="margin-top:6px">
      Figuren, die in euren Sets stecken, sind im Set-Preis enthalten und
      werden nicht doppelt gezählt (${fmtEur(t.in_sets_value)}).
      Details unter ❓ Hilfe → „Wie der Wert berechnet wird".</div>` : ""}
  </div>`;

  const chart = `
  <div class="card">
    <h3 style="margin:0 0 4px">Wertentwicklung</h3>
    ${data.timeline.length >= 2 ? totalChart(data.timeline)
      : `<div class="price-note">Der Wertverlauf wächst mit jedem
         Preis-Update – schau in ein paar Tagen wieder rein.</div>`}
  </div>`;

  const typeRows = Object.entries(data.by_type)
    .sort((a, b) => b[1].value - a[1].value)
    .map(([k, v]) => statBarRow(TYPE_LABELS[k] || k, v, t.value)).join("");
  const condRows = Object.entries(data.by_condition)
    .sort((a, b) => b[1].value - a[1].value)
    .map(([k, v]) => statBarRow(k === "new" ? "Neu" : "Gebraucht", v,
      t.value)).join("");
  const split = `
  <div class="card">
    <h3 style="margin:0 0 8px">Aufteilung</h3>
    ${typeRows}
    <div style="height:8px"></div>
    ${condRows}
  </div>`;

  const years = data.by_year.length >= 2 ? `
  <div class="card">
    <h3 style="margin:0 0 4px">Wert nach Erscheinungsjahr</h3>
    ${yearChart(data.by_year)}
  </div>` : "";

  const top = data.top.length ? `
  <div class="card">
    <h3 style="margin:0 0 6px">Top ${data.top.length} nach Wert</h3>
    <div class="set-figs">
      ${data.top.map((it, i) => `
      <div class="fig-row">
        <img class="card-img fig-img" src="${imgSrc(it.img_url)}" data-gid="${esc(it.item_id)}" data-gtype="${esc(it.item_type)}" alt="" loading="lazy">
        <div class="fig-info" style="display:flex;align-items:center;justify-content:space-between;gap:8px">
          <strong style="font-size:14px">${i + 1}. ${esc(it.name)}${it.quantity > 1 ? ` (${it.quantity}×)` : ""}</strong>
          <b style="white-space:nowrap">${fmtEur(it.value)}</b>
        </div>
      </div>`).join("")}
    </div>
  </div>` : "";

  const winners = dealer && data.winners.length ? `
  <div class="card">
    <h3 style="margin:0 0 6px">Beste Wertsteigerungen</h3>
    ${data.winners.map((it, i) => `
      <div class="sub" style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px dashed var(--line)">
        <span>${i + 1}. ${esc(it.name)}</span>
        <b class="${it.gain >= 0 ? "profit-pos" : "profit-neg"}">${it.gain >= 0 ? "+" : "−"}${fmtEur(Math.abs(it.gain))}</b>
      </div>`).join("")}
    <div class="price-note" style="margin-top:6px">Aktueller Wert minus Kaufpreis</div>
  </div>` : "";

  $("stats-view").innerHTML = chips + chart + split + years + top + winners;
  wireYearChart();
}

function wireYearChart() {
  const detail = $("year-detail");
  const bars = document.querySelectorAll(".year-bar");
  if (!detail || !bars.length) return;
  const show = (bar) => {
    document.querySelectorAll(".year-bar").forEach((b) =>
      b.setAttribute("fill", "#0057A6"));
    bar.setAttribute("fill", "#E3000F");
    detail.innerHTML = `<b>${bar.dataset.year}</b>: `
      + `${bar.dataset.value} · ${bar.dataset.pieces} Stück`;
  };
  bars.forEach((bar) => {
    bar.addEventListener("click", () => show(bar));
  });
}

function statBarRow(label, v, total) {
  const pct = total > 0 ? Math.round((v.value / total) * 100) : 0;
  return `
  <div class="stat-bar-row">
    <div class="sub" style="display:flex;justify-content:space-between">
      <span>${label} · ${v.pieces} Stück</span>
      <b>${fmtEur(v.value)} (${pct} %)</b>
    </div>
    <div class="stat-bar"><div class="stat-bar-fill" style="width:${pct}%"></div></div>
  </div>`;
}

function totalChart(pts) {
  const w = 560, h = 150, padX = 8, padT = 12, padB = 22;
  const values = pts.map((p) => p.value);
  let lo = Math.min(...values), hi = Math.max(...values);
  if (hi - lo < 0.01) { lo -= 1; hi += 1; }
  const t0 = pts[0].ts, t1 = pts[pts.length - 1].ts || t0 + 1;
  const x = (ts) => padX + ((ts - t0) / Math.max(1, t1 - t0)) * (w - 2 * padX);
  const y = (v) => padT + (1 - (v - lo) / (hi - lo)) * (h - padT - padB);
  const line = pts.map((p) => `${x(p.ts).toFixed(1)},${y(p.value).toFixed(1)}`)
    .join(" ");
  const dFmt = (ts) => new Date(ts * 1000).toLocaleDateString("de-DE",
    { day: "2-digit", month: "2-digit", year: "2-digit" });
  return `
  <svg viewBox="0 0 ${w} ${h}" class="history-svg" role="img" aria-label="Wertentwicklung">
    <line x1="${padX}" y1="${h - padB}" x2="${w - padX}" y2="${h - padB}" stroke="#D4D7DC" stroke-width="1.5"/>
    <polyline points="${line}" fill="none" stroke="#0057A6" stroke-width="2.5"/>
    ${pts.map((p) => `<circle cx="${x(p.ts).toFixed(1)}" cy="${y(p.value).toFixed(1)}" r="3" fill="#0057A6"/>`).join("")}
    <text x="${padX}" y="${h - 6}" class="hist-label">${dFmt(t0)}</text>
    <text x="${w - padX}" y="${h - 6}" text-anchor="end" class="hist-label">${dFmt(t1)}</text>
    <text x="${padX}" y="${padT + 2}" class="hist-label">${fmtEur(hi)}</text>
    <text x="${padX}" y="${h - padB - 4}" class="hist-label">${fmtEur(lo)}</text>
  </svg>
  <div class="price-note">Wertentwicklung eurer heutigen Sammlung
    (eigene Preisaufzeichnung)</div>`;
}

function yearChart(list) {
  const w = 560, h = 150, padB = 22, padT = 16;
  const maxV = Math.max(...list.map((e) => e.value)) || 1;
  const gap = 3;
  const bw = Math.max(4, Math.floor((w - 16) / list.length) - gap);
  const bars = list.map((e, i) => {
    const bh = Math.max(2, (e.value / maxV) * (h - padT - padB));
    const bx = 8 + i * (bw + gap);
    const by = h - padB - bh;
    return `<rect class="year-bar" x="${bx}" y="${by.toFixed(1)}" `
      + `width="${bw}" height="${bh.toFixed(1)}" rx="2" fill="#0057A6" `
      + `style="cursor:pointer" data-year="${e.year}" `
      + `data-value="${fmtEur(e.value)}" data-pieces="${e.pieces}">`
      + `<title>${e.year}: ${fmtEur(e.value)} (${e.pieces} Stück)</title></rect>`;
  }).join("");
  const first = list[0], last = list[list.length - 1];
  const peak = list.reduce((a, b) => (b.value > a.value ? b : a), list[0]);
  const px = 8 + list.indexOf(peak) * (bw + gap) + bw / 2;
  return `
  <svg viewBox="0 0 ${w} ${h}" class="history-svg" role="img" aria-label="Wert nach Jahr">
    ${bars}
    <text x="8" y="${h - 6}" class="hist-label">${first.year}</text>
    <text x="${w - 8}" y="${h - 6}" text-anchor="end" class="hist-label">${last.year}</text>
    <text x="${Math.min(Math.max(px, 30), w - 30)}" y="${padT - 4}" text-anchor="middle" class="hist-label">${peak.year}: ${fmtEur(peak.value)}</text>
  </svg>
  <div class="year-detail" id="year-detail">Balken antippen für Details je Jahr</div>`;
}

/* ---------------------------------------------------------------- CSV-Import */
function downloadCsvSample() {
  downloadCsv("brickfolio-import-beispiel.csv", [
    ["Nummer", "Typ", "Name", "Anzahl", "Zustand", "Bezahlt", "Jahr",
     "Notizen"],
    ["sw0815", "Figur", "Shoretrooper", "2", "Gebraucht", "24,50", "2016",
     "Flohmarkt Ottobrunn"],
    ["75154", "Set", "TIE Striker", "1", "Neu", "89,99", "2016", ""],
    ["col424", "Figur", "", "1", "Gebraucht", "", "", "leerer Name: Nummer wird als Name verwendet"],
    ["manuell-01", "Figur", "Eigenbau-Ritter", "1", "Gebraucht", "3,00", "",
     "eigene Nummern bekommen keine BrickLink-Preise"],
  ]);
  toast("Beispiel-CSV heruntergeladen 💾");
}

async function importCsvFile(file) {
  let text;
  try {
    text = await file.text();
  } catch (_) {
    toast("Datei konnte nicht gelesen werden");
    return;
  }
  try {
    const res = await api("/import/csv", { method: "POST",
      body: { csv: text } });
    let msg = `Import fertig: ${res.created} neu, ${res.merged} zusammengeführt`;
    if (res.error_count) msg += `, ${res.error_count} Fehler`;
    toast(msg + " ✔");
    if (res.errors && res.errors.length) {
      alert("Nicht importierte Zeilen:\n" + res.errors
        .map((e) => `Zeile ${e.line}: ${e.error}`).join("\n")
        + (res.error_count > res.errors.length ? "\n…" : ""));
    }
  } catch (e) { toast(e.message); }
}

/* ---------------------------------------------------------------- Verkaufsliste */
async function toggleDuplicates() {
  const box = $("duplicates-box");
  if (!box.hidden) {
    box.hidden = true;
    $("btn-duplicates").textContent = "📋 Verkaufsliste (Doppelte)";
    return;
  }
  try {
    const data = await api("/duplicates");
    state.duplicates = data;
    renderDuplicates(data);
    box.hidden = false;
    $("btn-duplicates").textContent = "📋 Verkaufsliste ausblenden";
  } catch (e) { toast(e.message); }
}

function renderDuplicates(data) {
  const box = $("duplicates-box");
  if (!data.items.length) {
    box.innerHTML = `<div class="card"><div class="price-note">
      Keine Doppelten – alles Einzelstücke.</div></div>`;
    return;
  }
  box.innerHTML = `
  <div class="card">
    <div class="card-head"><div class="card-title">
      <strong>📋 Verkaufsliste – Doppelte</strong>
      <div class="sub">${data.stats.pieces} Stück abgebbar
        · Verkaufswert ca. ${fmtEur(data.stats.value)}
        <span class="search-hint">(1 Exemplar bleibt immer · für eigene Sets gebrauchte Figuren zusätzlich reserviert)</span></div>
    </div></div>
    <div class="set-figs">
      ${data.items.map((it) => `
      <div class="fig-row">
        <img class="card-img fig-img" src="${imgSrc(it.img_url)}" data-gid="${esc(it.item_id)}" data-gtype="${esc(it.item_type)}" alt="" loading="lazy">
        <div class="fig-info">
          <strong>${esc(it.name)}</strong>
          <div class="sub">${esc(it.item_id)} · ${it.condition === "new" ? "Neu" : "Gebraucht"}
            · ${it.quantity}× vorhanden${
              it.set_reserved > 0
                ? ` (${it.set_reserved}× für Sets reserviert)`
                : (it.reserved > 0 ? ` (1 behalten)` : "")
            } → <b>${it.surplus}× abgebbar</b>
            ${it.unit_price ? ` · Ø ${fmtEur(it.unit_price)}${it.surplus > 1 ? " → " + fmtEur(it.value) : ""}` : ""}</div>
        </div>
      </div>`).join("")}
    </div>
    <div class="card-actions btn-grid" style="margin-top:8px">
      <button class="mini-btn" id="btn-dup-csv">Als CSV</button>
      <button class="mini-btn" id="btn-dup-print">Drucken</button>
    </div>
  </div>`;
  $("btn-dup-csv").addEventListener("click", exportDuplicatesCsv);
  $("btn-dup-print").addEventListener("click", printDuplicates);
}

function exportDuplicatesCsv() {
  const data = state.duplicates;
  const rows = [["Nummer", "Name", "Zustand", "Vorhanden", "Abgebbar",
    "Ø Stück (EUR)", "Wert (EUR)"]];
  data.items.forEach((it) => rows.push([it.item_id, it.name,
    it.condition === "new" ? "Neu" : "Gebraucht", it.quantity, it.surplus,
    numDe(it.unit_price), numDe(it.value)]));
  downloadCsv("brickfolio-verkaufsliste.csv", rows);
  toast("Verkaufsliste exportiert ✔");
}

function printDuplicates() {
  const data = state.duplicates;
  const rows = data.items.map((it) => [it.item_id, it.name,
    it.condition === "new" ? "Neu" : "Gebraucht",
    it.surplus, it.unit_price ? fmtEur(it.unit_price) : "",
    it.value ? fmtEur(it.value) : ""]);
  printTable("Verkaufsliste – Doppelte",
    `${data.stats.pieces} Stück abgebbar · Verkaufswert ca. ${fmtEur(data.stats.value)}`,
    ["Nummer", "Name", "Zustand", "Abgebbar", "Ø Stück", "Wert"], rows,
    ["num", "name", "cond", "qty", "price", "price"]);
}

/* ---------------------------------------------------------------- Passwörter */
async function changeOwnPassword() {
  const err = $("own-pass-error");
  err.hidden = true;
  try {
    await api("/me/password", { method: "POST", body: {
      current_password: $("own-pass-current").value,
      new_password: $("own-pass-new").value,
    }});
    $("own-pass-current").value = "";
    $("own-pass-new").value = "";
    toast("Passwort geändert ✔");
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
  }
}

/* ---------------------------------------------------------------- Export & Druck */
function csvCell(v) {
  v = String(v ?? "");
  return /[";\n\r]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
}

function numDe(v) {
  return v == null ? "" : String(v).replace(".", ",");
}

function downloadCsv(filename, rows) {
  const csv = "\ufeff" + rows.map((r) => r.map(csvCell).join(";")).join("\r\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}

const _dateDe = (ts) => new Date(ts * 1000).toLocaleDateString("de-DE");

async function exportCollectionCsv() {
  const data = await api("/collection?q=&sort=name");
  const rows = [["Nummer", "Name", "Typ", "Jahr", "Anzahl", "Zustand",
    "Ø Neu (EUR)", "Ø Gebraucht (EUR)", "Wert (EUR)", "Notizen",
    "Erfasst von", "Erfasst am"]];
  data.items.forEach((it) => {
    const unit = unitValue(it);
    rows.push([it.item_id, it.name, it.item_type, it.year > 0 ? it.year : "",
      it.quantity, it.condition === "new" ? "Neu" : "Gebraucht",
      numDe(it.price_new), numDe(it.price_used),
      unit ? numDe((unit * it.quantity).toFixed(2)) : "",
      it.notes, it.added_by_name || "", _dateDe(it.added_at)]);
  });
  downloadCsv("brickfolio-sammlung.csv", rows);
  toast("Sammlung exportiert ✔");
}

async function exportWantedCsv() {
  const data = await api("/wanted");
  const rows = [["Nummer", "Name", "Typ", "Jahr", "Ø Neu (EUR)",
    "Ø Gebraucht (EUR)", "Notizen", "Erfasst von", "Erfasst am"]];
  data.items.forEach((it) => {
    rows.push([it.item_id, it.name, it.item_type, it.year > 0 ? it.year : "",
      numDe(it.price_new), numDe(it.price_used), it.notes,
      it.added_by_name || "", _dateDe(it.added_at)]);
  });
  downloadCsv("brickfolio-wunschliste.csv", rows);
  toast("Wunschliste exportiert ✔");
}

function printTable(title, subtitle, headers, rows, cols) {
  cols = cols || headers.map(() => "");
  const cls = (i) => (cols[i] ? ` class="pc-${cols[i]}"` : "");
  const area = $("print-area");
  area.innerHTML = `<h1>${esc(title)}</h1>`
    + `<p>${esc(subtitle)} · Stand ${new Date().toLocaleDateString("de-DE")} · Finn's Brickfolio</p>`
    + `<table><colgroup>${cols.map((c) => `<col${c ? ` class="pc-${c}"` : ""}>`).join("")}</colgroup>`
    + `<thead><tr>${headers.map((h, i) => `<th${cls(i)}>${esc(h)}</th>`).join("")}</tr></thead>`
    + `<tbody>${rows.map((r) =>
        `<tr>${r.map((c, i) => `<td${cls(i)}>${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
  window.print();
}

async function printCollection() {
  const data = await api("/collection?q=&sort=name");
  const rows = data.items.map((it) => [it.item_id, it.name,
    it.year > 0 ? it.year : "", it.quantity,
    it.condition === "new" ? "Neu" : "Gebraucht",
    unitValue(it) ? fmtEur(unitValue(it)) : ""]);
  const sub = `${data.stats.total} Stück (${data.stats.unique_items} verschiedene)`
    + (data.stats.total_value ? ` · Gesamtwert ca. ${fmtEur(data.stats.total_value)}` : "");
  printTable("Deine LEGO-Sammlung", sub,
    ["Nummer", "Name", "Jahr", "Anz.", "Zustand", "Ø Preis"], rows,
    ["num", "name", "year", "qty", "cond", "price"]);
}

async function printWanted() {
  const data = await api("/wanted");
  const rows = data.items.map((it) => [it.item_id, it.name,
    it.year > 0 ? it.year : "",
    it.price_used ? fmtEur(it.price_used) : "",
    it.price_new ? fmtEur(it.price_new) : ""]);
  const sub = `${data.stats.count} Wünsche`
    + (data.stats.est_cost ? ` · geschätzt ${fmtEur(data.stats.est_cost)} (gebraucht)` : "");
  printTable("Deine Wunschliste", sub,
    ["Nummer", "Name", "Jahr", "Ø gebr.", "Ø neu"], rows,
    ["num", "name", "year", "price", "price"]);
}

async function downloadBackup() {
  try {
    const data = await api("/backup");
    const blob = new Blob([JSON.stringify(data)],
      { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `brickfolio-sicherung-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
    toast("Sicherung heruntergeladen 💾");
  } catch (e) { toast(e.message); }
}

async function restoreBackupFile(file) {
  let data;
  try {
    data = JSON.parse(await file.text());
  } catch (_) {
    toast("Datei ist kein gültiges JSON");
    return;
  }
  const when = data.created_at
    ? new Date(data.created_at * 1000).toLocaleString("de-DE") : "unbekannt";
  if (!confirm(`Sicherung vom ${when} einspielen?\n\nACHTUNG: ALLE aktuellen Daten werden ersetzt!`)) return;
  try {
    const res = await api("/restore", { method: "POST", body: data });
    const n = res.restored && res.restored.collection;
    toast(`Sicherung eingespielt ✔ (${n ?? "?"} Sammlungseinträge)`);
    setTimeout(() => location.reload(), 1200);
  } catch (e) { toast(e.message); }
}

/* ---------------------------------------------------------------- Einstellungen */
function initCollapsibleCards() {
  document.querySelectorAll("#view-settings .settings-card > h3")
    .forEach((h3) => {
      const card = h3.parentElement;
      const key = "bf_card_" + h3.textContent.replace(/\W+/g, "");
      const stored = localStorage.getItem(key);
      if (stored === "open") card.classList.remove("collapsed");
      else card.classList.add("collapsed");
      h3.addEventListener("click", () => {
        card.classList.toggle("collapsed");
        localStorage.setItem(key,
          card.classList.contains("collapsed") ? "closed" : "open");
      });
    });
}

async function loadPriceLog(limit) {
  const box = $("pricelog-list");
  if (!box) return;
  box.textContent = "Lade …";
  try {
    const res = await api(`/price_log?limit=${limit}`);
    const staleEl = $("pricelog-stale");
    if (staleEl) {
      const days = res.stale_days || 7;
      const n = res.stale_count || 0;
      staleEl.textContent = n > 0
        ? `🕒 Bei ${n} ${n === 1 ? "Artikel ist" : "Artikeln ist"} in der `
          + `Sammlung der Preisabruf älter als ${days} Tage `
          + `– der Hintergrundjob frischt sie nach und nach auf.`
        : `✔ Alle Sammlungs-Preise sind jünger als ${days} Tage.`;
      staleEl.hidden = false;
    }
    if (!res.entries.length) {
      box.textContent = "Noch keine Aufzeichnungen.";
      $("btn-pricelog-more").hidden = true;
      return;
    }
    box.innerHTML = res.entries.map((e) => {
      const d = new Date(e.ts * 1000);
      const when = d.toLocaleDateString("de-DE",
        { day: "2-digit", month: "2-digit" }) + " "
        + d.toLocaleTimeString("de-DE",
          { hour: "2-digit", minute: "2-digit" });
      const prices = [
        e.price_new != null ? "neu " + fmtEur(e.price_new) : null,
        e.price_used != null ? "gebr. " + fmtEur(e.price_used) : null,
      ].filter(Boolean).join(" · ");
      const src = e.source === "manuell"
        ? `<span class="pl-src manual">manuell</span>`
        : e.source === "auto"
          ? `<span class="pl-src">auto</span>` : "";
      return `<div class="pl-row">
        <span class="pl-when">${when}</span>
        <span class="pl-name">${esc(e.name)}</span>
        <span class="pl-prices">${prices || "–"}</span>${src}
      </div>`;
    }).join("");
    $("btn-pricelog-more").hidden = limit >= 200
      || res.entries.length < limit;
  } catch (e) {
    box.textContent = e.message;
  }
}

async function checkForUpdate(force) {
  if (!(state.user && state.user.is_admin)) return null;
  try {
    return await api("/update_check" + (force ? "?force=1" : ""));
  } catch (_) {
    return null;
  }
}

function renderUpdateInfo(info) {
  if (!info) return;
  $("ver-current").textContent = "v" + info.current;
  const hasUpdate = info.update_available;
  $("update-hint").hidden = !hasUpdate;
  $("ver-latest-ok").hidden = hasUpdate || !info.latest;
  if (hasUpdate) {
    $("ver-latest").textContent = "v" + info.latest;
    $("ver-url").href = info.url || "https://github.com/Melle79/brickfolio/releases";
  }
  const status = $("update-status");
  if (info.error) {
    status.textContent = info.error;
    status.hidden = false;
  } else {
    status.hidden = true;
  }
}

async function loadSettings() {
  const dealerUi = state.user && state.user.is_dealer;
  if ($("dealer-card")) {
    $("dealer-card").hidden = !dealerUi;
    if (dealerUi) $("offer-percent").value = state.offerPercent || 60;
  }
  if ($("pricelog-card")) {
    $("pricelog-card").hidden = !dealerUi;
    if (dealerUi) loadPriceLog(50);
  }
  $("settings-user").textContent = state.user ? state.user.username : "";
  $("own-name").value = state.user ? state.user.username : "";
  const isAdmin = !!(state.user && state.user.is_admin);
  $("api-panel").hidden = !isAdmin;
  $("name-card").hidden = !isAdmin;
  if (isAdmin && $("owner-name")) {
    $("owner-name").value =
      (state.ownerName && state.ownerName !== "Finn") ? state.ownerName : "";
    $("owner-name").placeholder = "Finn";
  }
  $("backup-card").hidden = !isAdmin;
  if (isAdmin) {
    api("/backup_info").then((b) => {
      if (!b || b.keep <= 0) return;
      const el = $("backup-auto-info");
      el.textContent = b.latest
        ? `Automatische Sicherung: täglich nach data/backups/ · ${b.count} von ${b.keep} Tagesständen`
        : `Automatische Sicherung: täglich nach data/backups/ (die erste entsteht kurz nach dem Start).`;
      const block = $("backup-restore-block");
      if (b.files && b.files.length) {
        block.hidden = false;
        $("backup-select").innerHTML = b.files.map((f) => {
          const time = f.mtime
            ? " · " + new Date(f.mtime * 1000).toLocaleTimeString("de-DE",
                { hour: "2-digit", minute: "2-digit" }) + " Uhr"
            : "";
          const label = f.name.replace("brickfolio-", "").replace(".db", "")
            + time + ` (${(f.size / 1024).toFixed(0)} KB)`;
          return `<option value="${esc(f.name)}">${esc(label)}</option>`;
        }).join("");
      }
    }).catch(() => {});
  }
  $("update-card").hidden = !isAdmin;
  if (isAdmin) checkForUpdate(false).then(renderUpdateInfo);
  const panel = $("admin-panel");
  panel.hidden = !isAdmin;
  if (!isAdmin) return;
  loadApiKeys();
  try {
    const users = await api("/users");
    $("user-list").innerHTML = users.map((u) => `
      <li>${esc(u.username)}${u.is_admin ? " 👑" : ""}
        <span class="user-actions">
          <button class="pw ${u.is_dealer ? "dealer-on" : ""}" data-dealer-user="${u.id}" data-dealer-state="${u.is_dealer ? 1 : 0}" title="Sammlerprofi-Modus">${u.is_dealer ? "Profi ✔" : "Profi"}</button>
          <button class="pw" data-pass-user="${u.id}" data-pass-name="${esc(u.username)}">Passwort</button>
          ${u.username !== state.user.username
            ? `<button class="del" data-del-user="${u.id}">Entfernen</button>` : ""}
        </span>
      </li>`).join("");
    $("user-list").querySelectorAll("[data-dealer-user]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const makeDealer = btn.dataset.dealerState !== "1";
        try {
          await api(`/users/${btn.dataset.dealerUser}/dealer`,
            { method: "POST", body: { is_dealer: makeDealer } });
          toast(makeDealer ? "Sammlerprofi aktiviert ✔"
                           : "Sammlerprofi deaktiviert");
          refreshMe().then(loadSettings);
        } catch (e) { toast(e.message); }
      });
    });
    $("user-list").querySelectorAll("[data-pass-user]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const pw = prompt(`Neues Passwort für "${btn.dataset.passName}" (mind. 4 Zeichen):`);
        if (pw == null) return;
        if (pw.length < 4) { toast("Bitte mindestens 4 Zeichen"); return; }
        try {
          await api(`/users/${btn.dataset.passUser}/password`,
            { method: "POST", body: { password: pw } });
          toast(`Passwort für ${btn.dataset.passName} gesetzt ✔`);
        } catch (e) { toast(e.message); }
      });
    });
    $("user-list").querySelectorAll("[data-del-user]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm("Benutzer wirklich entfernen?")) return;
        try { await api("/users/" + btn.dataset.delUser, { method: "DELETE" }); loadSettings(); }
        catch (e) { toast(e.message); }
      });
    });
  } catch (e) { toast(e.message); }
}

async function addUser() {
  const err = $("user-error");
  err.hidden = true;
  try {
    await api("/users", { method: "POST", body: {
      username: $("new-user").value.trim(), password: $("new-pass").value,
    }});
    $("new-user").value = ""; $("new-pass").value = "";
    toast("Benutzer angelegt ✔");
    loadSettings();
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
  }
}

/* ---------------------------------------------------------------- Start */
document.addEventListener("DOMContentLoaded", () => {
  $("btn-login").addEventListener("click", doLogin);
  $("btn-help").addEventListener("click", () => {
    $("help-overlay").hidden = false;
    document.body.style.overflow = "hidden";
  });
  const closeHelp = () => {
    $("help-overlay").hidden = true;
    document.body.style.overflow = "";
  };
  initCollapsibleCards();
  const ownerBtn = $("btn-owner-name");
  if (ownerBtn) {
    ownerBtn.addEventListener("click", async () => {
      try {
        const res = await api("/settings/owner_name", { method: "POST",
          body: { name: $("owner-name").value.trim() } });
        state.ownerName = res.owner_name;
        applyOwnerName(res.owner_name);
        toast("Anzeigename gespeichert ✔");
      } catch (e) { toast(e.message); }
    });
  }
  $("btn-help-close").addEventListener("click", closeHelp);
  $("help-overlay").addEventListener("click", (ev) => {
    if (ev.target === $("help-overlay")) closeHelp();
  });
  const closeProfile = () => {
    $("profile-overlay").hidden = true;
    document.body.style.overflow = "";
  };
  $("whoami").addEventListener("click", () => {
    if (!state.user) return;
    $("settings-user").textContent = state.user.username;
    $("own-name").value = state.user.username;
    $("own-name-error").hidden = true;
    $("own-pass-error").hidden = true;
    $("own-pass-current").value = "";
    $("own-pass-new").value = "";
    $("profile-overlay").hidden = false;
    document.body.style.overflow = "hidden";
  });
  $("btn-profile-close").addEventListener("click", closeProfile);
  $("profile-overlay").addEventListener("click", (ev) => {
    if (ev.target === $("profile-overlay")) closeProfile();
  });
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && !$("help-overlay").hidden) closeHelp();
    if (ev.key === "Escape" && !$("profile-overlay").hidden) closeProfile();
  });
  $("btn-setup").addEventListener("click", doSetup);
  $("setup-pass2").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") doSetup();
  });
  $("login-pass").addEventListener("keydown", (e) => { if (e.key === "Enter") doLogin(); });
  $("btn-logout").addEventListener("click", logout);
  $("btn-add-user").addEventListener("click", addUser);
  $("btn-own-pass").addEventListener("click", changeOwnPassword);
  $("btn-backup").addEventListener("click", downloadBackup);
  $("btn-new-list").addEventListener("click", async () => {
    const name = $("new-list-name").value.trim();
    if (!name) { toast("Bitte einen Namen eingeben"); return; }
    try {
      await api("/lists", { method: "POST", body: { name } });
      $("new-list-name").value = "";
      toast(`Liste "${name}" angelegt 🛒`);
      state.showArchive = false;
      loadLists();
      updateListsTab();
    } catch (e) { toast(e.message); }
  });
  $("btn-duplicates").addEventListener("click", toggleDuplicates);
  $("btn-csv-sample").addEventListener("click", downloadCsvSample);
  $("btn-pricelog-more").addEventListener("click",
    () => loadPriceLog(200));
  $("btn-update-check").addEventListener("click", async (ev) => {
    const btn = ev.currentTarget;
    btn.disabled = true;
    const info = await checkForUpdate(true);
    renderUpdateInfo(info);
    if (info && !info.update_available && !info.error) {
      toast("Brickfolio ist aktuell ✔");
    }
    btn.disabled = false;
  });
  $("btn-offer-percent").addEventListener("click", async () => {
    const pct = Number($("offer-percent").value.trim());
    if (!Number.isInteger(pct) || pct < 1 || pct > 100) {
      toast("Bitte eine ganze Zahl zwischen 1 und 100 eingeben");
      return;
    }
    try {
      await api("/settings/offer_percent", { method: "POST",
        body: { percent: pct } });
      state.offerPercent = pct;
      toast(`Vorschlag steht jetzt auf ${pct} % ✔`);
    } catch (e) { toast(e.message); }
  });
  $("btn-csv-import").addEventListener("click", () => $("csv-file").click());
  $("csv-file").addEventListener("change", (ev) => {
    const file = ev.target.files[0];
    ev.target.value = "";
    if (file) importCsvFile(file);
  });
  $("btn-toggle-archive").addEventListener("click", () => {
    state.showArchive = !state.showArchive;
    loadLists();
  });
  $("btn-restore").addEventListener("click", () => $("restore-file").click());
  $("btn-backup-dl").addEventListener("click", async () => {
    const name = $("backup-select").value;
    if (!name) return;
    try {
      const res = await fetch(`/api/backup_file/${encodeURIComponent(name)}`,
        { headers: { Authorization: `Bearer ${state.token}` } });
      if (!res.ok) throw new Error("Download fehlgeschlagen");
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 5000);
      toast("Tagesstand heruntergeladen 💾");
    } catch (e) { toast(e.message); }
  });
  $("btn-restore-snap").addEventListener("click", async () => {
    const name = $("backup-select").value;
    if (!name) return;
    const label = name.replace("brickfolio-", "").replace(".db", "");
    if (!confirm(`Wirklich den Stand vom ${label} wiederherstellen?\n\n`
      + `Alle aktuellen Daten werden durch diesen Tagesstand ersetzt. `
      + `Der jetzige Stand wird vorher automatisch als zusätzliche `
      + `Sicherung weggeschrieben.`)) return;
    try {
      const res = await api("/backup_restore_file", { method: "POST",
        body: { name } });
      alert(`Stand ${label} wiederhergestellt.\n`
        + `Sicherheitskopie: ${res.safety}\n\nDie App lädt jetzt neu.`);
      location.reload();
    } catch (e) { toast(e.message); }
  });
  $("restore-file").addEventListener("change", (ev) => {
    const file = ev.target.files[0];
    ev.target.value = "";
    if (file) restoreBackupFile(file);
  });
  $("btn-own-name").addEventListener("click", changeOwnUsername);
  $("btn-csv-col").addEventListener("click", () => exportCollectionCsv().catch((e) => toast(e.message)));
  $("btn-csv-want").addEventListener("click", () => exportWantedCsv().catch((e) => toast(e.message)));
  $("btn-print-col").addEventListener("click", () => printCollection().catch((e) => toast(e.message)));
  $("btn-print-want").addEventListener("click", () => printWanted().catch((e) => toast(e.message)));
  $("btn-save-keys").addEventListener("click", saveApiKeys);
  $("btn-test-keys").addEventListener("click", testApiKeys);
  $("btn-camera").addEventListener("click", () => $("file-input").click());
  $("btn-manual-toggle").addEventListener("click", () => {
    const f = $("manual-form");
    f.hidden = !f.hidden;
    if (!f.hidden) $("m-name").focus();
  });
  $("btn-manual-add").addEventListener("click", addManual);
  $("btn-manual-want").addEventListener("click", addManualWanted);
  setupCatalogSearch();
  $("file-input").addEventListener("change", (e) => {
    handlePhoto(e.target.files[0]);
    e.target.value = "";
  });

  // Bild per Drag & Drop auf die Scan-Fläche ziehen (Desktop)
  const dropZone = document.querySelector("[data-scan-drop]");
  if (dropZone) {
    ["dragenter", "dragover"].forEach((ev) =>
      dropZone.addEventListener(ev, (e) => {
        e.preventDefault();
        dropZone.classList.add("drag-over");
      }));
    ["dragleave", "dragend"].forEach((ev) =>
      dropZone.addEventListener(ev, (e) => {
        e.preventDefault();
        dropZone.classList.remove("drag-over");
      }));
    dropZone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropZone.classList.remove("drag-over");
      const file = [...(e.dataTransfer.files || [])]
        .find((f) => f.type.startsWith("image/"));
      if (file) handlePhoto(file);
      else toast("Bitte eine Bilddatei ablegen");
    });
  }

  // Screenshot/Bild aus der Zwischenablage einfügen (nur im Scan-Tab)
  document.addEventListener("paste", (e) => {
    const scanView = $("view-scan");
    if (!scanView || scanView.hidden) return;
    const item = [...(e.clipboardData?.items || [])]
      .find((i) => i.type.startsWith("image/"));
    if (item) {
      const file = item.getAsFile();
      if (file) { handlePhoto(file); toast("Bild eingefügt 📋"); }
    }
  });
  document.querySelectorAll(".tab").forEach((b) =>
    b.addEventListener("click", () => showTab(b.dataset.tab)));
  $("sort").addEventListener("change", loadCollection);
  $("type-filter").addEventListener("change", loadCollection);
  const collViewBtn = $("btn-collview");
  if (collViewBtn) {
    collViewBtn.addEventListener("click", () => {
      const grid = localStorage.getItem("bf_collview") === "grid";
      localStorage.setItem("bf_collview", grid ? "list" : "grid");
      applyCollView();
    });
  }
  let searchTimer;
  $("search").addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(loadCollection, 300);
  });

  if (state.token) { refreshMe(); showApp(); } else showLogin();

  // Galerie: Tipp auf ein Kartenbild öffnet alle Katalogbilder der Figur
  document.addEventListener("click", (ev) => {
    const img = ev.target.closest(".card-img");
    if (img && img.src && !img.src.startsWith("data:")) {
      openGallery(img.src, img.dataset.gid, img.dataset.gtype);
    }
  });
  $("lightbox").addEventListener("click", (ev) => {
    if (ev.target.closest(".lb-nav")) return;
    closeGallery();
  });
  $("lb-prev").addEventListener("click", () => stepGallery(-1));
  $("lb-next").addEventListener("click", () => stepGallery(1));
  document.addEventListener("keydown", (ev) => {
    if ($("lightbox").hidden) return;
    if (ev.key === "Escape") closeGallery();
    if (ev.key === "ArrowLeft") stepGallery(-1);
    if (ev.key === "ArrowRight") stepGallery(1);
  });
  let touchX = null;
  $("lightbox").addEventListener("touchstart",
    (ev) => { touchX = ev.touches[0].clientX; }, { passive: true });
  $("lightbox").addEventListener("touchend", (ev) => {
    if (touchX == null) return;
    const dx = ev.changedTouches[0].clientX - touchX;
    touchX = null;
    if (Math.abs(dx) > 40) stepGallery(dx < 0 ? 1 : -1);
  }, { passive: true });
  $("lightbox-img").addEventListener("error", () => {
    // Nicht existierende Bildvarianten still aussortieren
    if (gallery.urls.length <= 1) { closeGallery(); return; }
    gallery.urls.splice(gallery.idx, 1);
    gallery.idx = gallery.idx % gallery.urls.length;
    renderGallery();
  });

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
});
