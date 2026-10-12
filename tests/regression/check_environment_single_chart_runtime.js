// Exercise the comparison renderer without network, DOM framework, or hardware.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const page = fs.readFileSync(path.join(__dirname, '../../templates/environment_history.html'), 'utf8');
const code = page.match(/<script>([\s\S]*?)<\/script>/g).at(-1)
    .replace(/^<script>|<\/script>$/g, '')
    .replace(/{{\s*tent_id\|tojson\s*}}/g, '"tent_2"')
    .replace(/{{\s*initial_metric\|tojson\s*}}/g, '"compare"');

const elements = new Map();
function node(tag = 'div') {
    return {
        tag, children: [], classList: {toggle() {}, add() {}, remove() {}},
        append(...children) { this.children.push(...children); },
        appendChild(child) { this.children.push(child); return child; },
        replaceChildren(...children) { this.children = children; },
        remove() {}, setAttribute() {}, addEventListener() {},
    };
}
const document = {
    getElementById(id) { if (!elements.has(id)) elements.set(id, node()); return elements.get(id); },
    querySelector() { return node(); }, querySelectorAll() { return []; },
    createElement: node, createTextNode: text => text, addEventListener() {}, hidden: false,
};
const calls = [];
class Chart {
    constructor(canvas, config) { this.canvas = canvas; this.config = config; this.data = config.data; this.options = config.options; calls.push(this); }
    destroy() { this.destroyed = true; }
    update() { this.updates = (this.updates || 0) + 1; }
}
const series = ['temp', 'water_temp', 'outside_temp', 'hum', 'outside_hum', 'vpd', 'ppfd'];
const rows = [
    {ts: 1000, temp: 26, water_temp: null, outside_temp: 21, hum: 60, outside_hum: 50, vpd: 1.2, ppfd: 400},
    {ts: 1100, temp: 25.8, water_temp: 22, outside_temp: 20, hum: 62, outside_hum: 52, vpd: 1.1, ppfd: 390},
];
const intervals = new Map();
let nextInterval = 1, stateRequests = 0;
const now = Date.now() / 1000;
const state = {snapshot_ts: now, last_loop_ts: now - 1, temp_ok: true, hum_ok: true,
    temp_age: 1, hum_age: 1, temp: 26.2, hum: 61, vpd: 1.15,
    water_temp: 22.1, water_temp_source: {last_seen: now - 1},
    outside_temp: 20.5, outside_temp_source: {last_seen: now - 1},
    outside_hum: 51, outside_hum_source: {last_seen: now - 1},
    light_ppfd: 420, light_ppfd_source: {last_seen: now - 1}};
const context = {
    document, Chart, console, Date, Set, Object, Number, String, JSON,
    localStorage: {getItem: () => JSON.stringify(series), setItem() {}},
    fetch: async url => {if (url.endsWith('/state')) stateRequests++;
        return {ok: true, json: async () => url === '/api/tents'
            ? {tents: [{id: 'tent_2', name: 'Zelt 2'}]} : url.endsWith('/state') ? state : rows};},
    setInterval(callback) {const id = nextInterval++; intervals.set(id, callback); return id;},
    clearInterval(id) {intervals.delete(id);}, setTimeout() {}, clearTimeout() {},
    history: {replaceState() {}}, window: {location: {href: ''}, addEventListener() {}},
};
const sandbox = vm.createContext(context);
vm.runInContext(code, sandbox);
setImmediate(async () => {
    if (calls.length !== 1) throw new Error(`Erwartet genau ein Diagramm, erhalten: ${calls.length}`);
    const chart = calls[0];
    const datasets = chart.config.data.datasets;
    if (datasets.length !== 7) throw new Error(`Erwartet sieben Kurven, erhalten: ${datasets.length}`);
    if (!datasets.slice(0, 3).every(item => item.yAxisID === 'y_temp'))
        throw new Error('Die drei Temperaturen teilen nicht dieselbe Achse');
    if (datasets[1].data[0].y !== null) throw new Error('Fehlender Wasserwert wurde aufgefüllt');
    if (chart.config.options.scales.y_vpd.display !== false ||
        chart.config.options.scales.y_temp.display !== true)
        throw new Error('Zusatzskalen verdrängen die Temperaturachse');
    if (elements.get('compare-views').children.filter(item => item.className === 'compare-canvas').length !== 1)
        throw new Error('Mehr als eine Zeichenfläche erzeugt');
    console.log('✅ Sieben Kurven auf genau einer großen Zeichenfläche, korrekte Achsen und Messlücken');
    if (stateRequests !== 0) throw new Error('Live startete ohne Benutzeraktion');
    const before = datasets[0].data.length;
    vm.runInContext('toggleLive()', sandbox);
    await new Promise(resolve => setImmediate(resolve));
    if (stateRequests !== 1 || datasets[0].data.length !== before + 1 ||
        datasets[1].data.at(-1).y !== 22.1 || !chart.updates)
        throw new Error('Live-Polling ergänzt die sieben Kurven nicht auf dem vorhandenen Canvas');
    const activeTick = [...intervals.values()].at(-1);
    vm.runInContext('toggleLive()', sandbox);
    await new Promise(resolve => setImmediate(resolve));
    activeTick();
    await new Promise(resolve => setImmediate(resolve));
    if (stateRequests !== 1) throw new Error('Ausgeschaltete Live-Aufzeichnung fragt weiterhin Daten ab');
    console.log('✅ Live ergänzt nur nach Aktivierung und stoppt die Abfrage wieder');
    const stale = vm.runInContext('liveSample({snapshot_ts: 2000, last_loop_ts: 1999, temp_ok: false, hum_ok: false, temp: 28, hum: 70, water_temp: 24, water_temp_source: {last_seen: 1800}})', sandbox);
    if (stale.temp !== null || stale.hum !== null || stale.water_temp !== null)
        throw new Error('Veraltete Werte wurden als frische Live-Punkte gezeichnet');
    vm.runInContext('toggleLive(); selectMetric("temp")', sandbox);
    await new Promise(resolve => setImmediate(resolve));
    const requestsBefore = stateRequests;
    [...intervals.values()].forEach(callback => callback());
    await new Promise(resolve => setImmediate(resolve));
    if (stateRequests !== requestsBefore) throw new Error('Live läuft nach Verlassen des Vergleichs weiter');
    console.log('✅ Veraltete Sensoren erzeugen Lücken und andere Reiter stoppen Live');
});
