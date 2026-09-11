const DAYS = [
  ["montag", "Montag"],
  ["dienstag", "Dienstag"],
  ["mittwoch", "Mittwoch"],
  ["donnerstag", "Donnerstag"],
  ["freitag", "Freitag"],
  ["samstag", "Samstag"],
  ["sonntag", "Sonntag"],
];

const PROGRAMS = [
  {
    key: "hk1",
    title: "Heizkreis 1",
    icon: "mdi:radiator",
    baseLabel: "Reduziert",
    activeLabel: "Normal",
    baseIcon: "mdi:weather-night",
    activeIcon: "mdi:white-balance-sunny",
    inactiveClass: "reduced",
    activeClass: "normal",
    entityPrefix: "sensor.vitodens_hk1_zeitprogramm_",
  },
  {
    key: "ww",
    title: "Warmwasser",
    icon: "mdi:water-boiler",
    baseLabel: "Aus",
    activeLabel: "Warmwasser",
    baseIcon: "mdi:minus",
    activeIcon: "mdi:waves",
    inactiveClass: "off",
    activeClass: "water",
    entityPrefix: "sensor.vitodens_ww_zeitprogramm_",
  },
  {
    key: "zirkulation",
    title: "Zirkulation",
    icon: "mdi:sync",
    baseLabel: "Aus",
    activeLabel: "Zirkulation",
    baseIcon: "mdi:minus",
    activeIcon: "mdi:sync",
    inactiveClass: "off",
    activeClass: "circulation",
    entityPrefix: "sensor.vitodens_zirkulation_zeitprogramm_",
  },
];

const PROFILES = ["Schaukelstuhl", "Werktag"];

class VitodensScheduleBarsCard extends HTMLElement {
  setConfig(config) {
    this.config = {
      title: "Zeitprogramme",
      editorPath: "/vitodens-lokal/zeitplan-editor",
      profileMatrixEntity: "sensor.vitodens_zeitprogramm_profile_matrix",
      directProfileTopic: "vitodens/action/zeitprogramm_editor/profil_anwenden_direkt",
      discardAllTopic: "vitodens/action/zeitprogramm_editor/alle_entwuerfe_verwerfen",
      draftCountEntity: "sensor.vitodens_zeitprogramm_editor_anzahl_entwuerfe",
      writeSelectionEntity: "button.vitodens_zeitprogramm_editor_auswahl_uebernehmen",
      writeAllEntity: "button.vitodens_zeitprogramm_editor_alle_entwuerfe_uebernehmen",
      programs: ["hk1", "ww", "zirkulation"],
      ...config,
    };
    this.attachShadow({ mode: "open" });
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  getCardSize() {
    return 8;
  }

  esc(value) {
    return String(value ?? "").replace(/[&<>"]/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
    }[char]));
  }

  fire(type, detail = {}) {
    this.dispatchEvent(new CustomEvent(type, { detail, bubbles: true, composed: true }));
  }

  navigate(path) {
    history.pushState(null, "", path);
    this.fire("location-changed", { replace: false });
  }

  selectedPrograms() {
    const wanted = Array.isArray(this.config.programs) ? this.config.programs : ["hk1", "ww", "zirkulation"];
    return PROGRAMS.filter((program) => wanted.includes(program.key));
  }

  todayIndex() {
    return (new Date().getDay() + 6) % 7;
  }

  dayLabel(dayKey) {
    return DAYS.find(([key]) => key === dayKey)?.[1] || dayKey;
  }

  entityId(program, dayKey) {
    return this.config.entities?.[program.key]?.[dayKey] || `${program.entityPrefix}${dayKey}`;
  }

  matrixProgram(programKey) {
    const entity = this.config.profileMatrixEntity;
    return this._hass?.states?.[entity]?.attributes?.programs?.[programKey] || null;
  }

  dayInfo(programKey, dayKey) {
    return this.matrixProgram(programKey)?.days?.[dayKey] || null;
  }

  profileSchedule(programKey, profileLabel) {
    return this.matrixProgram(programKey)?.profiles?.[profileLabel] || "";
  }

  draftCount() {
    const value = Number(this._hass?.states?.[this.config.draftCountEntity]?.state || 0);
    return Number.isFinite(value) ? value : 0;
  }

  minutes(value) {
    if (!value || value === "na" || value === "unknown" || value === "unavailable") return null;
    const match = String(value).match(/^(\d{1,2}):(\d{2})$/);
    if (!match) return null;
    return Math.min(1440, Math.max(0, Number(match[1])) * 60 + Math.max(0, Number(match[2])));
  }

