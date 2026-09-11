const VHC_DEFAULTS = {
  modeEntity: "select.vitodens_betriebsart",
  sparEntity: "switch.vitodens_sparbetrieb_dauerhaft",
  partyEntity: "switch.vitodens_partybetrieb_dauerhaft",
  wwActiveEntity: "binary_sensor.vitodens_ww_erzeugung_aktiv",
  hk1WindowEntity: "binary_sensor.vitodens_hk1_zeitfenster_aktiv",
  boilerTempEntity: "sensor.vitodens_kesseltemperatur",
  outsideTempEntity: "sensor.vitodens_aussentemperatur",
  storeTempEntity: "sensor.vitodens_speichertemperatur",
  slopeEntity: "number.vitodens_hk1_heizkurve_neigung",
  levelEntity: "number.vitodens_hk1_heizkurve_niveau",
  temperatures: [
    ["Reduziert", "number.vitodens_hk1_reduzierte_temperatur_soll", "mdi:weather-night"],
    ["Normal", "number.vitodens_hk1_normaltemperatur_soll", "mdi:white-balance-sunny"],
    ["Komfort", "number.vitodens_hk1_komforttemperatur_soll", "mdi:sofa"],
    ["Warmwasser", "number.vitodens_ww_temperatur_soll", "mdi:waves"],
  ],
};

