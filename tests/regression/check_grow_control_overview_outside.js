// Exercise the Grow Control cards without a browser or a running station.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const page = fs.readFileSync(path.join(__dirname, '../../templates/grow_control_dashboard.html'), 'utf8');
const script = page.match(/<script>([\s\S]*?)<\/script>/g).at(-1)
    .replace(/^<script>|<\/script>$/g, '')
    .replace(/{{\s*url_for\('grow_control_tent', tent_id='__TENT_ID__'\)\|tojson\s*}}/g,
        '"/grow-control/tents/__TENT_ID__"');

function node(tag = 'div') {
    return {
        tag, children: [], attributes: {},
        setAttribute(key, value) { this.attributes[key] = value; },
        append(...items) { this.children.push(...items); },
        appendChild(item) { this.children.push(item); },
        replaceChildren(...items) { this.children = items; },
    };
}
const grid = node();
const tents = [
    {id: 'tent_1', name: 'Zelt 1', runtime_loaded: true, control_enabled: true,
        temp: 26.2, hum: 66.9, vpd: 1.13, outside_temp: 19.1, outside_hum: 67.3,
        outside_vpd: 0.72, outside_temp_label: 'Thermometer', outside_hum_label: 'Feuchtesensor'},
    {id: 'tent_2', name: 'Zelt 2', runtime_loaded: false,
        temp: null, hum: null, vpd: null, outside_temp: null, outside_hum: null, outside_vpd: null},
];
vm.runInNewContext(script, {
    document: {getElementById: () => grid, createElement: node},
    fetch: async () => ({ok: true, json: async () => ({tents})}),
    window: {setInterval() {}}, console,
});
setImmediate(() => {
    if (grid.children.length !== 2) throw new Error('Beide Stationen müssen erscheinen');
    for (const card of grid.children) {
        if (card.tag !== 'a' || !card.href.includes('/grow-control/tents/'))
            throw new Error('Die ganze Stationskachel muss ein Link sein');
        if (card.children.some(child => child.tag === 'a'))
            throw new Error('Verschachtelter Öffnen-Link in der Kachel');
    }
    const [, inside, heading, outside, footer] = grid.children[0].children;
    if (inside.children.length !== 3 || outside.children.length !== 3 ||
        heading.textContent !== 'Außenwerte' || footer.children.length !== 1)
        throw new Error('Innen- und Außenreihe brauchen jeweils drei Kacheln ohne Öffnen-Button');
    const texts = outside.children.map(tile => tile.children.map(child => child.textContent));
    if (texts[0][1] !== '19.1 °C' || texts[1][1] !== '67.3 %' || texts[2][1] !== '0.72 kPa')
        throw new Error('Die drei Außenwerte fehlen');
    const empty = grid.children[1].children[3].children.map(tile => tile.children[1].textContent);
    if (empty.some(value => value !== '—'))
        throw new Error('Fehlende Außenwerte dürfen nicht als Null erscheinen');
    console.log('✅ Ganze Stationskachel klickbar, drei Außenwerte und sichere Leerwerte');
});
