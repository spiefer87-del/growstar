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
    createElement: node, createTextNode: text => text,
};
const calls = [];
class Chart {
    constructor(canvas, config) { this.canvas = canvas; this.config = config; calls.push(this); }
    destroy() { this.destroyed = true; }
}
const series = ['temp', 'water_temp', 'outside_temp', 'hum', 'outside_hum', 'vpd', 'ppfd'];
const rows = [
    {ts: 1000, temp: 26, water_temp: null, outside_temp: 21, hum: 60, outside_hum: 50, vpd: 1.2, ppfd: 400},
    {ts: 1100, temp: 25.8, water_temp: 22, outside_temp: 20, hum: 62, outside_hum: 52, vpd: 1.1, ppfd: 390},
];
const context = {
    document, Chart, console, Date, Set, Object, Number, String, JSON,
    localStorage: {getItem: () => JSON.stringify(series), setItem() {}},
    fetch: async url => ({ok: true, json: async () => url === '/api/tents'
        ? {tents: [{id: 'tent_2', name: 'Zelt 2'}]} : rows}),
    setInterval() {}, setTimeout() {}, clearTimeout() {},
    history: {replaceState() {}}, window: {location: {href: ''}},
};
vm.runInNewContext(code, context);
setImmediate(() => {
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
});
