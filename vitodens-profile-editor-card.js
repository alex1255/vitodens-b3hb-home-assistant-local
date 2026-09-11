const VPE_DAYS = [
  ["montag", "Montag", "Mo"],
  ["dienstag", "Dienstag", "Di"],
  ["mittwoch", "Mittwoch", "Mi"],
  ["donnerstag", "Donnerstag", "Do"],
  ["freitag", "Freitag", "Fr"],
  ["samstag", "Samstag", "Sa"],
  ["sonntag", "Sonntag", "So"],
];

const VPE_PROGRAMS = [
  { key: "hk1", label: "Heizkreis 1", icon: "mdi:radiator", active: "Normal", base: "Reduziert", color: "heat" },
  { key: "ww", label: "Warmwasser", icon: "mdi:water-boiler", active: "Warmwasser", base: "Aus", color: "water" },
  { key: "zirkulation", label: "Zirkulation", icon: "mdi:sync", active: "Zirkulation", base: "Aus", color: "circle" },
];

const VPE_PROFILE_LABELS = ["Schaukelstuhl", "Werktag"];
const VPE_SLOT_LABELS = ["Fenster 1", "Fenster 2", "Fenster 3", "Fenster 4"];

const VPE_DEFAULTS = {
  title: "Profile bearbeiten",
  overviewPath: "/vitodens-lokal/zeitprogramme",
  matrixEntity: "sensor.vitodens_zeitprogramm_profile_matrix",
  statusEntity: "sensor.vitodens_zeitprogramm_editor_status",
  programEntity: "select.vitodens_zeitprogramm_editor_programm",
  profileEntity: "select.vitodens_zeitprogramm_editor_profil",
  slotEntity: "select.vitodens_zeitprogramm_editor_profil_fenster",
  activeEntity: "switch.vitodens_zeitprogramm_editor_profil_fenster_aktiv",
  startHourEntity: "number.vitodens_zeitprogramm_editor_profil_start_stunde",
  startMinuteEntity: "number.vitodens_zeitprogramm_editor_profil_start_minute",
  endHourEntity: "number.vitodens_zeitprogramm_editor_profil_ende_stunde",
  endMinuteEntity: "number.vitodens_zeitprogramm_editor_profil_ende_minute",
  profilePlanEntity: "sensor.vitodens_zeitprogramm_editor_profil_plan",
};