  ranges(raw) {
    if (!raw || raw === "unknown" || raw === "unavailable") return [];
    return String(raw).split(",").map((part) => {
      const [start, end] = part.trim().split("-");
      const startMinute = this.minutes(start);
      const endMinute = this.minutes(end);
      return startMinute !== null && endMinute !== null && endMinute > startMinute
        ? { start: startMinute, end: endMinute }
        : null;
    }).filter(Boolean);
  }

  segments(ranges) {
    const points = [...new Set([0, 1440, ...ranges.flatMap((range) => [range.start, range.end])])]
      .sort((a, b) => a - b);
    return points.slice(0, -1).map((start, index) => {
      const end = points[index + 1];
      return {
        start,
        end,
        active: ranges.some((range) => start >= range.start && end <= range.end),
      };
    }).filter((segment) => segment.end > segment.start);
  }

  time(minutes) {
    return `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;
  }

  rangeText(ranges) {
    return ranges.length ? ranges.map((range) => `${this.time(range.start)}-${this.time(range.end)}`).join(", ") : "Kein aktives Fenster";
  }

  segment(program, item) {
    const width = ((item.end - item.start) / 1440) * 100;
    return `
      <span class="segment ${item.active ? program.activeClass : program.inactiveClass}" style="width:${width}%">
        ${width >= 8 ? `<ha-icon icon="${item.active ? program.activeIcon : program.baseIcon}"></ha-icon>` : ""}
      </span>
    `;
  }

  profileActions(program, dayKey, currentProfile) {
    return `
      <div class="profile-actions">
        ${PROFILES.map((profile) => {
          const saved = this.profileSchedule(program.key, profile);
          const active = currentProfile === profile;
          const busy = this._busyKey === `${program.key}:${dayKey}:${profile}`;
          const disabled = !saved || busy;
          return `
            <button class="profile-action ${active ? "active" : ""}"
              data-program="${program.key}" data-day="${dayKey}" data-profile="${this.esc(profile)}"
              title="${saved ? `${this.esc(profile)} fuer ${this.esc(this.dayLabel(dayKey))} vormerken` : `${this.esc(profile)} ist fuer ${this.esc(program.title)} noch nicht gespeichert`}" 
              ${disabled ? "disabled" : ""}>
              <ha-icon icon="${active ? "mdi:check-circle" : "mdi:bookmark-outline"}"></ha-icon>
              <span>${busy ? "Setze..." : this.esc(profile)}</span>
            </button>
          `;
        }).join("")}
      </div>
    `;
  }

  scale() {
    return `
      <div class="scale-labels"><span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span></div>
      <div class="ticks">${Array.from({ length: 25 }, (_, index) => `<i class="${index % 6 === 0 ? "major" : ""}"></i>`).join("")}</div>
    `;
  }

  day(program, dayKey, dayName, index) {
    const info = this.dayInfo(program.key, dayKey);
    const entity = this.entityId(program, dayKey);
    const raw = info?.effective || this._hass?.states?.[entity]?.state;
    const ranges = this.ranges(raw);
    const title = index === this.todayIndex() ? `${dayName} (Heute)` : dayName;
    const profile = info?.profile || "Profil unbekannt";
    const neutral = ["Individuell", "Keine Daten", "Profil unbekannt"].includes(profile);
    return `
      <div class="day" title="${this.esc(title)}: ${this.esc(this.rangeText(ranges))}">
        <div class="day-head">
          <div class="day-title">
            <span>${this.esc(title)}</span>
            <span class="profile-pill ${neutral ? "neutral" : "known"}">
              <ha-icon icon="mdi:bookmark-box"></ha-icon>
              ${info?.draft ? "Vorgemerkt: " : ""}${this.esc(profile)}
            </span>
          </div>
          <button class="day-more" data-entity="${entity}" title="${this.esc(title)} Details" aria-label="${this.esc(title)} Details">
            <ha-icon icon="mdi:chevron-right"></ha-icon>
          </button>
        </div>
        ${this.scale()}
        <div class="bar" aria-label="${this.esc(title)}: ${this.esc(this.rangeText(ranges))}">
          ${this.segments(ranges).map((item) => this.segment(program, item)).join("")}
        </div>
        ${this.profileActions(program, dayKey, profile)}
      </div>
    `;
  }

  program(program) {
    return `
      <section class="program ${program.key}">
        <div class="program-title"><ha-icon icon="${program.icon}"></ha-icon><span>${program.title}</span></div>
        <div class="legend">
          <span><i class="${program.inactiveClass}"></i>${program.baseLabel}</span>
          <span><i class="${program.activeClass}"></i>${program.activeLabel}</span>
        </div>
        ${DAYS.map(([dayKey, dayName], index) => this.day(program, dayKey, dayName, index)).join("")}
      </section>
    `;
  }

  async applyProfile(programKey, dayKey, profile) {
    if (!this._hass) return;
    this._busyKey = `${programKey}:${dayKey}:${profile}`;
    this._lastError = "";
    this.render();
    try {
      await this._hass.callService("mqtt", "publish", {
        topic: this.config.directProfileTopic,
        payload: JSON.stringify({ program: programKey, day: dayKey, profile }),
      });
    } catch (error) {
      this._lastError = error?.message || String(error);
    } finally {
      this._busyKey = "";
      this.render();
    }
  }

  async discardAll() {
    if (!this.draftCount() || !window.confirm("Alle vorgemerkten Profilzuweisungen loeschen?")) return;
    await this._hass.callService("mqtt", "publish", { topic: this.config.discardAllTopic, payload: "discard" });
  }

  async writeDrafts(mode) {
    const count = this.draftCount();
    if (!count) return;
    const all = mode === "all";
    const message = all
      ? `${count} vorgemerkte Zeitprogramme wirklich in die Heizung schreiben?`
      : "Die aktuell ausgewaehlte Vormerkung wirklich in die Heizung schreiben?";
    if (!window.confirm(message)) return;
    await this._hass.callService("button", "press", {
      entity_id: all ? this.config.writeAllEntity : this.config.writeSelectionEntity,
    });
  }

  render() {
    if (!this.shadowRoot) return;
    const draftCount = this.draftCount();
    this.shadowRoot.innerHTML = `
      <style>
        :host{display:block;--vito-blue:#18a8ee;--vito-orange:#ff8b38;--vito-green:#1fbf93;--vito-track:rgba(127,127,127,.18);--vito-line:rgba(127,127,127,.28);--vito-muted:var(--secondary-text-color)}
        ha-card{overflow:hidden}
        .head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px 16px 10px}
        h2{display:flex;align-items:center;gap:10px;margin:0;font-size:18px;font-weight:650;line-height:1.2}
        .edit,.day-more{display:inline-grid;place-items:center;color:var(--primary-text-color);background:transparent;border:0;border-radius:50%;cursor:pointer}
        .edit{width:40px;height:40px}.day-more{flex:0 0 auto;width:32px;height:32px;color:var(--secondary-text-color)}
        .edit:hover,.day-more:hover{background:rgba(127,127,127,.12)}
        .program{border-top:1px solid var(--divider-color);padding:12px 16px 16px}
        .program-title{display:flex;align-items:center;gap:9px;font-size:15px;font-weight:650;margin-bottom:8px}
        .legend{display:flex;gap:14px;flex-wrap:wrap;color:var(--vito-muted);font-size:12px;margin-bottom:8px}
        .legend span{display:inline-flex;align-items:center;gap:6px}.legend i{width:4px;height:18px;border-radius:2px;display:inline-block}
        .day{width:100%;padding:10px 0 12px;border-top:1px solid rgba(127,127,127,.16);text-align:left}.day:first-of-type{border-top:0}
        .day-head{display:flex;align-items:center;justify-content:space-between;gap:10px;font-size:15px;font-weight:560;margin-bottom:8px}
        .day-title{min-width:0;display:flex;align-items:center;gap:9px;flex-wrap:wrap}
        .profile-pill{display:inline-flex;align-items:center;gap:4px;min-height:24px;padding:2px 8px;border-radius:999px;font-size:12px;font-weight:650;line-height:1.2;background:rgba(127,127,127,.12)}
        .profile-pill ha-icon{--mdc-icon-size:15px}.profile-pill.known{background:color-mix(in srgb,var(--vito-green) 17%,transparent);color:color-mix(in srgb,var(--vito-green) 82%,var(--primary-text-color))}.profile-pill.neutral{color:var(--vito-muted)}
        .scale-labels{display:grid;grid-template-columns:repeat(5,1fr);color:var(--vito-muted);font-size:12px;margin-bottom:3px}
        .scale-labels span:nth-child(1){text-align:left}.scale-labels span:nth-child(2),.scale-labels span:nth-child(3),.scale-labels span:nth-child(4){text-align:center}.scale-labels span:nth-child(5){text-align:right}
        .ticks{display:grid;grid-template-columns:repeat(25,1fr);align-items:end;height:9px;margin-bottom:4px}.ticks i{justify-self:start;width:1px;height:4px;background:var(--vito-line)}.ticks i.major{height:8px;background:var(--vito-muted)}
        .bar{display:flex;height:32px;overflow:hidden;border:1px solid var(--vito-line);border-radius:3px;background:var(--vito-track)}
        .segment{display:inline-grid;place-items:center;min-width:0;height:100%}.segment ha-icon{--mdc-icon-size:18px;color:white;opacity:.96}
        .reduced{background:var(--vito-blue)}.normal,.water{background:var(--vito-orange)}.circulation{background:var(--vito-green)}.off{background:var(--vito-track)}
        .profile-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}.profile-action{min-height:34px;display:inline-flex;align-items:center;justify-content:center;gap:6px;padding:6px 10px;color:var(--primary-text-color);background:rgba(127,127,127,.10);border:1px solid rgba(127,127,127,.24);border-radius:8px;font:inherit;font-size:13px;font-weight:650;cursor:pointer}.profile-action ha-icon{--mdc-icon-size:17px}.profile-action:hover:not(:disabled){background:rgba(127,127,127,.16)}.profile-action.active{border-color:color-mix(in srgb,var(--vito-green) 65%,transparent);background:color-mix(in srgb,var(--vito-green) 16%,transparent)}.profile-action:disabled{cursor:default;opacity:.42}
        .commit{display:grid;gap:9px;margin:0 16px 16px;padding:12px;border:1px solid color-mix(in srgb,var(--vito-orange) 55%,var(--vito-line));border-radius:8px;background:color-mix(in srgb,var(--vito-orange) 8%,var(--card-background-color))}.commit-head{display:flex;align-items:center;gap:8px;font-weight:700}.commit-note{font-size:13px;color:var(--vito-muted)}.commit-actions{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.commit button{min-height:42px;display:flex;align-items:center;justify-content:center;gap:7px;padding:7px;border:1px solid var(--vito-line);border-radius:8px;background:var(--card-background-color);color:var(--primary-text-color);font:inherit;font-weight:650;cursor:pointer}.commit button.primary{border-color:var(--vito-orange);background:color-mix(in srgb,var(--vito-orange) 15%,var(--card-background-color))}.commit button:disabled{opacity:.42;cursor:not-allowed}
        .error{margin:0 16px 12px;padding:9px 10px;border-radius:8px;color:var(--error-color);background:color-mix(in srgb,var(--error-color) 12%,transparent);font-size:13px}
        @media(max-width:520px){.head{padding:14px 12px 8px}.program{padding:12px 12px 15px}.scale-labels{font-size:11px}.bar{height:30px}.profile-action{flex:1 1 132px}.commit{margin:0 12px 14px}.commit-actions{grid-template-columns:1fr}}
      </style>
      <ha-card>
        <div class="head">
          <h2><ha-icon icon="mdi:chart-timeline-variant"></ha-icon>${this.esc(this.config.title)}</h2>
          <button class="edit" title="Zeitplan-Editor oeffnen" aria-label="Zeitplan-Editor oeffnen"><ha-icon icon="mdi:calendar-edit"></ha-icon></button>
        </div>
        ${this._lastError ? `<div class="error">${this.esc(this._lastError)}</div>` : ""}
        ${this.selectedPrograms().map((program) => this.program(program)).join("")}
        <div class="commit">
          <div class="commit-head"><ha-icon icon="mdi:database-arrow-up"></ha-icon>Vorgemerkte Zeiten</div>
          <div class="commit-note">${draftCount ? `${draftCount} vorgemerkt. Erst „Schreiben“ uebertraegt Zeiten an die Heizung.` : "Keine vorgemerkten Aenderungen."}</div>
          <div class="commit-actions">
            <button data-commit="discard" ${draftCount ? "" : "disabled"}><ha-icon icon="mdi:delete-outline"></ha-icon>Vormerkungen loeschen</button>
            <button data-commit="selection" ${draftCount ? "" : "disabled"}><ha-icon icon="mdi:calendar-arrow-right"></ha-icon>Auswahl schreiben</button>
            <button class="primary" data-commit="all" ${draftCount ? "" : "disabled"}><ha-icon icon="mdi:calendar-sync"></ha-icon>Alle schreiben</button>
          </div>
        </div>
      </ha-card>
    `;

    this.shadowRoot.querySelector(".edit")?.addEventListener("click", () => this.navigate(this.config.editorPath));
    this.shadowRoot.querySelectorAll(".day-more").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        this.fire("hass-more-info", { entityId: button.dataset.entity });
      });
    });
    this.shadowRoot.querySelectorAll(".profile-action").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        this.applyProfile(button.dataset.program, button.dataset.day, button.dataset.profile);
      });
    });
    this.shadowRoot.querySelectorAll("[data-commit]").forEach((button) => {
      button.addEventListener("click", () => button.dataset.commit === "discard" ? this.discardAll() : this.writeDrafts(button.dataset.commit));
    });
  }
}

if (!customElements.get("vitodens-schedule-bars-card")) {
  customElements.define("vitodens-schedule-bars-card", VitodensScheduleBarsCard);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: "vitodens-schedule-bars-card",
  name: "Vitodens Schedule Bars",
  description: "Shows Vitodens local schedules as day bars with safe profile drafts.",
});
