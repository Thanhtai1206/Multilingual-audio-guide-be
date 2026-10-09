/*
 * Admin dashboard - HTML/CSS/JS thuần, gọi API /api/v1/admin/*.
 * Mỗi "trang" là 1 hàm render vào #page.
 */
(() => {
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];
  const esc = escapeHtml;
  const state = { token: storage.get("admin_token"), user: null, page: "dashboard", pois: [], timer: null };

  const isAdmin = () => state.user && state.user.role === "admin";
  const fmtDate = (v) => (v ? new Date(v).toLocaleString("vi-VN") : "—");
  const money = (v) => (v || 0).toLocaleString("vi-VN") + " ₫";
  const tag = (v, label) => `<span class="tag ${esc(v)}">${esc(label ?? v)}</span>`;

  function toast(text) {
    const el = $("#toast");
    el.textContent = text;
    el.classList.remove("hidden");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => el.classList.add("hidden"), 3500);
  }

  async function api(path, opts = {}) {
    try {
      return (await apiRequest("/admin" + path, { ...opts, token: state.token })).data;
    } catch (err) {
      if (err.status === 401) logout("Phiên đăng nhập hết hạn");
      let msg = err.message;
      if (err.details && Array.isArray(err.details)) msg += ": " + err.details.map((d) => `${d.field} - ${d.message}`).join("; ");
      toast("Lỗi: " + msg);
      throw err;
    }
  }

  // ---------------- Modal ----------------
  function openModal(title, html, onMount) {
    $("#modal-title").textContent = title;
    $("#modal-body").innerHTML = html;
    $("#modal").classList.remove("hidden");
    if (onMount) onMount($("#modal-body"));
  }
  function closeModal() {
    $("#modal").classList.add("hidden");
    clearInterval(state.timer);
  }
  $("#modal-close").onclick = closeModal;
  $("#modal").addEventListener("click", (e) => e.target.id === "modal" && closeModal());

  function formData(form) {
    const data = {};
    for (const el of form.elements) {
      if (!el.name) continue;
      if (el.type === "checkbox") data[el.name] = el.checked;
      else if (el.type === "number") data[el.name] = el.value === "" ? null : Number(el.value);
      else data[el.name] = el.value;
    }
    return data;
  }

  // ---------------- Đăng nhập ----------------
  $("#login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = formData(e.target);
    try {
      const { data } = await apiRequest("/admin/auth/login", { method: "POST", body });
      state.token = data.access_token;
      storage.set("admin_token", state.token);
      await boot();
    } catch (err) {
      $("#login-msg").textContent = err.message;
    }
  });

  function logout(msg = "") {
    state.token = null;
    storage.remove("admin_token");
    $("#shell").classList.add("hidden");
    $("#login").classList.remove("hidden");
    $("#login-msg").textContent = msg;
  }
  $("#btn-logout").onclick = (e) => {
    e.preventDefault();
    logout();
  };

  async function boot() {
    try {
      state.user = (await apiRequest("/admin/auth/me", { token: state.token })).data;
    } catch (_) {
      return logout();
    }
    $("#login").classList.add("hidden");
    $("#shell").classList.remove("hidden");
    $("#user-name").textContent = state.user.full_name;
    $("#user-role").textContent = state.user.role;
    $$("[data-admin-only]").forEach((el) => el.classList.toggle("hidden", !isAdmin()));
    go(state.page);
  }

  // ---------------- Điều hướng ----------------
  const PAGES = {
    dashboard: ["Tổng quan", renderDashboard],
    pois: ["Điểm tham quan (POI)", renderPois],
    tours: ["Lộ trình", renderTours],
    access: ["Mã truy cập & thanh toán", renderAccess],
    knowledge: ["Kiến thức cho chatbot", renderKnowledge],
    languages: ["Ngôn ngữ", renderLanguages],
    users: ["Tài khoản quản trị", renderUsers],
  };
  function go(page) {
    state.page = page;
    $$("#nav button").forEach((b) => b.classList.toggle("active", b.dataset.page === page));
    $("#page-title").textContent = PAGES[page][0];
    $("#page").innerHTML = '<p class="muted">Đang tải…</p>';
    PAGES[page][1]().catch(() => ($("#page").innerHTML = '<p class="msg">Không tải được dữ liệu</p>'));
  }
  $$("#nav button").forEach((b) => (b.onclick = () => go(b.dataset.page)));

  // ================================================================ TỔNG QUAN
  async function renderDashboard() {
    const [s, logs] = await Promise.all([api("/stats"), api("/chat-logs?limit=10")]);
    const card = (label, value) => `<tr><td>${label}</td><td><b>${value}</b></td></tr>`;
    $("#page").innerHTML = `
      <table class="stats">
        ${card("POI đang hoạt động", `${s.active_pois}/${s.total_pois}`)}
        ${card("Ngôn ngữ bật", s.active_languages)}
        ${card("Độ phủ bản dịch", s.localization_coverage_percent + "%")}
        ${card("Doanh thu", money(s.revenue_vnd))}
        ${card("Câu hỏi chatbot", s.total_chats)}
        ${card("Lượt tương tác", s.total_events)}
        ${card("Tác vụ nền đang chạy", s.background_tasks)}
      </table>
      <div class="toolbar">${isAdmin() ? '<button id="btn-localize-all" class="btn primary">Dịch + tạo audio tất cả</button>' : ""}
        <button id="btn-refresh" class="btn">Tải lại</button></div>
      <div class="grid-2">
        <div class="box"><h3>Trạng thái bản dịch</h3>${Object.entries(s.localization_status).map(([k, v]) => `${tag(k)} ${v}`).join(" &nbsp; ") || '<span class="muted">Chưa có</span>'}
          <h3>Phiên truy cập</h3>${Object.entries(s.access_sessions).map(([k, v]) => `${tag(k)} ${v}`).join(" &nbsp; ") || '<span class="muted">Chưa có</span>'}</div>
        <div class="box"><h3>POI được quan tâm nhất</h3><table><tr><th>POI</th><th>Lượt</th></tr>
          ${s.top_pois.map((p) => `<tr><td>${esc(p.name)}</td><td>${p.count}</td></tr>`).join("") || '<tr><td colspan="2" class="muted">Chưa có dữ liệu</td></tr>'}</table>
          <h3>Ngôn ngữ du khách dùng</h3>${Object.entries(s.events_by_lang).map(([k, v]) => `<b>${esc(k)}</b>: ${v}`).join(" · ") || '<span class="muted">Chưa có</span>'}</div>
      </div>
      <div class="box"><h3>Câu hỏi gần đây</h3><table><tr><th>Thời gian</th><th>NN</th><th>Câu hỏi</th><th>Trả lời</th></tr>
        ${logs.map((l) => `<tr><td class="small">${fmtDate(l.created_at)}</td><td>${esc(l.lang)}</td><td>${esc(l.question)}</td><td class="small">${esc(l.answer).slice(0, 160)}</td></tr>`).join("") || '<tr><td colspan="4" class="muted">Chưa có</td></tr>'}</table></div>`;
    $("#btn-refresh").onclick = () => go("dashboard");
    const all = $("#btn-localize-all");
    if (all) all.onclick = async () => {
      const r = await api("/localize-all", { method: "POST", body: { force: false } });
      toast(`Đã xếp hàng ${r.queued} POI. Quá trình chạy nền, có thể mất vài phút.`);
    };
  }

  // ================================================================ POI
  async function renderPois(q = "") {
    const page = await api(`/pois?size=100${q ? "&q=" + encodeURIComponent(q) : ""}`);
    state.pois = page.items;
    $("#page").innerHTML = `
      <div class="toolbar"><input id="poi-q" placeholder="Tìm theo tên hoặc mã…" value="${esc(q)}" />
        <span class="spacer"></span>${isAdmin() ? '<button id="btn-new-poi" class="btn primary">+ Thêm POI</button>' : ""}</div>
      <div class="box"><table><tr><th>#</th><th>Mã</th><th>Tên</th><th>Tọa độ</th><th>Bán kính</th><th>Ưu tiên</th><th>Trạng thái</th><th></th></tr>
      ${page.items.map((p) => `<tr><td>${p.sort_order}</td><td><code>${esc(p.code)}</code></td><td><b>${esc(p.name)}</b></td>
        <td class="small">${p.latitude.toFixed(5)}, ${p.longitude.toFixed(5)}</td><td>${p.trigger_radius_m} m</td><td>${p.priority}</td>
        <td>${p.is_active ? tag("on", "Hiển thị") : tag("off", "Ẩn")}</td>
        <td class="actions"><button class="btn small-btn" data-loc="${p.id}">Bản dịch</button>
          ${isAdmin() ? `<button class="btn small-btn" data-edit="${p.id}">Sửa</button><button class="btn small-btn danger" data-del="${p.id}">Xóa</button>` : ""}</td></tr>`).join("")}
      </table><p class="muted small">Tổng: ${page.total}</p></div>`;
    $("#poi-q").onchange = (e) => renderPois(e.target.value);
    if ($("#btn-new-poi")) $("#btn-new-poi").onclick = () => poiForm();
    $$("[data-edit]").forEach((b) => (b.onclick = () => poiForm(state.pois.find((p) => p.id === b.dataset.edit))));
    $$("[data-loc]").forEach((b) => (b.onclick = () => localizationModal(state.pois.find((p) => p.id === b.dataset.loc))));
    $$("[data-del]").forEach((b) => (b.onclick = async () => {
      const poi = state.pois.find((p) => p.id === b.dataset.del);
      if (!confirm(`Xóa "${poi.name}"? Mọi bản dịch và audio sẽ bị xóa theo.`)) return;
      await api(`/pois/${poi.id}`, { method: "DELETE" });
      toast("Đã xóa");
      renderPois(q);
    }));
  }

  // Mã tiện ích -> nhãn (phải khớp AMENITIES trong app/services/poi_details.py; có test kiểm tra)
  const AMENITY_LABELS = {
    wheelchair: "Lối đi cho xe lăn",
    stairs: "Nhiều bậc thang",
    parking: "Bãi gửi xe",
    restroom: "Nhà vệ sinh",
    drinking_water: "Nước uống",
    shade: "Có bóng mát, ghế nghỉ",
    photo_ok: "Được chụp ảnh",
    no_photo_ceremony: "Không chụp ảnh khi hành lễ",
    shoes_off: "Bỏ giày dép trước khi vào",
    quiet_zone: "Giữ yên lặng",
    dress_code: "Trang phục kín đáo",
  };
  const DAYS = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ nhật"];

  // [{day, open, close}] -> "06:00-11:30, 13:30-21:00" cho từng ngày
  function hoursToText(hours, day) {
    return (hours || []).filter((h) => h.day === day).map((h) => `${h.open}-${h.close}`).join(", ");
  }

  // Ngược lại: đọc ô nhập của 1 ngày. Trống = đóng cửa. Báo lỗi rõ ràng nếu gõ sai.
  function textToHours(text, day) {
    const result = [];
    for (const part of text.split(",").map((x) => x.trim()).filter(Boolean)) {
      const m = part.match(/^(\d{1,2})[:h](\d{2})\s*-\s*(\d{1,2})[:h](\d{2})$/);
      if (!m) throw new Error(`${DAYS[day]}: "${part}" không đúng dạng, ví dụ 06:00-21:00`);
      const pad = (n) => String(n).padStart(2, "0");
      result.push({ day, open: `${pad(m[1])}:${m[2]}`, close: `${pad(m[3])}:${m[4]}` });
    }
    return result;
  }

  function poiForm(poi) {
    const p = poi || { code: "", name: "", description: "", category: "landmark", latitude: 16.1003, longitude: 108.2777,
      trigger_radius_m: 30, priority: 0, sort_order: (state.pois.length || 0) + 1, is_active: true, thumbnail_url: "" };
    openModal(poi ? "Sửa POI" : "Thêm POI", `
      <form id="poi-form" class="form">
        <label>Mã (không dấu)<input name="code" value="${esc(p.code)}" required pattern="[A-Za-z0-9_\\-]{2,50}" /></label>
        <label>Loại<select name="category">${["landmark", "statue", "hall", "gate", "garden", "viewpoint", "service"].map((c) => `<option ${c === p.category ? "selected" : ""}>${c}</option>`).join("")}</select></label>
        <label class="full">Tên (tiếng Việt)<input name="name" value="${esc(p.name)}" required /></label>
        <label class="full">Nội dung thuyết minh (tiếng Việt) <textarea name="description" required>${esc(p.description)}</textarea></label>
        <div class="full toolbar"><button type="button" id="btn-ai" class="btn small-btn">Gợi ý bằng AI</button>
          <span class="muted small">Đổi tên/nội dung sẽ tự động dịch lại 16 ngôn ngữ và tạo audio mới.</span></div>
        <label>Vĩ độ<input name="latitude" type="number" step="0.000001" value="${p.latitude}" required /></label>
        <label>Kinh độ<input name="longitude" type="number" step="0.000001" value="${p.longitude}" required /></label>
        <div class="full"><div id="pick-map"></div><span class="muted small">Chạm vào bản đồ để chọn tọa độ. Vòng tròn = vùng tự phát thuyết minh.</span></div>
        <label>Bán kính kích hoạt (m)<input name="trigger_radius_m" type="number" min="5" max="500" value="${p.trigger_radius_m}" /></label>
        <label>Mức ưu tiên (0-100)<input name="priority" type="number" min="0" max="100" value="${p.priority}" /></label>
        <label>Thứ tự hiển thị<input name="sort_order" type="number" value="${p.sort_order}" /></label>
        <label>Ảnh đại diện (URL)<input name="thumbnail_url" value="${esc(p.thumbnail_url || "")}" /></label>

        <fieldset class="full"><legend>Thông tin chi tiết (hiện cho du khách như trên Google Maps)</legend>
          <table class="hours-table">
            ${DAYS.map((d, i) => `<tr><td>${d}</td><td><input class="hours-in" data-day="${i}" value="${esc(hoursToText(p.opening_hours, i))}" placeholder="Trống = đóng cửa" /></td></tr>`).join("")}
          </table>
          <p class="muted small">Ghi dạng <b>06:00-21:00</b>. Nghỉ trưa thì ghi 2 khung: <b>06:00-11:30, 13:30-21:00</b>.
            <button type="button" id="btn-copy-hours" class="btn small-btn">Chép giờ Thứ Hai cho cả tuần</button></p>
          <div class="form">
            <label>Vé vào cửa (đồng, 0 = miễn phí)<input name="entry_fee_vnd" type="number" min="0" step="1000" value="${p.entry_fee_vnd || 0}" /></label>
            <label>Thời gian tham quan gợi ý (phút)<input name="visit_minutes" type="number" min="1" max="600" value="${p.visit_minutes || ""}" /></label>
          </div>
          <div class="amen-grid">${Object.entries(AMENITY_LABELS).map(([code, label]) =>
            `<label class="check"><input type="checkbox" class="amen-in" value="${code}" ${(p.amenities || []).includes(code) ? "checked" : ""} /> ${label}</label>`).join("")}</div>
          <label>Lưu ý cho du khách (tiếng Việt, tự dịch sang 16 ngôn ngữ)<textarea name="tips" maxlength="2000" class="short">${esc(p.tips || "")}</textarea></label>
        </fieldset>

        <label class="check full"><input type="checkbox" name="is_active" ${p.is_active ? "checked" : ""} /> Hiển thị cho du khách</label>
        <div class="row-actions"><button type="button" class="btn" id="btn-cancel">Hủy</button><button class="btn primary">Lưu</button></div>
      </form>`, (root) => {
      const form = $("#poi-form", root);
      const map = L.map($("#pick-map", root)).setView([p.latitude, p.longitude], 18);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 20, maxNativeZoom: 19, attribution: "© OSM" }).addTo(map);
      const marker = L.circleMarker([p.latitude, p.longitude], { radius: 7, color: "#fff", weight: 2, fillColor: "#b45309", fillOpacity: 1 }).addTo(map);
      const circle = L.circle([p.latitude, p.longitude], { radius: p.trigger_radius_m, color: "#b45309" }).addTo(map);
      const sync = () => {
        const ll = [Number(form.latitude.value), Number(form.longitude.value)];
        marker.setLatLng(ll); circle.setLatLng(ll); circle.setRadius(Number(form.trigger_radius_m.value) || 30);
      };
      map.on("click", (e) => { form.latitude.value = e.latlng.lat.toFixed(6); form.longitude.value = e.latlng.lng.toFixed(6); sync(); });
      [form.latitude, form.longitude, form.trigger_radius_m].forEach((el) => (el.oninput = sync));
      setTimeout(() => map.invalidateSize(), 100);
      $("#btn-cancel", root).onclick = closeModal;
      $("#btn-copy-hours", root).onclick = () => {
        const inputs = $$(".hours-in", root);
        inputs.forEach((el) => (el.value = inputs[0].value));
      };
      $("#btn-ai", root).onclick = async (e) => {
        e.target.disabled = true;
        try {
          const r = await api("/ai/enhance-description", { method: "POST", body: { name: form.name.value, description: form.description.value } });
          if (confirm("Gợi ý của AI:\n\n" + r.description + "\n\nDùng nội dung này?")) form.description.value = r.description;
        } catch (_) {} finally { e.target.disabled = false; }
      };
      form.onsubmit = async (e) => {
        e.preventDefault();
        const body = formData(form);
        if (!body.thumbnail_url) body.thumbnail_url = null;
        try {
          body.opening_hours = $$(".hours-in", root).flatMap((el) => textToHours(el.value, Number(el.dataset.day)));
        } catch (err) {
          toast(err.message);
          return;
        }
        body.amenities = $$(".amen-in", root).filter((el) => el.checked).map((el) => el.value);
        body.entry_fee_vnd = body.entry_fee_vnd || 0;
        await api(poi ? `/pois/${poi.id}` : "/pois", { method: poi ? "PUT" : "POST", body });
        toast(poi ? "Đã lưu" : "Đã tạo POI - đang dịch đa ngôn ngữ ở nền");
        closeModal();
        renderPois();
      };
    });
  }

  function localizationModal(poi) {
    const load = async () => {
      const rows = await api(`/pois/${poi.id}/localizations`);
      const busy = rows.some((r) => ["pending", "processing"].includes(r.status));
      $("#modal-body").innerHTML = `
        <div class="toolbar">${isAdmin() ? `<button id="btn-loc-all" class="btn primary small-btn">Dịch các ngôn ngữ còn thiếu</button>
          <button id="btn-loc-force" class="btn small-btn">Dịch lại toàn bộ (ghi đè)</button>` : ""}
          <span class="spacer"></span><span class="muted small">${busy ? "Đang xử lý, trang tự cập nhật..." : ""}</span></div>
        <table><tr><th>Ngôn ngữ</th><th>Trạng thái</th><th>Nguồn</th><th>Tên</th><th>Audio</th><th></th></tr>
        ${rows.map((r) => `<tr><td><b>${esc(r.lang)}</b> <span class="small muted">${esc(r.language_name)}</span></td>
          <td>${tag(r.status)} ${r.status === "ready" && !r.is_fresh ? tag("outdated", "cũ") : ""}${r.error ? `<div class="small" style="color:#c00">${esc(r.error)}</div>` : ""}</td>
          <td class="small">${esc(r.translated_by || "—")}</td><td class="small">${esc(r.name || "—")}</td>
          <td>${r.audio_url ? `<audio controls preload="none" src="${esc(r.audio_url)}"></audio>` : '<span class="muted small">—</span>'}</td>
          <td class="actions">${isAdmin() && r.lang !== "vi" ? `<button class="btn small-btn" data-manual="${r.lang}">Sửa tay</button>` : ""}
            ${isAdmin() ? `<button class="btn small-btn" data-redo="${r.lang}">Dịch lại</button>` : ""}</td></tr>`).join("")}</table>`;
      if ($("#btn-loc-all")) {
        $("#btn-loc-all").onclick = () => queue(null, false);
        $("#btn-loc-force").onclick = () => confirm("Ghi đè cả bản sửa tay?") && queue(null, true);
      }
      $$("[data-redo]").forEach((b) => (b.onclick = () => queue([b.dataset.redo], true)));
      $$("[data-manual]").forEach((b) => (b.onclick = () => manualEdit(rows.find((r) => r.lang === b.dataset.manual))));
      clearInterval(state.timer);
      if (busy) state.timer = setInterval(load, 3000);
    };
    const queue = async (languages, force) => {
      const r = await api(`/pois/${poi.id}/localize`, { method: "POST", body: { languages, force } });
      toast(`Đã xếp hàng ${r.queued} ngôn ngữ`);
      load();
    };
    const manualEdit = (row) => {
      clearInterval(state.timer);
      $("#modal-body").innerHTML = `<form id="manual-form" class="form">
        <p class="full muted">Bản sửa tay sẽ không bị dịch máy ghi đè. Gốc tiếng Việt: <b>${esc(poi.name)}</b></p>
        <label class="full">Tên (${esc(row.lang)})<input name="name" value="${esc(row.name || "")}" required /></label>
        <label class="full">Nội dung (${esc(row.lang)})<textarea name="description" required>${esc(row.description || "")}</textarea></label>
        <label class="check full"><input type="checkbox" name="regenerate_audio" checked /> Tạo lại audio</label>
        <div class="row-actions"><button type="button" class="btn" id="btn-back">Quay lại</button><button class="btn primary">Lưu</button></div></form>`;
      $("#btn-back").onclick = load;
      $("#manual-form").onsubmit = async (e) => {
        e.preventDefault();
        await api(`/pois/${poi.id}/localizations/${row.lang}`, { method: "PUT", body: formData(e.target) });
        toast("Đã lưu bản dịch");
        load();
      };
    };
    openModal(`Bản dịch: ${poi.name}`, '<p class="muted">Đang tải…</p>', load);
  }

  // ================================================================ LỘ TRÌNH
  async function renderTours() {
    const [tours, pois] = await Promise.all([api("/tours"), api("/pois?size=100")]);
    state.pois = pois.items;
    const name = (id) => (state.pois.find((p) => p.id === id) || {}).name || "?";
    $("#page").innerHTML = `<div class="toolbar"><span class="spacer"></span>${isAdmin() ? '<button id="btn-new-tour" class="btn primary">+ Thêm lộ trình</button>' : ""}</div>
      <div class="box"><table><tr><th>Mã</th><th>Tên</th><th>Các điểm</th><th>Thời gian</th><th>Đã dịch</th><th>Trạng thái</th><th></th></tr>
      ${tours.map((t) => `<tr><td><code>${esc(t.code)}</code></td><td><b>${esc(t.name)}</b><div class="small muted">${esc(t.description || "")}</div></td>
        <td class="small">${t.poi_ids.map((id, i) => `${i + 1}. ${esc(name(id))}`).join("<br>")}</td><td>${t.estimated_minutes}′</td>
        <td class="small">${t.translated_languages.length} NN</td><td>${t.is_active ? tag("on", "Hiển thị") : tag("off", "Ẩn")}</td>
        <td class="actions">${isAdmin() ? `<button class="btn small-btn" data-edit="${t.id}">Sửa</button><button class="btn small-btn danger" data-del="${t.id}">Xóa</button>` : ""}</td></tr>`).join("")}</table></div>`;
    if ($("#btn-new-tour")) $("#btn-new-tour").onclick = () => tourForm();
    $$("[data-edit]").forEach((b) => (b.onclick = () => tourForm(tours.find((t) => t.id === b.dataset.edit))));
    $$("[data-del]").forEach((b) => (b.onclick = async () => {
      if (!confirm("Xóa lộ trình này?")) return;
      await api(`/tours/${b.dataset.del}`, { method: "DELETE" });
      renderTours();
    }));
  }

  function tourForm(tour) {
    const t = tour || { code: "", name: "", description: "", poi_ids: [], estimated_minutes: 30, is_active: true };
    let selected = [...t.poi_ids];
    openModal(tour ? "Sửa lộ trình" : "Thêm lộ trình", `<form id="tour-form" class="form">
      <label>Mã<input name="code" value="${esc(t.code)}" required /></label>
      <label>Thời gian ước tính (phút)<input name="estimated_minutes" type="number" min="1" value="${t.estimated_minutes}" /></label>
      <label class="full">Tên<input name="name" value="${esc(t.name)}" required /></label>
      <label class="full">Mô tả<input name="description" value="${esc(t.description || "")}" /></label>
      <div class="full"><b class="small">Thứ tự các điểm (bấm để thêm theo thứ tự)</b><div id="sel" class="chips" style="margin:8px 0"></div>
        <div class="chips">${state.pois.map((p) => `<button type="button" class="btn small-btn" data-add="${p.id}">+ ${esc(p.name)}</button>`).join("")}</div></div>
      <label class="check full"><input type="checkbox" name="is_active" ${t.is_active ? "checked" : ""}/> Hiển thị</label>
      <div class="row-actions"><button class="btn primary">Lưu</button></div></form>`, (root) => {
      const draw = () => {
        $("#sel", root).innerHTML = selected.map((id, i) => `<span>${i + 1}. ${esc((state.pois.find((p) => p.id === id) || {}).name || id)} <button type="button" data-rm="${i}">x</button></span>`).join("") || '<span class="muted">Chưa chọn điểm nào</span>';
        $$("[data-rm]", root).forEach((b) => (b.onclick = () => { selected.splice(Number(b.dataset.rm), 1); draw(); }));
      };
      $$("[data-add]", root).forEach((b) => (b.onclick = () => { if (!selected.includes(b.dataset.add)) selected.push(b.dataset.add); draw(); }));
      draw();
      $("#tour-form", root).onsubmit = async (e) => {
        e.preventDefault();
        const body = { ...formData(e.target), poi_ids: selected };
        await api(tour ? `/tours/${tour.id}` : "/tours", { method: tour ? "PUT" : "POST", body });
        closeModal();
        renderTours();
      };
    });
  }

  // ================================================================ MÃ TRUY CẬP
  async function renderAccess(status = "", page = 1) {
    const data = await api(`/access-sessions?page=${page}&size=20${status ? "&status=" + status : ""}`);
    const pages = Math.max(1, Math.ceil(data.total / data.size));
    $("#page").innerHTML = `
      <div class="box"><h3>Bán vé tiền mặt</h3>
        <form id="cash-form" class="toolbar"><label>Số lượng<input name="quantity" type="number" min="1" max="50" value="1" style="width:100px" /></label>
          <label>Ghi chú<input name="note" placeholder="VD: Đoàn khách Hàn Quốc" style="min-width:260px" /></label>
          <button class="btn primary" style="align-self:flex-end">Tạo mã</button></form>
        <div id="new-codes" class="codes" style="margin-top:12px"></div></div>
      <div class="box"><div class="toolbar"><h3 style="margin:0">Lịch sử phiên truy cập</h3><span class="spacer"></span>
        <select id="status-filter"><option value="">Tất cả trạng thái</option>${["pending", "paid", "active", "expired", "cancelled"].map((s) => `<option ${s === status ? "selected" : ""}>${s}</option>`).join("")}</select></div>
        <table><tr><th>Mã</th><th>Hình thức</th><th>Trạng thái</th><th>Số tiền</th><th>Tạo lúc</th><th>Hết hạn dùng</th><th>Ghi chú</th><th></th></tr>
        ${data.items.map((s) => `<tr><td><code>${esc(s.code)}</code></td><td>${s.method === "cash" ? "Tiền mặt" : "Online"}</td><td>${tag(s.status)}</td>
          <td>${money(s.amount)}</td><td class="small">${fmtDate(s.created_at)}</td><td class="small">${fmtDate(s.access_expires_at)}</td><td class="small">${esc(s.note || "")}</td>
          <td>${isAdmin() && ["paid", "active", "pending"].includes(s.status) ? `<button class="btn small-btn danger" data-revoke="${s.id}">Thu hồi</button>` : ""}</td></tr>`).join("")}</table>
        <div class="pager"><button class="btn small-btn" id="prev" ${page <= 1 ? "disabled" : ""}>Trước</button> ${page}/${pages}
          <button class="btn small-btn" id="next" ${page >= pages ? "disabled" : ""}>Sau</button></div></div>`;
    $("#cash-form").onsubmit = async (e) => {
      e.preventDefault();
      const body = formData(e.target);
      if (!body.note) body.note = null;
      const codes = await api("/access-codes", { method: "POST", body });
      $("#new-codes").innerHTML = codes.map((c) => `<span class="code">${esc(c.code)}</span>`).join("");
      toast("Đưa mã cho khách nhập vào ứng dụng");
      setTimeout(() => renderAccess(status, 1).then(() => ($("#new-codes").innerHTML = codes.map((c) => `<span class="code">${esc(c.code)}</span>`).join(""))), 50);
    };
    $("#status-filter").onchange = (e) => renderAccess(e.target.value, 1);
    $("#prev").onclick = () => renderAccess(status, page - 1);
    $("#next").onclick = () => renderAccess(status, page + 1);
    $$("[data-revoke]").forEach((b) => (b.onclick = async () => {
      if (!confirm("Thu hồi quyền truy cập này?")) return;
      await api(`/access-sessions/${b.dataset.revoke}/revoke`, { method: "POST" });
      renderAccess(status, page);
    }));
  }

  // ================================================================ KIẾN THỨC
  async function renderKnowledge() {
    const items = await api("/knowledge");
    $("#page").innerHTML = `<div class="toolbar"><span class="muted">Chatbot tìm câu trả lời trong nội dung POI và các bài viết dưới đây (viết bằng tiếng Việt).</span>
      <span class="spacer"></span>${isAdmin() ? '<button id="btn-new" class="btn primary">+ Thêm bài viết</button>' : ""}</div>
      <div class="box"><table><tr><th>Tiêu đề</th><th>Nội dung</th><th>Trạng thái</th><th></th></tr>
      ${items.map((a) => `<tr><td><b>${esc(a.title)}</b></td><td class="small">${esc(a.content)}</td><td>${a.is_active ? tag("on", "Dùng") : tag("off", "Tắt")}</td>
        <td class="actions">${isAdmin() ? `<button class="btn small-btn" data-edit="${a.id}">Sửa</button><button class="btn small-btn danger" data-del="${a.id}">Xóa</button>` : ""}</td></tr>`).join("")}</table></div>`;
    const form = (a) => {
      const x = a || { title: "", content: "", tags: [], is_active: true };
      openModal(a ? "Sửa bài viết" : "Thêm bài viết", `<form id="art" class="form">
        <label class="full">Tiêu đề<input name="title" value="${esc(x.title)}" required /></label>
        <label class="full">Nội dung<textarea name="content" required>${esc(x.content)}</textarea></label>
        <label class="full">Từ khóa (phân cách dấu phẩy)<input name="tags" value="${esc(x.tags.join(", "))}" /></label>
        <label class="check full"><input type="checkbox" name="is_active" ${x.is_active ? "checked" : ""}/> Dùng cho chatbot</label>
        <div class="row-actions"><button class="btn primary">Lưu</button></div></form>`, (root) => {
        $("#art", root).onsubmit = async (e) => {
          e.preventDefault();
          const body = formData(e.target);
          body.tags = body.tags.split(",").map((s) => s.trim()).filter(Boolean);
          await api(a ? `/knowledge/${a.id}` : "/knowledge", { method: a ? "PUT" : "POST", body });
          closeModal();
          renderKnowledge();
        };
      });
    };
    if ($("#btn-new")) $("#btn-new").onclick = () => form();
    $$("[data-edit]").forEach((b) => (b.onclick = () => form(items.find((a) => a.id === b.dataset.edit))));
    $$("[data-del]").forEach((b) => (b.onclick = async () => {
      if (!confirm("Xóa bài viết?")) return;
      await api(`/knowledge/${b.dataset.del}`, { method: "DELETE" });
      renderKnowledge();
    }));
  }

  // ================================================================ NGÔN NGỮ
  async function renderLanguages() {
    const langs = await api("/languages");
    $("#page").innerHTML = `<div class="box"><p class="muted">Tắt ngôn ngữ để ẩn khỏi app (tiếng Việt và tiếng Anh là bắt buộc).</p>
      <table><tr><th>Mã</th><th>Tên</th><th>Mã dịch máy</th><th>Giọng đọc</th><th>Bật</th></tr>
      ${langs.map((l) => `<tr><td><b>${esc(l.code)}</b></td><td>${esc(l.native_name)} <span class="muted small">${esc(l.name)}</span></td>
        <td><code>${esc(l.translator_code)}</code></td><td class="small">${esc(l.tts_voice)}</td>
        <td><input type="checkbox" data-code="${l.code}" ${l.is_active ? "checked" : ""} ${isAdmin() ? "" : "disabled"} style="width:auto" /></td></tr>`).join("")}</table></div>`;
    $$("[data-code]").forEach((cb) => (cb.onchange = async () => {
      try {
        await api(`/languages/${cb.dataset.code}`, { method: "PATCH", body: { is_active: cb.checked } });
        toast("Đã cập nhật");
      } catch (_) {
        cb.checked = !cb.checked;
      }
    }));
  }

  // ================================================================ TÀI KHOẢN
  async function renderUsers() {
    const users = await api("/users");
    $("#page").innerHTML = `<div class="toolbar"><span class="muted">admin: toàn quyền · staff: bán vé tiền mặt, xem dữ liệu</span><span class="spacer"></span>
      <button id="btn-new" class="btn primary">+ Thêm tài khoản</button></div>
      <div class="box"><table><tr><th>Tên đăng nhập</th><th>Họ tên</th><th>Vai trò</th><th>Trạng thái</th><th>Đăng nhập gần nhất</th><th></th></tr>
      ${users.map((u) => `<tr><td><b>${esc(u.username)}</b></td><td>${esc(u.full_name)}</td><td>${tag(u.role === "admin" ? "admin" : "", u.role)}</td>
        <td>${u.is_active ? tag("on", "Hoạt động") : tag("off", "Khóa")}</td><td class="small">${fmtDate(u.last_login_at)}</td>
        <td class="actions">${u.id !== state.user.id ? `<button class="btn small-btn" data-toggle="${u.id}" data-active="${u.is_active}">${u.is_active ? "Khóa" : "Mở khóa"}</button>` : ""}</td></tr>`).join("")}</table></div>`;
    $("#btn-new").onclick = () => openModal("Thêm tài khoản", `<form id="uf" class="form">
      <label>Tên đăng nhập<input name="username" required /></label><label>Mật khẩu (≥ 8 ký tự)<input name="password" type="password" minlength="8" required /></label>
      <label>Họ tên<input name="full_name" required /></label><label>Vai trò<select name="role"><option value="staff">staff</option><option value="admin">admin</option></select></label>
      <div class="row-actions"><button class="btn primary">Tạo</button></div></form>`, (root) => {
      $("#uf", root).onsubmit = async (e) => {
        e.preventDefault();
        await api("/users", { method: "POST", body: formData(e.target) });
        closeModal();
        renderUsers();
      };
    });
    $$("[data-toggle]").forEach((b) => (b.onclick = async () => {
      await api(`/users/${b.dataset.toggle}`, { method: "PATCH", body: { is_active: b.dataset.active !== "true" } });
      renderUsers();
    }));
  }

  // ---------------- Khởi động ----------------
  if (state.token) boot();
  else logout();
})();
