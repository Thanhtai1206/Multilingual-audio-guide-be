// App du khách: mua vé -> tải dữ liệu -> bản đồ + GPS -> tới gần điểm nào thì tự phát thuyết minh.
(function () {
  // Thông số geofence
  const DEBOUNCE_MS = 3000; // ở trong vùng >= 3 giây mới tính là đã tới (tránh GPS nhảy)
  const COOLDOWN_MS = 5 * 60 * 1000; // 1 điểm đã phát thì 5 phút sau mới tự phát lại
  const CHECK_EVERY_MS = 3000;
  const DEFAULT_CENTER = [16.1003, 108.2777];
  const SPEECH_LANG = {
    vi: "vi-VN", en: "en-US", zh: "zh-CN", ja: "ja-JP", ko: "ko-KR", fr: "fr-FR", de: "de-DE", es: "es-ES",
    ru: "ru-RU", th: "th-TH", it: "it-IT", pt: "pt-BR", id: "id-ID", ms: "ms-MY", hi: "hi-IN", ar: "ar-SA",
  };

  const $ = (sel) => document.querySelector(sel);
  const audio = $("#audio");

  let token = storage.get("visitor_token");
  let lang = storage.get("lang") || ((navigator.language || "vi").slice(0, 2) === "vi" ? "vi" : "en");
  let languages = [];
  let bundle = null;
  let position = null;
  let simulate = false;
  let autoplay = storage.get("autoplay", true);
  let enteredAt = {}; // poiId -> lúc bắt đầu vào vùng
  let lastPlayed = {}; // poiId -> lúc phát gần nhất
  let currentPoi = null;
  let playEventSent = false;
  let pendingTranslations = 0;
  let pollId = 0;
  let map = null;
  let poiLayer = null;
  let userMarker = null;
  let routeLine = null;
  let gpsStatus = null; // { key, accuracy } - lưu lại để đổi ngôn ngữ thì vẽ lại được
  let insights = null; // trạng thái mở cửa + đông khách của điểm đang mở (lấy từ server, đổi theo giờ)
  let popularDay = null; // ngày đang xem trong biểu đồ đông khách

  function tr(key) {
    return t(lang, key);
  }

  // Thanh thông báo dưới tab. ms = 0 thì không tự ẩn
  function showMsg(text, ms = 4000) {
    const bar = $("#msg-bar");
    bar.textContent = text;
    bar.classList.remove("hidden");
    clearTimeout(showMsg.timer);
    if (ms > 0) showMsg.timer = setTimeout(() => bar.classList.add("hidden"), ms);
  }

  function distance(lat1, lng1, lat2, lng2) {
    const R = 6371000, rad = Math.PI / 180;
    const dLat = (lat2 - lat1) * rad, dLng = (lng2 - lng1) * rad;
    const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLng / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(a));
  }

  function langName(code) {
    const l = languages.find((x) => x.code === code);
    return l ? l.native_name : code;
  }

  function sendEvent(poiId, type) {
    if (!token) return;
    apiRequest("/events", { method: "POST", token, body: { poi_id: poiId, type, lang } }).catch(() => {});
  }

  // ===== Mua vé / nhập mã =====
  async function loadAccessInfo() {
    try {
      const { data } = await apiRequest("/access/info");
      $("#price").textContent = data.price_vnd.toLocaleString("vi-VN") + " đ";
      $("#hours").textContent = data.access_hours;
      return data;
    } catch (e) {
      return null;
    }
  }

  function showGate(message) {
    $("#app").classList.add("hidden");
    $("#gate").classList.remove("hidden");
    $("#gate-msg").textContent = message || "";
  }

  async function redeem(code, attempt = 1) {
    $("#gate-msg").textContent = tr("processing");
    try {
      const { data } = await apiRequest("/access/token", { method: "POST", body: { code } });
      token = data.access_token;
      storage.set("visitor_token", token);
      history.replaceState(null, "", "/");
      await startApp();
    } catch (err) {
      // thanh toán online: webhook có thể về chậm hơn -> thử lại vài lần
      if (err.code === "PAYMENT_PENDING" && attempt < 6) {
        $("#gate-msg").textContent = tr("paymentPending");
        setTimeout(() => redeem(code, attempt + 1), 2000);
        return;
      }
      $("#gate-msg").textContent = err.message;
    }
  }

  $("#redeem-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const code = $("#code-input").value.trim().toUpperCase();
    if (code.length >= 4) redeem(code);
  });

  $("#btn-pay-online").addEventListener("click", async () => {
    try {
      const { data } = await apiRequest("/access/online", { method: "POST" });
      location.href = data.payment_url;
    } catch (err) {
      $("#gate-msg").textContent = err.message;
    }
  });

  function logout(message) {
    token = null;
    storage.remove("visitor_token");
    stopAudio();
    showGate(message);
  }

  // ===== Tải dữ liệu: tải hết 1 lần, lần sau gửi ETag, không đổi thì server trả 304 =====
  async function loadBundle() {
    const cacheKey = "bundle_" + lang;
    const cached = storage.get(cacheKey);
    const headers = cached && cached.etag ? { "If-None-Match": cached.etag } : {};
    try {
      const res = await apiRequest("/content/bundle?lang=" + lang, { token, headers });
      pendingTranslations = Number(res.headers.get("X-Translation-Pending") || 0);
      if (res.notModified && cached) {
        bundle = cached.data;
      } else {
        bundle = res.data;
        storage.set(cacheKey, { etag: res.headers.get("ETag"), data: res.data });
      }
    } catch (err) {
      if (err.status === 401) {
        logout(tr("expired"));
        throw err;
      }
      if (!cached) throw err;
      bundle = cached.data; // mất mạng thì dùng bản đã lưu
      showMsg("Offline");
    }
    languages = bundle.languages;
    renderAll();
    refreshPanel();
  }

  // Panel đang mở mà bản dịch vừa có -> cập nhật lại chữ (không cắt audio đang phát)
  function refreshPanel() {
    if (!currentPoi || $("#poi-panel").classList.contains("hidden")) return;
    const fresh = bundle.pois.find((p) => p.id === currentPoi.id);
    if (!fresh || !audio.paused) return;
    const changed = fresh.served_lang !== currentPoi.served_lang || fresh.tips !== currentPoi.tips ||
      JSON.stringify(fresh.opening_hours) !== JSON.stringify(currentPoi.opening_hours);
    if (changed) openPoi(fresh, { silent: true, keepInsights: true });
  }

  // Server đang dịch ở nền -> 4 giây tải lại 1 lần cho tới khi xong (tối đa 2 phút)
  async function waitForTranslations() {
    const myId = ++pollId;
    if (!pendingTranslations) return;
    showMsg(tr("translating"), 0);
    for (let i = 0; i < 30 && pendingTranslations > 0; i++) {
      await new Promise((r) => setTimeout(r, 4000));
      if (myId !== pollId) return; // đã đổi ngôn ngữ khác
      try {
        await loadBundle();
      } catch (e) {
        return;
      }
    }
    if (myId !== pollId) return;
    if (pendingTranslations) showMsg(tr("fallbackNote") + " English / Tiếng Việt");
    else showMsg(tr("translated"));
  }

  // ===== Bản đồ =====
  function initMap() {
    if (map) return;
    map = L.map("map").setView(DEFAULT_CENTER, 18);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 20, maxNativeZoom: 19, attribution: "© OpenStreetMap",
    }).addTo(map);
    poiLayer = L.layerGroup().addTo(map);
    map.on("click", (e) => {
      if (simulate) updatePosition(e.latlng.lat, e.latlng.lng, "sim");
    });
  }

  function renderMarkers() {
    poiLayer.clearLayers();
    const bounds = [];
    bundle.pois.forEach((poi, i) => {
      const ll = [poi.latitude, poi.longitude];
      bounds.push(ll);
      L.circle(ll, { radius: poi.trigger_radius_m, color: "#8b3a0e", weight: 1, fillOpacity: 0.1 }).addTo(poiLayer);
      const icon = L.divIcon({ className: "poi-num", html: String(i + 1), iconSize: [20, 20] });
      L.marker(ll, { icon, title: poi.name }).on("click", () => openPoi(poi)).addTo(poiLayer);
    });
    if (bounds.length && !position) map.fitBounds(bounds, { padding: [30, 30], maxZoom: 18 });
  }

  // ===== GPS + geofence =====
  function startGps() {
    if (!navigator.geolocation) {
      setGpsStatus("gpsDenied");
      return;
    }
    setGpsStatus("locating");
    navigator.geolocation.watchPosition(
      (pos) => {
        if (!simulate) updatePosition(pos.coords.latitude, pos.coords.longitude, "gps", pos.coords.accuracy);
      },
      () => {
        if (!position) setGpsStatus("gpsDenied");
      },
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 }
    );
    setInterval(checkGeofence, CHECK_EVERY_MS);
  }

  function updatePosition(lat, lng, source, accuracy) {
    position = { lat, lng };
    if (!userMarker) {
      userMarker = L.circleMarker([lat, lng], { radius: 7, color: "#fff", weight: 2, fillColor: "#1565c0", fillOpacity: 1 }).addTo(map);
    } else {
      userMarker.setLatLng([lat, lng]);
    }
    if (source === "sim") setGpsStatus("simulateOn");
    else setGpsStatus(accuracy ? "gpsAccuracy" : null, accuracy);
    checkGeofence();
    renderList();
  }

  function setGpsStatus(key, accuracy) {
    gpsStatus = key ? { key, accuracy } : null;
    renderGpsStatus();
  }

  function renderGpsStatus() {
    let text = "";
    if (gpsStatus) {
      text = tr(gpsStatus.key);
      if (gpsStatus.key === "gpsAccuracy") text += " " + Math.round(gpsStatus.accuracy) + " " + tr("meters");
    }
    $("#gps-status").textContent = text;
  }

  function checkGeofence() {
    if (!position || !bundle) return;
    const now = Date.now();
    const inside = [];
    for (const poi of bundle.pois) {
      const d = distance(position.lat, position.lng, poi.latitude, poi.longitude);
      if (d <= poi.trigger_radius_m) {
        if (!enteredAt[poi.id]) enteredAt[poi.id] = now;
        inside.push({ poi, d });
      } else {
        delete enteredAt[poi.id];
      }
    }
    // nhiều vùng chồng nhau: lấy điểm ưu tiên cao hơn, bằng nhau thì lấy điểm gần hơn
    inside.sort((a, b) => b.poi.priority - a.poi.priority || a.d - b.d);
    for (const { poi } of inside) {
      const stayedLongEnough = simulate || now - enteredAt[poi.id] >= DEBOUNCE_MS;
      const notRecent = !lastPlayed[poi.id] || now - lastPlayed[poi.id] > COOLDOWN_MS;
      if (stayedLongEnough && notRecent && audio.paused) {
        lastPlayed[poi.id] = now;
        sendEvent(poi.id, "geofence_enter");
        showMsg(tr("near") + ": " + poi.name);
        openPoi(poi, { autoplay });
        break;
      }
    }
  }

  $("#btn-locate").addEventListener("click", () => {
    if (position) map.setView([position.lat, position.lng], 19);
    else showMsg(tr("locating"));
  });

  $("#chk-simulate").addEventListener("change", (e) => {
    simulate = e.target.checked;
    if (simulate) showMsg(tr("simulateOn"));
  });

  $("#chk-autoplay").addEventListener("change", (e) => {
    autoplay = e.target.checked;
    storage.set("autoplay", autoplay);
  });

  // ===== Panel thông tin 1 điểm =====
  function openPoi(poi, opts = {}) {
    currentPoi = poi;
    playEventSent = false;
    stopAudio();
    $("#poi-title").textContent = poi.name;
    $("#poi-desc").textContent = poi.description;
    if (!opts.keepInsights || !insights || insights.poi_id !== poi.id) {
      insights = null;
      popularDay = null;
      loadInsights(poi.id);
    }
    renderDetails(poi);

    const note = $("#poi-note");
    if (poi.is_fallback) {
      note.textContent = tr("fallbackNote") + " " + langName(poi.served_lang);
      note.classList.remove("hidden");
    } else {
      note.classList.add("hidden");
    }

    const actions = $("#poi-actions");
    actions.innerHTML = "";
    if (poi.is_fallback || !poi.audio_url) {
      const btn = document.createElement("button");
      btn.className = "btn btn-sm";
      btn.textContent = tr("makeAudio");
      btn.onclick = () => translateNow(poi, btn);
      actions.appendChild(btn);
    }
    const speakBtn = document.createElement("button");
    speakBtn.className = "btn btn-sm";
    speakBtn.textContent = tr("speak");
    speakBtn.onclick = () => speak(poi);
    actions.appendChild(speakBtn);

    if (poi.audio_url) {
      audio.src = poi.audio_url;
      audio.classList.remove("hidden");
    } else {
      audio.removeAttribute("src");
      audio.classList.add("hidden");
    }
    $("#poi-panel").classList.remove("hidden");
    if (!opts.silent) sendEvent(poi.id, "view");
    if (opts.autoplay) {
      if (poi.audio_url) audio.play().catch(() => {});
      else speak(poi);
    }
  }

  // ===== Thông tin chi tiết (giống thẻ địa điểm trên Google Maps) =====
  // Tên thứ trong tuần theo ngôn ngữ đang chọn: dùng Intl của trình duyệt, khỏi dịch tay 16 ngôn ngữ.
  // 2026-10-05 là Thứ Hai -> day 0 giống backend.
  function dayName(day) {
    try {
      return new Intl.DateTimeFormat(lang, { weekday: "long" }).format(new Date(2026, 9, 5 + day));
    } catch (_) {
      return String(day + 1);
    }
  }

  function money(vnd) {
    if (!vnd) return tr("free");
    try {
      return new Intl.NumberFormat(lang, { style: "currency", currency: "VND", maximumFractionDigits: 0 }).format(vnd);
    } catch (_) {
      return vnd + " VND";
    }
  }

  // Các khung giờ của 1 ngày, vd ["06:00–11:30", "13:30–21:00"]; rỗng = đóng cả ngày
  function periodsOf(poi, day) {
    return poi.opening_hours.filter((p) => p.day === day).map((p) => p.open + "–" + p.close);
  }

  function periodsText(poi, day) {
    const list = periodsOf(poi, day);
    return list.length ? list.join(", ") : tr("closedAllDay");
  }

  async function loadInsights(poiId) {
    try {
      const { data } = await apiRequest("/pois/" + poiId + "/insights", { token });
      if (!currentPoi || currentPoi.id !== poiId) return; // khách đã mở điểm khác
      insights = data;
      if (popularDay === null) popularDay = data.today;
      renderDetails(currentPoi);
    } catch (_) {
      /* mất mạng -> vẫn hiện giờ mở cửa từ bundle, chỉ thiếu trạng thái + đông khách */
    }
  }

  // Dòng dưới tiêu đề: "Điện thờ · Đang mở cửa · Đóng cửa lúc 11:30"
  function statusHtml() {
    if (!insights) return "";
    const s = insights.open_status;
    if (s.state === "unknown") return "";
    const open = s.state === "open" || s.state === "closing_soon";
    const label = {
      open: "statusOpen", closing_soon: "statusClosingSoon", closed: "statusClosed", opening_soon: "statusOpeningSoon",
    }[s.state];
    let more = "";
    if (open) more = tr("closesAt") + " " + s.closes_at;
    else {
      const when = s.opens_in_days === 0 ? "" : s.opens_in_days === 1 ? tr("tomorrow") + " " : dayName(s.opens_day) + " ";
      more = tr("opensAt") + " " + when + s.opens_at;
    }
    const cls = s.state === "open" ? "st-open" : open || s.state === "opening_soon" ? "st-warn" : "st-closed";
    return '<b class="' + cls + '">' + escapeHtml(tr(label)) + "</b> · " + escapeHtml(more);
  }

  function popularHtml() {
    if (!insights) return "";
    const pt = insights.popular_times;
    if (!pt.by_day) return '<span class="small">' + escapeHtml(tr("notEnoughData")) + "</span>";
    let html = '<select id="popular-day">';
    for (let d = 0; d < 7; d++) {
      html += '<option value="' + d + '"' + (d === popularDay ? " selected" : "") + ">" +
        escapeHtml(d === insights.today ? tr("today") : dayName(d)) + "</option>";
    }
    html += "</select>";
    if (insights.busy_now !== null && popularDay === insights.today) {
      const level = insights.busy_now >= 70 ? "busyHigh" : insights.busy_now >= 35 ? "busyMedium" : "busyLow";
      html += ' <span class="small">' + escapeHtml(tr("busyNow") + ": " + tr(level)) + "</span>";
    }
    // Cột theo giờ 5h - 22h; cột giờ hiện tại tô đậm
    const nowHour = parseInt(insights.now_local.slice(11, 13), 10);
    html += '<div class="bars">';
    for (let h = 5; h <= 22; h++) {
      const v = pt.by_day[popularDay][h];
      const now = popularDay === insights.today && h === nowHour ? " now" : "";
      html += '<div class="bar' + now + '" title="' + h + "h: " + v + '%"><i style="height:' + Math.max(v, 2) + '%"></i>' +
        "<span>" + (h % 3 === 0 ? h : "") + "</span></div>";
    }
    return html + "</div>";
  }

  function renderDetails(poi) {
    const meta = [tr("cat_" + poi.category)];
    const status = statusHtml();
    $("#poi-meta").innerHTML = meta.map(escapeHtml).join("") + (status ? " · " + status : "");

    const rows = [];
    // Giờ mở cửa: hiện hôm nay, bấm "Xem cả tuần" để mở cả 7 ngày
    if (poi.opening_hours.length) {
      const today = insights ? insights.today : (new Date().getDay() + 6) % 7;
      let week = "";
      for (let d = 0; d < 7; d++) {
        const list = periodsOf(poi, d);
        week += "<tr" + (d === today ? ' class="today"' : "") + "><td>" + escapeHtml(dayName(d)) + "</td><td>" +
          (list.length ? list.map(escapeHtml).join("<br>") : escapeHtml(tr("closedAllDay"))) + "</td></tr>";
      }
      rows.push([tr("hoursLabel"), escapeHtml(tr("today") + ": " + periodsText(poi, today)) +
        "<details><summary>" + escapeHtml(tr("showWeek")) + '</summary><table class="week">' + week + "</table></details>"]);
    } else {
      rows.push([tr("hoursLabel"), escapeHtml(tr("hoursUnknown"))]);
    }
    rows.push([tr("feeLabel"), escapeHtml(money(poi.entry_fee_vnd))]);
    if (poi.visit_minutes) rows.push([tr("visitLabel"), escapeHtml(tr("about") + " " + poi.visit_minutes + " " + tr("minutes"))]);
    if (poi.amenities.length) {
      rows.push([tr("amenitiesLabel"), "<ul class=\"amen\">" +
        poi.amenities.map((a) => "<li>" + escapeHtml(tr("amenity_" + a)) + "</li>").join("") + "</ul>"]);
    }
    if (poi.tips) {
      const note = poi.tips_lang && poi.tips_lang !== lang ? ' <span class="small">(' + escapeHtml(langName(poi.tips_lang)) + ")</span>" : "";
      rows.push([tr("tipsLabel"), escapeHtml(poi.tips) + note]);
    }
    rows.push([tr("popularLabel"), popularHtml() || '<span class="small">...</span>']);

    const maps = "https://www.google.com/maps/dir/?api=1&travelmode=walking&destination=" + poi.latitude + "," + poi.longitude;
    $("#poi-details").innerHTML = "<h4>" + escapeHtml(tr("detailsTitle")) + '</h4><table class="details">' +
      rows.map(([k, v]) => "<tr><th>" + escapeHtml(k) + "</th><td>" + v + "</td></tr>").join("") + "</table>" +
      '<p><a href="' + maps + '" target="_blank" rel="noopener">' + escapeHtml(tr("directions")) + "</a></p>";

    const sel = $("#popular-day");
    if (sel) sel.onchange = (e) => { popularDay = Number(e.target.value); renderDetails(currentPoi); };
  }

  // Trạng thái mở cửa đổi theo giờ -> panel đang mở thì 1 phút hỏi lại server 1 lần
  setInterval(() => {
    if (currentPoi && !$("#poi-panel").classList.contains("hidden")) loadInsights(currentPoi.id);
  }, 60000);

  // Bấm "Dịch và tạo audio": server dịch ngay điểm này rồi trả về
  async function translateNow(poi, btn) {
    btn.disabled = true;
    btn.textContent = tr("processing");
    try {
      const { data } = await apiRequest("/pois/" + poi.id + "/localizations/" + lang + "/ensure", { method: "POST", token });
      const idx = bundle.pois.findIndex((p) => p.id === poi.id);
      if (idx >= 0) bundle.pois[idx] = data;
      storage.remove("bundle_" + lang);
      openPoi(data, { autoplay: true });
    } catch (err) {
      showMsg(err.message);
      btn.disabled = false;
      btn.textContent = tr("makeAudio");
    }
  }

  function speak(poi) {
    if (!window.speechSynthesis) return;
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(poi.name + ". " + poi.description);
    u.lang = SPEECH_LANG[poi.served_lang] || poi.served_lang;
    speechSynthesis.speak(u);
  }

  function stopAudio() {
    audio.pause();
    if (window.speechSynthesis) speechSynthesis.cancel();
  }

  audio.addEventListener("play", () => {
    if (currentPoi && !playEventSent) {
      playEventSent = true;
      sendEvent(currentPoi.id, "audio_play");
    }
  });

  $("#poi-close").addEventListener("click", () => {
    stopAudio();
    $("#poi-panel").classList.add("hidden");
  });

  // ===== Danh sách điểm =====
  function renderList() {
    if (!bundle) return;
    let items = bundle.pois.map((p, i) => ({
      p, i, d: position ? distance(position.lat, position.lng, p.latitude, p.longitude) : null,
    }));
    if (position) items.sort((a, b) => a.d - b.d);
    $("#poi-list").innerHTML = items.map(({ p, i, d }) => {
      let info = [];
      if (d !== null) info.push(Math.round(d) + " " + tr("meters"));
      info.push(p.audio_url ? tr("hasAudio") : tr("noAudio"));
      if (p.is_fallback) info.push(langName(p.served_lang));
      return '<li data-id="' + p.id + '">' + (i + 1) + ". <b>" + escapeHtml(p.name) + "</b>" +
        '<br><span class="small">' + escapeHtml(info.join(" - ")) + "</span></li>";
    }).join("");
    document.querySelectorAll("#poi-list li").forEach((li) => {
      li.onclick = () => openPoi(bundle.pois.find((p) => p.id === li.dataset.id));
    });
  }

  // ===== Lộ trình =====
  function renderTours() {
    let html = '<option value="">' + escapeHtml(tr("autoPick")) + "</option>";
    for (const tour of bundle.tours) {
      html += '<option value="' + tour.id + '">' + escapeHtml(tour.name) + " (" + tour.estimated_minutes + " " + tr("minutes") + ")</option>";
    }
    $("#tour-select").innerHTML = html;
  }

  $("#btn-recommend").addEventListener("click", async () => {
    // chưa có GPS thì lấy điểm đầu tiên (cổng chùa) làm điểm xuất phát
    const first = bundle.pois[0];
    const start = position || { lat: first ? first.latitude : DEFAULT_CENTER[0], lng: first ? first.longitude : DEFAULT_CENTER[1] };
    try {
      const { data } = await apiRequest("/tours/recommend", {
        method: "POST",
        token,
        body: { latitude: start.lat, longitude: start.lng, lang, tour_id: $("#tour-select").value || null },
      });
      $("#route-summary").textContent = tr("total") + ": " + Math.round(data.total_distance_m) + " " + tr("meters") +
        ", ~" + Math.round(data.total_minutes) + " " + tr("minutes");
      $("#route-list").innerHTML = data.stops.map((s) =>
        '<li data-id="' + s.poi.id + '"><b>' + escapeHtml(s.poi.name) + "</b><br>" +
        '<span class="small">' + tr("walk") + " " + Math.round(s.walk_distance_m) + " " + tr("meters") +
        " (" + s.walk_minutes + " " + tr("minutes") + "), " + tr("listen") + " " + s.listen_minutes + " " + tr("minutes") + "</span></li>"
      ).join("");
      document.querySelectorAll("#route-list li").forEach((li) => {
        li.onclick = () => openPoi(bundle.pois.find((p) => p.id === li.dataset.id));
      });
      if (routeLine) routeLine.remove();
      const pts = [[start.lat, start.lng]].concat(data.stops.map((s) => [s.poi.latitude, s.poi.longitude]));
      routeLine = L.polyline(pts, { color: "#1565c0", weight: 3 }).addTo(map);
    } catch (err) {
      showMsg(err.message);
    }
  });

  // ===== Hỏi đáp =====
  function addChatLine(who, html) {
    const p = document.createElement("p");
    p.innerHTML = "<b>" + escapeHtml(who) + ":</b> " + html;
    $("#chat-log").appendChild(p);
    $("#chat-log").scrollTop = 99999;
    return p;
  }

  $("#chat-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = $("#chat-input").value.trim();
    if (q.length < 2) return;
    $("#chat-input").value = "";
    addChatLine(tr("you"), escapeHtml(q));
    const line = addChatLine(tr("guide"), "...");
    try {
      const { data } = await apiRequest("/chat", { method: "POST", token, body: { question: q, lang } });
      let html = "<b>" + escapeHtml(tr("guide")) + ":</b> " + escapeHtml(data.answer);
      if (data.sources.length) {
        html += '<br><span class="small">' + tr("sources") + ": " + data.sources.map((s) => escapeHtml(s.title)).join(", ") + "</span>";
      }
      line.innerHTML = html;
    } catch (err) {
      line.innerHTML = "<b>" + escapeHtml(tr("guide")) + ':</b> <span class="msg">' + escapeHtml(err.message) + "</span>";
    }
  });

  // ===== Ngôn ngữ =====
  function fillLanguageSelects() {
    const html = languages.map((l) => '<option value="' + l.code + '">' + escapeHtml(l.native_name) + "</option>").join("");
    document.querySelectorAll(".lang-select").forEach((sel) => {
      sel.innerHTML = html;
      sel.value = lang;
    });
  }

  document.querySelectorAll(".lang-select").forEach((sel) => {
    sel.addEventListener("change", () => changeLang(sel.value));
  });

  async function changeLang(code) {
    if (code === lang) return;
    lang = code;
    storage.set("lang", code);
    document.querySelectorAll(".lang-select").forEach((sel) => (sel.value = code));
    stopAudio();
    $("#poi-panel").classList.add("hidden");
    $("#route-summary").textContent = "";
    $("#route-list").innerHTML = "";
    applyLanguage();
    const inApp = token && !$("#app").classList.contains("hidden");
    if (inApp) showMsg(tr("processing"), 0);
    await loadUiStrings(code); // nhãn giao diện, ngôn ngữ mới thì server dịch lần đầu
    if (lang !== code) return;
    applyLanguage();
    if (inApp) {
      await loadBundle(); // server tự xếp hàng dịch những điểm còn thiếu
      waitForTranslations();
      if (!pendingTranslations) showMsg(tr("translated"));
    }
  }

  function applyLanguage() {
    applyI18n(lang);
    $("#chat-input").placeholder = tr("chatPlaceholder");
    $("#code-input").placeholder = "AB3K9Q";
    renderGpsStatus();
    if (bundle) {
      renderList();
      renderTours();
    }
  }

  // ===== Tab =====
  document.querySelectorAll(".tabs button").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b === btn));
      document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === "view-" + btn.dataset.view));
      if (btn.dataset.view === "map") setTimeout(() => map.invalidateSize(), 50);
    });
  });

  function renderAll() {
    fillLanguageSelects();
    renderMarkers();
    renderList();
    renderTours();
  }

  async function startApp() {
    $("#gate").classList.add("hidden");
    $("#app").classList.remove("hidden");
    initMap();
    setTimeout(() => map.invalidateSize(), 50);
    try {
      await loadBundle();
    } catch (err) {
      if (err.status !== 401) showMsg(err.message);
      return;
    }
    waitForTranslations();
    if (!$("#chat-log").children.length) addChatLine(tr("guide"), escapeHtml(tr("chatHello")));
    if (!startApp.gpsStarted) {
      startApp.gpsStarted = true;
      startGps();
    }
  }

  async function init() {
    $("#chk-autoplay").checked = autoplay;
    applyLanguage();
    loadUiStrings(lang).then(applyLanguage);
    try {
      languages = (await apiRequest("/languages")).data;
    } catch (e) {
      languages = [{ code: "vi", native_name: "Tiếng Việt" }, { code: "en", native_name: "English" }];
    }
    fillLanguageSelects();
    const info = await loadAccessInfo();
    const params = new URLSearchParams(location.search);
    if (params.get("payment") === "success" && params.get("code")) {
      showGate();
      $("#code-input").value = params.get("code");
      return redeem(params.get("code"));
    }
    if (params.get("payment") === "failed") {
      history.replaceState(null, "", "/");
      return showGate(tr("paymentFailed"));
    }
    if (token || (info && !info.access_required)) return startApp();
    showGate();
  }

  init();
})();