class VitodensHeatingControlCard extends HTMLElement {
  setConfig(config) {
    this.config = { title: "HK1 Regler", ...VHC_DEFAULTS, ...config };
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  getCardSize() {
    return 6;
  }

  state(entity) {
    return this._hass?.states?.[entity]?.state ?? "unknown";
  }

  attr(entity, key, fallback = undefined) {
    return this._hass?.states?.[entity]?.attributes?.[key] ?? fallback;
  }

  temp(entity) {
    const value = this.state(entity);
    if (value === "unknown" || value === "unavailable") return "-";
    const unit = this.attr(entity, "unit_of_measurement", "");
    return `${value}${unit}`;
  }

  async setMode(option) {
    const current = this.state(this.config.modeEntity);
    if (option === current) return;
    const ok = window.confirm(`Betriebsart auf "${option}" setzen?`);
    if (!ok) return;
    await this._hass.callService("select", "select_option", {
      entity_id: this.config.modeEntity,
      option,
    });
  }

  async toggleSwitch(entity) {
    const on = this.state(entity) === "on";
    await this._hass.callService("switch", on ? "turn_off" : "turn_on", { entity_id: entity });
  }

  async bump(entity, delta) {
    const current = Number(this.state(entity));
    if (!Number.isFinite(current)) return;
    const min = Number(this.attr(entity, "min", -100));
    const max = Number(this.attr(entity, "max", 100));
    const next = Math.max(min, Math.min(max, current + delta));
    await this._hass.callService("number", "set_value", { entity_id: entity, value: next });
  }

  modeButtons() {
    const current = this.state(this.config.modeEntity);
    const modes = this.attr(this.config.modeEntity, "options", ["Aus", "Nur Warmwasser", "Heizen und Warmwasser"]);
    const iconMap = {
      "Aus": "mdi:power",
      "Nur Warmwasser": "mdi:water-boiler",
      "Heizen und Warmwasser": "mdi:radiator",
    };
    return modes.map((mode) => `
      <button class="mode ${mode === current ? "active" : ""}" data-mode="${mode}">
        <ha-icon icon="${iconMap[mode] || "mdi:tune"}"></ha-icon>
        <span>${mode}</span>
      </button>
    `).join("");
  }

  statusChip(label, entity, icon) {
    const on = this.state(entity) === "on";
    return `
      <button class="chip ${on ? "on" : ""}" data-switch="${entity}">
        <ha-icon icon="${icon}"></ha-icon>
        <span>${label}</span>
        <b>${on ? "An" : "Aus"}</b>
      </button>
    `;
  }

  readOnlyChip(label, entity, icon) {
    const on = this.state(entity) === "on";
    return `
      <div class="chip readonly ${on ? "on" : ""}">
        <ha-icon icon="${icon}"></ha-icon>
        <span>${label}</span>
        <b>${on ? "Aktiv" : "Aus"}</b>
      </div>
    `;
  }

  temperatureRows() {
    return this.config.temperatures.map(([label, entity, icon]) => `
      <div class="temp-row">
        <div class="temp-name">
          <ha-icon icon="${icon}"></ha-icon>
          <span>${label}</span>
        </div>
        <button class="round" data-bump="${entity}" data-delta="-1" aria-label="${label} senken">
          <ha-icon icon="mdi:minus"></ha-icon>
        </button>
        <strong>${this.temp(entity)}</strong>
        <button class="round" data-bump="${entity}" data-delta="1" aria-label="${label} erhöhen">
          <ha-icon icon="mdi:plus"></ha-icon>
        </button>
      </div>
    `).join("");
  }

  curveControl() {
    const slope = Number(this.state(this.config.slopeEntity));
    const level = Number(this.state(this.config.levelEntity));
    const valid = Number.isFinite(slope) && Number.isFinite(level);
    const outside = [20, 10, 0, -10, -20, -30];
    const reference = [25, 38, 48, 58, 68, 80];
    const values = valid
      ? reference.map((value) => Math.round(20 + level + (value - 22) * slope / 1.1))
      : reference.map(() => null);
    const points = values.map((value, index) => {
      const x = 9 + index * 16.4;
      const y = value === null ? 72 : Math.max(9, Math.min(80, 86 - value * 0.88));
      return { x, y, value };
    });
    const polyline = points.map(({ x, y }) => `${x},${y}`).join(" ");
    const area = `9,86 ${polyline} ${points.at(-1).x},86`;
    const nodes = points.map(({ x, y, value }) => `
      <span class="chart-node" style="left:${x}%;top:${y / 92 * 100}%">
        ${value === null ? "-" : `${value}°`}
      </span>
    `).join("");
    const xLabels = outside.map((value, index) => `<span style="left:${9 + index * 16.4}%">${value > 0 ? "+" : ""}${value}°</span>`).join("");

    return `
      <section class="curve-panel">
        <div class="curve-title">Aussentemperatur</div>
        <div class="chart-wrap">
          <div class="y-title">Vorlauftemperatur</div>
          <svg class="chart" viewBox="0 0 100 92" preserveAspectRatio="none" aria-label="Heizkennlinie">
            ${points.map(({ x }) => `<line x1="${x}" y1="5" x2="${x}" y2="86"></line>`).join("")}
            <polygon points="${area}"></polygon>
            <polyline points="${polyline}"></polyline>
          </svg>
          <div class="chart-nodes">${nodes}</div>
          <div class="x-labels">${xLabels}</div>
        </div>
        <div class="curve-heading">Werte festlegen</div>
        ${this.curveRow("Neigung", this.config.slopeEntity, 0.1, 1)}
        ${this.curveRow("Niveau", this.config.levelEntity, 1, 1)}
      </section>
    `;
  }

  curveRow(label, entity, step, decimals) {
    const value = Number(this.state(entity));
    const display = Number.isFinite(value) ? value.toFixed(decimals) : "-";
    return `
      <div class="curve-control-row">
        <strong>${label}</strong>
        <button class="curve-button" data-bump="${entity}" data-delta="-${step}" aria-label="${label} senken"><ha-icon icon="mdi:minus"></ha-icon></button>
        <b>${display}</b>
        <button class="curve-button" data-bump="${entity}" data-delta="${step}" aria-label="${label} erhöhen"><ha-icon icon="mdi:plus"></ha-icon></button>
      </div>
    `;
  }

  render() {
    if (!this.shadowRoot) return;
    const curveOnly = this.config.variant === "curve";
    const title = curveOnly ? "Heizkennlinie" : this.config.title;
    const body = curveOnly ? `
          ${this.curveControl()}
          <div class="temps">${this.temperatureRows()}</div>
    ` : `
          <div class="mode-grid">${this.modeButtons()}</div>
          <div class="chips">
            ${this.statusChip("Sparbetrieb", this.config.sparEntity, "mdi:weather-night")}
            ${this.statusChip("Partybetrieb", this.config.partyEntity, "mdi:white-balance-sunny")}
            ${this.readOnlyChip("HK1 Zeitfenster", this.config.hk1WindowEntity, "mdi:calendar-check")}
            ${this.readOnlyChip("WW Erzeugung", this.config.wwActiveEntity, "mdi:water-sync")}
          </div>
          <div class="live">
            <div class="metric"><span>Aussen</span><b>${this.temp(this.config.outsideTempEntity)}</b></div>
            <div class="metric"><span>Kessel</span><b>${this.temp(this.config.boilerTempEntity)}</b></div>
            <div class="metric"><span>Speicher</span><b>${this.temp(this.config.storeTempEntity)}</b></div>
          </div>
    `;
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          --vhc-orange: #ff8b38;
          --vhc-blue: #18a8ee;
          --vhc-green: #1fbf93;
          --vhc-border: rgba(127, 127, 127, 0.26);
          --vhc-soft: rgba(127, 127, 127, 0.12);
        }
        ha-card { overflow: hidden; }
        .wrap { padding: 16px; display: grid; gap: 16px; }
        .head {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
        }
        h2 {
          margin: 0;
          display: flex;
          align-items: center;
          gap: 10px;
          font-size: 18px;
          line-height: 1.2;
        }
        .mode-grid {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 8px;
        }
        button {
          font: inherit;
          color: inherit;
        }
        .mode {
          min-height: 76px;
          display: grid;
          place-items: center;
          gap: 5px;
          padding: 10px 6px;
          border: 1px solid var(--vhc-border);
          border-radius: 8px;
          background: var(--card-background-color);
          cursor: pointer;
          text-align: center;
        }
        .mode ha-icon { --mdc-icon-size: 24px; color: var(--secondary-text-color); }
        .mode span {
          max-width: 100%;
          font-size: 13px;
          line-height: 1.2;
          overflow-wrap: anywhere;
        }
        .mode.active {
          border-color: var(--vhc-orange);
          background: color-mix(in srgb, var(--vhc-orange) 18%, var(--card-background-color));
        }
        .mode.active ha-icon { color: var(--vhc-orange); }
        .chips {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 8px;
        }
        .chip {
          min-height: 48px;
          display: grid;
          grid-template-columns: 24px 1fr auto;
          align-items: center;
          gap: 8px;
          padding: 9px 10px;
          border: 1px solid var(--vhc-border);
          border-radius: 8px;
          background: var(--card-background-color);
          cursor: pointer;
          text-align: left;
        }
        .chip.readonly { cursor: default; }
        .chip ha-icon { color: var(--secondary-text-color); }
        .chip span { min-width: 0; overflow: hidden; text-overflow: ellipsis; }
        .chip b { font-size: 12px; color: var(--secondary-text-color); }
        .chip.on { border-color: var(--vhc-green); }
        .chip.on ha-icon, .chip.on b { color: var(--vhc-green); }
        .live {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 8px;
        }
        .metric {
          min-width: 0;
          padding: 10px;
          border-radius: 8px;
          background: var(--vhc-soft);
        }
        .metric span {
          display: block;
          color: var(--secondary-text-color);
          font-size: 12px;
          margin-bottom: 4px;
        }
        .metric b {
          font-size: 16px;
          font-variant-numeric: tabular-nums;
        }
        .curve-panel { border-top: 1px solid var(--vhc-border); }
        .curve-title { padding: 15px 0 8px; text-align: center; text-transform: uppercase; color: var(--secondary-text-color); font-size: 14px; }
        .chart-wrap { position: relative; height: 290px; padding: 0 0 28px 38px; }
        .chart { width: 100%; height: 100%; overflow: visible; }
        .chart line { stroke: var(--vhc-border); stroke-width: .35; stroke-dasharray: 2.4 2.4; }
        .chart polygon { fill: color-mix(in srgb, var(--vhc-orange) 11%, transparent); }
        .chart polyline { fill: none; stroke: #cf331c; stroke-width: 1.1; vector-effect: non-scaling-stroke; }
        .chart-nodes { position: absolute; left: 38px; right: 0; top: 0; bottom: 28px; pointer-events: none; }
        .chart-node { position: absolute; width: 46px; height: 46px; display: grid; place-items: center; transform: translate(-50%, -50%); box-sizing: border-box; border: 2px solid #cf331c; border-radius: 50%; background: var(--card-background-color); color: var(--primary-text-color); font-size: 15px; font-weight: 600; font-variant-numeric: tabular-nums; }
        .y-title { position: absolute; left: 0; top: 50%; transform: translate(-43%, -50%) rotate(-90deg); text-transform: uppercase; color: var(--secondary-text-color); font-size: 12px; white-space: nowrap; }
        .x-labels { position: absolute; left: 38px; right: 0; bottom: 5px; height: 22px; color: var(--secondary-text-color); font-size: 12px; }
        .x-labels span { position: absolute; transform: translateX(-50%); white-space: nowrap; }
        .curve-heading { margin: 0 -16px; padding: 10px 16px; text-transform: uppercase; color: var(--secondary-text-color); background: var(--vhc-soft); font-size: 13px; }
        .curve-control-row { display: grid; grid-template-columns: minmax(100px, 1fr) 42px 58px 42px; align-items: center; gap: 8px; min-height: 62px; border-bottom: 1px solid var(--vhc-border); }
        .curve-control-row > strong { font-size: 18px; }
        .curve-control-row > b { text-align: center; font-size: 20px; font-variant-numeric: tabular-nums; }
        .curve-button { width: 38px; height: 38px; display: grid; place-items: center; border: 0; border-radius: 50%; color: white; background: #292929; cursor: pointer; }
        .curve-button ha-icon { --mdc-icon-size: 24px; }
        .temps { display: grid; gap: 8px; }
        .temp-row {
          display: grid;
          grid-template-columns: minmax(120px, 1fr) 38px 64px 38px;
          align-items: center;
          gap: 8px;
          min-height: 44px;
        }
        .temp-name {
          min-width: 0;
          display: flex;
          align-items: center;
          gap: 8px;
          color: var(--primary-text-color);
        }
        .temp-name span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .temp-name ha-icon { color: var(--secondary-text-color); }
        .round {
          width: 38px;
          height: 38px;
          display: inline-grid;
          place-items: center;
          border: 1px solid var(--vhc-border);
          border-radius: 50%;
          background: var(--card-background-color);
          cursor: pointer;
        }
        .round:hover, .mode:hover, .chip:not(.readonly):hover { background: var(--vhc-soft); }
        .temp-row strong {
          text-align: center;
          font-size: 16px;
          font-variant-numeric: tabular-nums;
        }
        @media (max-width: 520px) {
          .wrap { padding: 14px 12px; gap: 14px; }
          .mode-grid { grid-template-columns: 1fr; }
          .chips, .live { grid-template-columns: 1fr; }
          .chart-wrap { height: 235px; padding-left: 32px; }
          .chart-nodes { left: 32px; }
          .chart-node { width: 40px; height: 40px; font-size: 13px; }
          .x-labels { left: 32px; font-size: 10px; }
          .curve-heading { margin-left: -12px; margin-right: -12px; padding-left: 12px; }
          .temp-row { grid-template-columns: minmax(88px, 1fr) 36px 58px 36px; gap: 6px; }
          .round { width: 36px; height: 36px; }
        }
      </style>
      <ha-card>
        <div class="wrap">
          <div class="head">
            <h2><ha-icon icon="${curveOnly ? "mdi:chart-bell-curve-cumulative" : "mdi:home-thermometer"}"></ha-icon>${title}</h2>
          </div>
          ${body}
        </div>
      </ha-card>
    `;

    this.shadowRoot.querySelectorAll("[data-mode]").forEach((button) => {
      button.addEventListener("click", () => this.setMode(button.dataset.mode));
    });
    this.shadowRoot.querySelectorAll("[data-switch]").forEach((button) => {
      button.addEventListener("click", () => this.toggleSwitch(button.dataset.switch));
    });
    this.shadowRoot.querySelectorAll("[data-bump]").forEach((button) => {
      button.addEventListener("click", () => this.bump(button.dataset.bump, Number(button.dataset.delta)));
    });
  }
}

if (!customElements.get("vitodens-heating-control-card")) {
  customElements.define("vitodens-heating-control-card", VitodensHeatingControlCard);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: "vitodens-heating-control-card",
  name: "Vitodens Heating Control",
  description: "Local Vitodens heating mode and temperature control.",
});