class VitodensProfileEditorCard extends HTMLElement {
  setConfig(config) {
    this.config = { ...VPE_DEFAULTS, ...config };
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  getCardSize() {
    return 7;
  }

  state(entity, fallback = "unknown") {
    return this._hass?.states?.[entity]?.state ?? fallback;
  }

  attr(entity, key, fallback = undefined) {
    return this._hass?.states?.[entity]?.attributes?.[key] ?? fallback;
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

  programKey() {
    const current = this.state(this.config.programEntity, "Heizkreis 1");
    return VPE_PROGRAMS.find((program) => program.label === current)?.key || "hk1";
  }

  program() {
    return VPE_PROGRAMS.find((program) => program.key === this.programKey()) || VPE_PROGRAMS[0];
  }

  profile() {
    const current = this.state(this.config.profileEntity, "Schaukelstuhl");
    return VPE_PROFILE_LABELS.includes(current) ? current : "Schaukelstuhl";
  }

  profileSchedule(programKey, profileLabel) {
    return this.attr(this.config.matrixEntity, "programs", {})?.[programKey]?.profiles?.[profileLabel] || "";
  }

  currentSchedule() {
    const plan = this.state(this.config.profilePlanEntity, "");
    if (plan && plan !== "unknown" && plan !== "unavailable" && plan !== "Nicht gespeichert") return plan;
    return this.profileSchedule(this.programKey(), this.profile());
  }

  minutes(value) {
    if (!value || value === "na") return null;
    const match = String(value).match(/^(\d{1,2}):(\d{2})$/);
    if (!match) return null;
    return Math.min(1440, Math.max(0, Number(match[1]) * 60 + Number(match[2])));
  }

  time(value) {
    return `${String(Math.floor(value / 60)).padStart(2, "0")}:${String(value % 60).padStart(2, "0")}`;
  }

  ranges(schedule) {
    return String(schedule || "").split(",").map((part, index) => {
      const [start, end] = part.trim().split("-");
      const startMinute = this.minutes(start);
      const endMinute = this.minutes(end);
      return startMinute !== null && endMinute !== null && endMinute > startMinute
        ? { index, start: startMinute, end: endMinute }
        : { index, start: null, end: null };
    }).slice(0, 4);
  }

  activeRanges(schedule) {
    return this.ranges(schedule).filter((range) => range.start !== null && range.end !== null);
  }

  slotIndex() {
    const slot = this.state(this.config.slotEntity, "Fenster 1");
    return Math.max(0, VPE_SLOT_LABELS.indexOf(slot));
  }

  statusText() {
    const status = this.state(this.config.statusEntity, "");
    return status.startsWith("Profil ") && status.includes(" gespeichert:")
      ? status
      : "Aenderungen an den Profilfenstern werden automatisch gespeichert.";
  }

  async selectOption(entity, option) {
    if (this.state(entity) === option) return;
    await this._hass.callService("select", "select_option", { entity_id: entity, option });
  }

  async chooseProgram(label) {
    await this.selectOption(this.config.programEntity, label);
  }

  async chooseProfile(label) {
    await this.selectOption(this.config.profileEntity, label);
  }

  async chooseSlot(label) {
    await this.selectOption(this.config.slotEntity, label);
  }

  async setActive(on) {
    await this._hass.callService("switch", on ? "turn_on" : "turn_off", { entity_id: this.config.activeEntity });
  }

  numberValue(entity) {
    const value = Number(this.state(entity));
    return Number.isFinite(value) ? value : 0;
  }

  async setNumber(entity, value) {
    const min = Number(this.attr(entity, "min", 0));
    const max = Number(this.attr(entity, "max", 100));
    const step = Number(this.attr(entity, "step", 1));
    const next = Math.max(min, Math.min(max, Math.round(value / step) * step));
    await this._hass.callService("number", "set_value", { entity_id: entity, value: next });
  }

  async bump(entity, delta) {
    await this.setNumber(entity, this.numberValue(entity) + delta);
    if (entity === this.config.endHourEntity && this.numberValue(entity) + delta >= 24) {
      await this.setNumber(this.config.endMinuteEntity, 0);
    }
  }


  programButtons() {
    const current = this.programKey();
    return VPE_PROGRAMS.map((program) => `
      <button class="program ${program.color} ${program.key === current ? "active" : ""}" data-program-label="${this.esc(program.label)}">
        <ha-icon icon="${program.icon}"></ha-icon>
        <span>${this.esc(program.label)}</span>
      </button>
    `).join("");
  }

  profileCards() {
    const currentProgram = this.programKey();
    const currentProfile = this.profile();
    return VPE_PROFILE_LABELS.map((profile) => {
      const schedule = profile === currentProfile ? this.currentSchedule() : this.profileSchedule(currentProgram, profile);
      const ranges = this.activeRanges(schedule);
      const empty = !schedule;
      return `
        <button class="profile ${profile === currentProfile ? "active" : ""}" data-profile="${this.esc(profile)}">
          <span class="profile-top">
            <ha-icon icon="${profile === "Schaukelstuhl" ? "mdi:sofa" : "mdi:briefcase"}"></ha-icon>
            <b>${this.esc(profile)}</b>
          </span>
          <span class="mini-bar ${empty ? "empty" : ""}">${this.timeline(schedule, this.program(), false)}</span>
          <small>${empty ? "Noch leer" : ranges.map((range) => `${this.time(range.start)}-${this.time(range.end)}`).join(" / ")}</small>
        </button>
      `;
    }).join("");
  }

  timeline(schedule, program, markSelected = true) {
    const ranges = this.activeRanges(schedule);
    const selected = this.slotIndex();
    if (!ranges.length) return `<span class="fill muted"></span>`;
    const points = [...new Set([0, 1440, ...ranges.flatMap((range) => [range.start, range.end])])].sort((a, b) => a - b);
    return points.slice(0, -1).map((start, index) => {
      const end = points[index + 1];
      const active = ranges.find((range) => start >= range.start && end <= range.end);
      const width = ((end - start) / 1440) * 100;
      const selectedClass = markSelected && active?.index === selected ? "selected" : "";
      return `<span class="fill ${active ? program.color : "muted"} ${selectedClass}" style="width:${width}%"></span>`;
    }).join("");
  }

  slotButtons() {
    const current = this.slotIndex();
    const ranges = this.ranges(this.currentSchedule());
    return VPE_SLOT_LABELS.map((label, index) => {
      const range = ranges[index];
      const value = range?.start !== null ? `${this.time(range.start)}-${this.time(range.end)}` : "Aus";
      return `
        <button class="slot ${index === current ? "active" : ""}" data-slot="${this.esc(label)}">
          <span>${label.replace("Fenster ", "")}</span>
          <b>${value}</b>
        </button>
      `;
    }).join("");
  }

  stepper(label, entity, delta) {
    const value = this.numberValue(entity);
    return `
      <div class="stepper">
        <span class="step-label">${label}</span>
        <div class="step-actions">
          <button data-bump="${entity}" data-delta="${-delta}" aria-label="${label} kleiner"><ha-icon icon="mdi:minus"></ha-icon></button>
          <strong>${String(value).padStart(2, "0")}</strong>
          <button data-bump="${entity}" data-delta="${delta}" aria-label="${label} groesser"><ha-icon icon="mdi:plus"></ha-icon></button>
        </div>
      </div>
    `;
  }

  render() {
    if (!this.shadowRoot) return;
    const program = this.program();
    const schedule = this.currentSchedule();
    const active = this.state(this.config.activeEntity) === "on";
    this.shadowRoot.innerHTML = `
      <style>
        :host{display:block;--pe-blue:#2da8ec;--pe-orange:#ff9442;--pe-green:#18b889;--pe-red:#e35f5f;--pe-line:rgba(127,127,127,.24);--pe-soft:rgba(127,127,127,.11);--pe-muted:var(--secondary-text-color)}
        ha-card{overflow:hidden}.wrap{display:grid;gap:16px;padding:16px}button{font:inherit;color:inherit}.head{display:flex;align-items:center;justify-content:space-between;gap:12px}.head h2{display:flex;align-items:center;gap:10px;margin:0;font-size:19px;line-height:1.2}.nav{width:40px;height:40px;display:grid;place-items:center;border:0;border-radius:50%;background:transparent;cursor:pointer}.nav:hover{background:var(--pe-soft)}
        .programs,.profiles,.slots,.days,.quick{display:grid;gap:8px}.programs{grid-template-columns:repeat(3,minmax(0,1fr))}.profiles{grid-template-columns:repeat(2,minmax(0,1fr))}.slots{grid-template-columns:repeat(4,minmax(0,1fr))}.days{grid-template-columns:repeat(7,minmax(0,1fr))}.quick{grid-template-columns:repeat(3,minmax(0,1fr))}
        .program,.profile,.slot,.day,.apply,.toggle{border:1px solid var(--pe-line);border-radius:8px;background:var(--card-background-color);cursor:pointer}.program{min-height:68px;display:grid;place-items:center;gap:5px;padding:8px;text-align:center}.program ha-icon{--mdc-icon-size:24px;color:var(--pe-muted)}.program span{font-size:13px;line-height:1.15;overflow-wrap:anywhere}.program.active{background:color-mix(in srgb,var(--accent-color) 12%,var(--card-background-color));border-color:var(--accent-color)}.program.active ha-icon{color:var(--accent-color)}
        .profile{min-width:0;display:grid;gap:9px;padding:12px;text-align:left}.profile-top{display:flex;align-items:center;gap:8px}.profile-top ha-icon{color:var(--pe-muted)}.profile small{min-height:16px;color:var(--pe-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.profile.active{border-color:var(--pe-green);background:color-mix(in srgb,var(--pe-green) 12%,var(--card-background-color))}
        .bar,.mini-bar{display:flex;overflow:hidden;border-radius:4px;background:var(--pe-soft)}.bar{height:38px;border:1px solid var(--pe-line)}.mini-bar{height:20px}.fill{display:block;height:100%;min-width:0}.fill.heat{background:var(--pe-orange)}.fill.water{background:var(--pe-blue)}.fill.circle{background:var(--pe-green)}.fill.muted{background:var(--pe-soft)}.fill.selected{box-shadow:inset 0 0 0 2px white}
        .scale{display:grid;grid-template-columns:repeat(5,1fr);font-size:12px;color:var(--pe-muted);margin-bottom:4px}.scale span:nth-child(2),.scale span:nth-child(3),.scale span:nth-child(4){text-align:center}.scale span:last-child{text-align:right}
        .section{display:grid;gap:10px}.section-title{display:flex;align-items:center;gap:8px;font-size:14px;font-weight:700;color:var(--primary-text-color)}.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;color:var(--pe-muted)}.legend span{display:inline-flex;align-items:center;gap:6px}.dot{width:10px;height:10px;border-radius:50%;display:inline-block}.dot.heat{background:var(--pe-orange)}.dot.water{background:var(--pe-blue)}.dot.circle{background:var(--pe-green)}.dot.muted{background:var(--pe-soft)}
        .slot{min-height:56px;display:grid;gap:3px;place-items:center;padding:7px 4px}.slot span{font-size:12px;color:var(--pe-muted)}.slot b{font-size:12px;font-variant-numeric:tabular-nums;white-space:nowrap}.slot.active{border-color:var(--pe-orange);background:color-mix(in srgb,var(--pe-orange) 13%,var(--card-background-color))}
        .editor{display:grid;grid-template-columns:1fr;gap:10px;align-items:stretch}.time-grid{display:grid;grid-template-columns:repeat(2,minmax(250px,1fr));gap:8px}.toggle{min-height:58px;display:flex;align-items:center;justify-content:center;gap:10px;padding:10px}.toggle ha-icon{color:var(--pe-muted)}.toggle.on{border-color:var(--pe-green);background:color-mix(in srgb,var(--pe-green) 12%,var(--card-background-color))}.toggle.on ha-icon{color:var(--pe-green)}
        .stepper{display:grid;gap:7px;min-width:0;padding:9px 10px;border:1px solid var(--pe-line);border-radius:8px}.step-label{font-size:13px;color:var(--pe-muted);white-space:nowrap}.step-actions{display:grid;grid-template-columns:42px minmax(48px,1fr) 42px;align-items:center;gap:8px;min-width:0}.stepper strong{text-align:center;font-size:18px;font-variant-numeric:tabular-nums}.stepper button{width:42px;height:42px;display:grid;place-items:center;border:0;border-radius:50%;background:var(--pe-soft);cursor:pointer}.stepper button ha-icon{--mdc-icon-size:22px}
        .day{min-height:42px;font-weight:700}.day:hover,.apply:hover,.program:hover,.profile:hover,.slot:hover,.toggle:hover,.write:hover{background:var(--pe-soft)}.apply,.write{min-height:44px;display:flex;align-items:center;justify-content:center;gap:8px;padding:8px 10px;font-weight:700}.apply{border:1px solid var(--pe-line);border-radius:8px;background:var(--card-background-color);cursor:pointer}.apply.primary{border-color:var(--pe-green);background:color-mix(in srgb,var(--pe-green) 13%,var(--card-background-color))}.write-box{padding:12px;border:1px solid color-mix(in srgb,var(--pe-orange) 55%,var(--pe-line));border-radius:8px;background:color-mix(in srgb,var(--pe-orange) 8%,var(--card-background-color))}.write-note{font-size:13px;color:var(--pe-muted)}.write-actions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.write{border:1px solid var(--pe-orange);border-radius:8px;background:var(--card-background-color);cursor:pointer}.write.primary{background:color-mix(in srgb,var(--pe-orange) 16%,var(--card-background-color))}.write:disabled{opacity:.45;cursor:not-allowed}.status,.error{padding:10px 12px;border-radius:8px;font-size:13px}.status{background:var(--pe-soft);color:var(--pe-muted)}.error{background:color-mix(in srgb,var(--error-color) 12%,transparent);color:var(--error-color)}
        @media(max-width:740px){.programs{grid-template-columns:1fr}.time-grid{grid-template-columns:1fr}.quick,.write-actions{grid-template-columns:1fr}.slots{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:460px){.wrap{padding:12px}.profiles{grid-template-columns:1fr}.days{grid-template-columns:repeat(4,minmax(0,1fr))}}
      </style>
      <ha-card>
        <div class="wrap">
          <div class="head">
            <h2><ha-icon icon="mdi:bookmark-box-multiple"></ha-icon>${this.esc(this.config.title)}</h2>
            <button class="nav" data-nav="${this.esc(this.config.overviewPath)}" title="Zurueck zur Uebersicht"><ha-icon icon="mdi:chart-timeline-variant"></ha-icon></button>
          </div>
          <div class="programs">${this.programButtons()}</div>
          <div class="profiles">${this.profileCards()}</div>
          <div class="section">
            <div class="section-title"><ha-icon icon="${program.icon}"></ha-icon>${this.esc(program.label)} / ${this.esc(this.profile())}</div>
            <div class="legend"><span><i class="dot muted"></i>${this.esc(program.base)}</span><span><i class="dot ${program.color}"></i>${this.esc(program.active)}</span></div>
            <div class="scale"><span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span></div>
            <div class="bar">${this.timeline(schedule, program)}</div>
          </div>
          <div class="slots">${this.slotButtons()}</div>
          <div class="editor">
            <div class="time-grid">
              ${this.stepper("Start Stunde", this.config.startHourEntity, 1)}
              ${this.stepper("Start Minute", this.config.startMinuteEntity, 10)}
              ${this.stepper("Ende Stunde", this.config.endHourEntity, 1)}
              ${this.stepper("Ende Minute", this.config.endMinuteEntity, 10)}
            </div>
            <button class="toggle ${active ? "on" : ""}" data-active="${active ? "off" : "on"}">
              <ha-icon icon="${active ? "mdi:toggle-switch" : "mdi:toggle-switch-off"}"></ha-icon>
              <b>${active ? "Aktiv" : "Aus"}</b>
            </button>
          </div>
          ${this._error ? `<div class="error">${this.esc(this._error)}</div>` : ""}
          <div class="status">${this.esc(this.statusText())}</div>
        </div>
      </ha-card>
    `;

    this.shadowRoot.querySelector("[data-nav]")?.addEventListener("click", (event) => {
      this.navigate(event.currentTarget.dataset.nav);
    });
    this.shadowRoot.querySelectorAll("[data-program-label]").forEach((button) => {
      button.addEventListener("click", () => this.chooseProgram(button.dataset.programLabel));
    });
    this.shadowRoot.querySelectorAll("[data-profile]").forEach((button) => {
      button.addEventListener("click", () => this.chooseProfile(button.dataset.profile));
    });
    this.shadowRoot.querySelectorAll("[data-slot]").forEach((button) => {
      button.addEventListener("click", () => this.chooseSlot(button.dataset.slot));
    });
    this.shadowRoot.querySelector("[data-active]")?.addEventListener("click", (event) => {
      this.setActive(event.currentTarget.dataset.active === "on");
    });
    this.shadowRoot.querySelectorAll("[data-bump]").forEach((button) => {
      button.addEventListener("click", () => this.bump(button.dataset.bump, Number(button.dataset.delta)));
    });
  }
}

if (!customElements.get("vitodens-profile-editor-card")) {
  customElements.define("vitodens-profile-editor-card", VitodensProfileEditorCard);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: "vitodens-profile-editor-card",
  name: "Vitodens Profile Editor",
  description: "Profile-first schedule editor for the local Vitodens dashboard.",
});
